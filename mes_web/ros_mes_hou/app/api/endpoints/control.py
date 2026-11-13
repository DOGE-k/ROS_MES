# app/api/endpoints/control.py
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from app.api.deps import get_current_user
from app.crud import finetuning as finetuning_crud
from app.db import models
from app.db.database import get_db
from app.schemas import finetuning as finetuning_schemas
from app.ros import get_ros_dispatcher
from app.ros.base import RosDispatchError, RosbridgeError
from app.ros.control_session import session_manager
from app.ros.rosbridge import build_fine_tuning_publish_payload, resolve_arm_from_unit_id, resolve_module_seg
from app.ros.finetuning_batch import batch_manager
from app.ros.stop_holds import BLOCK_MESSAGE, axis_numbers_for_arm, stop_holds, validate_target
from app.schemas.local_stop import LocalStopRequest
from app.ros.runtime_settings import runtime_settings, SettingsChange
from app.schemas.hardware import HardwareFeedback, EmergencyStopResponse, ManualEmergencyRelease
from sqlalchemy.orm import Session

router = APIRouter()


@router.get("/debug-settings")
def get_debug_settings(current_user: models.User = Depends(get_current_user)):
    return {"code": 200, "message": "当前服务连接配置", "data": runtime_settings.snapshot()}


@router.patch("/debug-settings")
def update_debug_settings(record: SettingsChange, current_user: models.User = Depends(get_current_user)):
    result = runtime_settings.update(record)
    get_ros_dispatcher().start_native_node()
    return {"code": 200, "message": "连接设置已应用，未自动下发任务", "data": result}


@router.get("/session")
def get_control_session(
    ttl_seconds: Optional[int] = Query(None, ge=0),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """最近一条微调会话记录及有效性。

    有效期由前端偏好传入，不在服务端落库；返回的 session 为空表示需要重新握手。
    """
    dispatcher = get_ros_dispatcher()
    data = session_manager.state(db, ttl_seconds=ttl_seconds, current_revision=dispatcher.revision)
    return {"code": 200, "message": "会话记录，续接未经设备复核", "data": {
        **data, "connection_revision": dispatcher.revision}}


@router.post("/session/{session_id}/resume")
def resume_control_session(
    session_id: str,
    ttl_seconds: Optional[int] = Body(None, embed=True, ge=0),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """校验并滑动会话有效期；只读记录，不发送模块确认或运动指令。"""
    dispatcher = get_ros_dispatcher()
    result = session_manager.resume(
        db, session_id, ttl_seconds=ttl_seconds, current_revision=dispatcher.revision)
    return {
        "code": 200,
        "message": "会话有效，可续接（未重新握手）" if result["valid"] else f"会话不可续接：{result['reason']}",
        "data": {**result, "connection_revision": dispatcher.revision},
    }


@router.post("/session/{session_id}/close")
def close_control_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """结束会话记录：只清除 MES 续接依据，不解绑设备、不发送任何指令。"""
    record = session_manager.close(db, session_id)
    if record is None:
        raise HTTPException(404, "会话记录不存在")
    return {"code": 200, "message": "已结束会话记录；未向设备发送指令", "data": record}


@router.post("/stop")
async def request_local_stop(
    record: LocalStopRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """局部停：只停目标模块或目标轴，其他模块继续可用；不清除全局急停联锁。

    发送成功只代表指令已进入 rosbridge，设备是否停止仍需反馈/现场确认。
    """
    dispatcher = get_ros_dispatcher()
    if record.connection_revision is not None and record.connection_revision != dispatcher.revision:
        raise HTTPException(409, "连接配置已更改，请重新读取设置后操作")
    client = getattr(dispatcher, "client", None)
    hold_mode = getattr(client, "execution_mode", "real")
    simulated = dispatcher.emergency_mode == "mock"
    try:
        validate_target(scope=record.scope, module_id=record.module_id, device_id=record.device_id)
        resolve_module_seg(record.module_id)
    except RosbridgeError as exc:
        raise HTTPException(422, str(exc)) from exc

    # 先记锁再发送：发送失败时锁定保留，避免操作员以为已经停住却继续下发
    hold = stop_holds.create(db, mode=hold_mode, scope=record.scope, module_id=record.module_id,
                             device_id=record.device_id, state="requested")
    if record.scope == "module":
        scope_label = f"模块 {record.module_id}"
        hold_axes = None
    elif record.scope == "arm":
        scope_label = f"模块 {record.module_id} 臂 {record.device_id}"
        hold_axes = axis_numbers_for_arm(record.device_id)
    else:
        scope_label = f"模块 {record.module_id} 轴 {record.device_id}"
        hold_axes = {int(record.device_id)}
    batch_manager.hold_target(record.module_id, axes=hold_axes, mode=hold_mode)
    try:
        with runtime_settings.operation(dispatcher.revision):
            sent = await dispatcher.trigger_local_stop(
                scope=record.scope, module_id=record.module_id, device_id=record.device_id)
    except Exception as exc:
        stop_holds.update_state(db, hold["id"], "unknown", f"局部停发送异常：{exc}")
        raise HTTPException(502, "局部停指令发送失败，MES 已锁定该目标；请现场确认设备状态") from exc

    if simulated:
        message = f"{scope_label} 模拟局部停已记录，未连接真实设备"
    elif sent:
        message = f"{scope_label} 局部停指令已发送；设备是否停止待确认"
    else:
        message = f"{scope_label} 局部停指令发送失败，MES 已锁定该目标"
    updated = stop_holds.update_state(db, hold["id"], "sent" if sent else "unknown", message) or hold
    print(f"操作员 {current_user.Username} 执行局部停：{scope_label}（{'模拟' if simulated else '真实'}）")
    return {"code": 200, "message": message, "data": {
        **updated, "simulated": simulated, "connection_revision": dispatcher.revision}}


@router.get("/stop/holds")
def list_local_stop_holds(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """当前环境的局部停记录；只读，不代表设备实测状态。"""
    dispatcher = get_ros_dispatcher()
    client = getattr(dispatcher, "client", None)
    mode = getattr(client, "execution_mode", "real")
    return {"code": 200, "message": "MES 局部停记录，未向设备发送查询", "data": {
        "mode": mode,
        "holds": stop_holds.active(db, mode),
        "connection_revision": dispatcher.revision,
    }}


@router.post("/stop/clear")
def clear_local_stop_holds(
    module_id: int = Query(..., ge=1),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """清除该模块的 MES 局部停记录：只恢复下发能力，不发送解除或运动指令。"""
    dispatcher = get_ros_dispatcher()
    client = getattr(dispatcher, "client", None)
    mode = getattr(client, "execution_mode", "real")
    cleared = stop_holds.clear_module(db, module_id, mode=mode)
    print(f"操作员 {current_user.Username} 清除模块 {module_id} 的局部停记录 {cleared} 条")
    return {"code": 200, "message": "已清除 MES 局部停记录；未发送解除或运动指令", "data": {
        "module_id": module_id, "cleared": cleared, "connection_revision": dispatcher.revision}}


@router.post("/stop/{hold_id}/clear")
def clear_local_stop_hold(
    hold_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """清除单条局部停记录；同 `/stop/clear`，不发指令。"""
    dispatcher = get_ros_dispatcher()
    client = getattr(dispatcher, "client", None)
    mode = getattr(client, "execution_mode", "real")
    result = stop_holds.clear(db, hold_id, mode=mode)
    if result is None:
        raise HTTPException(404, "局部停记录不存在")
    return {"code": 200, "message": "已清除 MES 局部停记录；未发送解除或运动指令", "data": result}


@router.post("/finetuning", response_model=finetuning_schemas.FineTuningApiResponse)
def send_fine_tuning(
    record: finetuning_schemas.FineTuningCreate,
    db: Session = Depends(get_db),
    dispatcher=None,
):
    dispatcher = dispatcher or get_ros_dispatcher()
    business_module_id = int(record.module_id or 0)
    business_device_id = int(record.device_id or 0)
    try:
        axis_index = ("rotation", "swing", "telescopic").index(record.parameter_name)
        expected_axis = (resolve_arm_from_unit_id(record.unit_id) - 1) * 3 + axis_index + 1
        if business_device_id != expected_axis:
            raise ValueError("轴号、机械臂和参数类型不匹配")
    except (ValueError, RosbridgeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    client = getattr(dispatcher, "client", None)
    batch_manager.assert_available(db, business_module_id, record.unit_id,
        mode=getattr(client, "execution_mode", "real"), safety_mode=getattr(client, "safety_mode", "real"),
        axes={expected_axis})
    position = float(record.position if record.position is not None else record.new_value)
    # 先做参数校验再落库，非法轴号/模块号不应产生脏记录
    try:
        payload = build_fine_tuning_publish_payload(
            record.parameter_name, position, business_module_id, business_device_id)
    except RosbridgeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db_record = finetuning_crud.create_fine_tuning_record(
        db=db,
        record=record,
        creater_id=1,
    )
    payload["business"] = {
        "module_id": business_module_id,
        "device_id": business_device_id,
        "unit_id": record.unit_id,
    }

    try:
        dispatch_result = dispatcher.dispatch("fine_tuning", payload)
    except (RosDispatchError, RosbridgeError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "code": 200,
        "message": "微调发送模拟成功，未连接真实设备" if dispatch_result.get("simulated") else "微调指令已写入 rosbridge 连接，尚无设备确认",
        "data": [
            {
                "device_id": business_device_id,
                "position": position,
                "type": "axis",
                "parameter_name": db_record.parameter_name,
            },
            {
                "device_id": -1,
                "position": 0.0,
                "type": "pressure",
            },
        ],
        "dispatch": dispatch_result,
    }

@router.post("/finetuning/batches", status_code=202)
async def create_finetuning_batch(
    record: finetuning_schemas.FineTuningBatchCreate,
    current_user: models.User = Depends(get_current_user),
):
    dispatcher = get_ros_dispatcher()
    if record.connection_revision is not None and record.connection_revision != dispatcher.revision:
        raise HTTPException(409, "连接配置已更改，请重新确认机械臂后提交")
    with runtime_settings.operation(dispatcher.revision):
        result = await batch_manager.start(record, dispatcher.client, current_user.User_ID)
    return {"code": 202, "message": "批次已登记，执行状态以查询结果为准", "data": result}


@router.get("/finetuning/batches/active")
def active_finetuning_batch(module_id: int, unit_id: int, current_user: models.User = Depends(get_current_user)):
    return {"code": 200, "message": "当前目标执行状态", "data": batch_manager.latest(module_id, unit_id, get_ros_dispatcher().client.execution_mode)}


@router.get("/finetuning/batches/by-request/{request_id}")
def get_batch_by_request(request_id: str, current_user: models.User = Depends(get_current_user)):
    return {"code": 200, "message": "提交结果查询，不触发运动", "data": batch_manager.by_request(request_id)}


@router.get("/finetuning/batches/{batch_id}")
def get_finetuning_batch(batch_id: str, current_user: models.User = Depends(get_current_user)):
    return {"code": 200, "message": "批次状态", "data": batch_manager.get(batch_id)}


@router.post("/finetuning/batches/{batch_id}/interrupt")
def interrupt_finetuning_batch(batch_id: str, current_user: models.User = Depends(get_current_user)):
    return {"code": 200, "message": "仅停止后续下发，不替代硬件急停", "data": batch_manager.interrupt(batch_id)}


@router.post("/finetuning/batches/{batch_id}/acknowledge")
def acknowledge_finetuning_batch(batch_id: str, record: finetuning_schemas.BatchAcknowledge,
                                current_user: models.User = Depends(get_current_user)):
    return {"code": 200, "message": "已关闭 MES 待核实记录；未发送运动", "data": batch_manager.acknowledge(batch_id)}


@router.get("/emergency_stop/status")
def get_emergency_state(current_user: models.User = Depends(get_current_user)):
    dispatcher = get_ros_dispatcher()
    return {"code": 200, "message": "MES 控制联锁状态，不是设备实测", "data": {
        **batch_manager.safety(dispatcher.emergency_mode), "connection_revision": dispatcher.revision}}


@router.post("/emergency_stop/manual_release")
async def manually_release_emergency_stop(
    record: ManualEmergencyRelease,
    current_user: models.User = Depends(get_current_user),
):
    dispatcher = get_ros_dispatcher()
    if record.connection_revision != dispatcher.revision:
        raise HTTPException(409, "连接配置已更改，请查看最新急停状态后重新确认")
    with runtime_settings.operation(dispatcher.revision, require_idle=True):
        state = batch_manager.clear_safety(record.expected_generation, dispatcher.emergency_mode)
        if state["simulated"]:
            dispatcher.emergency_client.robot.stop(False)
    print(f"操作员 {current_user.Username} 人工确认并清除了 MES 急停记录。")
    return {"code": 200, "message": "已人工解除 MES 急停状态", "data": {
        **state, "connection_revision": dispatcher.revision}}


@router.websocket("/feedback/ws")
async def fine_tuning_feedback_ws(websocket: WebSocket):
    await websocket.accept()
    try:
        async for feedback in get_ros_dispatcher().stream_feedback():
            await websocket.send_json(feedback)
    except WebSocketDisconnect:
        return

@router.get("/serial_test")
async def test_serial_connection(
    current_user: models.User = Depends(get_current_user)
):
    """
    串口连接测试：
    通过串口向下位机发送测试数据，并等待响应确认，来验证上下位机通信是否正常
    """
    result = await get_ros_dispatcher().test_serial_connection()
    return {
        "code": 200,
        "message": "串口测试完成" if result.get("success") else "串口测试失败",
        "data": result,
    }

@router.get("/hardware/realtime", response_model=HardwareFeedback)
async def get_realtime_hardware_status(
    current_user: models.User = Depends(get_current_user)
):
    """
    获取底层机械臂的真实硬件状态（绕过数据库直接读硬件）
    """
    status_data = await get_ros_dispatcher().get_hardware_status()
    if "error" in status_data:
         raise HTTPException(status_code=500, detail=status_data["error"])
    return status_data

@router.post("/emergency_stop", response_model=EmergencyStopResponse)
async def activate_emergency_stop(
    current_user: models.User = Depends(get_current_user)
):
    """
    点击按钮：触发机械臂急停！
    """
    print(f"警告：操作员 {current_user.Username} 触发了紧急停止！")
    dispatcher = get_ros_dispatcher()
    mode = dispatcher.emergency_mode
    with runtime_settings.operation(dispatcher.revision):
        batch_manager.set_safety("stop_requested", mode)
        success = await dispatcher.trigger_emergency_stop()
        batch_manager.set_safety("stop_sent" if success else "stop_unknown", mode)

    if success:
        return {
            "success": True,
            "message": "模拟急停成功，未连接真实设备" if mode == "mock" else "急停指令已发送；设备是否停止仍需状态反馈确认",
            "simulated": mode == "mock",
            "timestamp": datetime.now()
        }
    else:
        raise HTTPException(status_code=500, detail="急停指令发送失败，请检查 ROS 节点连接！")


@router.post("/emergency_stop/release", response_model=EmergencyStopResponse)
async def release_emergency_stop(
    current_user: models.User = Depends(get_current_user)
):
    """
    急停解除：/control/softstop_release → softstop_node 转发 /arm/cmd_vel [0x04]
    （三轴版接口清单 §5：系统级指令 1=急停 / 4=解除 / 8=模块停）
    """
    print(f"操作员 {current_user.Username} 执行急停解除。")
    dispatcher = get_ros_dispatcher()
    mode = dispatcher.emergency_mode
    with runtime_settings.operation(dispatcher.revision):
        success = await dispatcher.release_emergency_stop()
        batch_manager.set_safety(("clear" if mode == "mock" else "release_sent") if success else "stop_unknown", mode)

    if success:
        return {
            "success": True,
            "message": "模拟解除成功，未连接真实设备" if mode == "mock" else "急停解除指令已发送；设备解除状态尚未确认",
            "simulated": mode == "mock",
            "timestamp": datetime.now()
        }
    else:
        raise HTTPException(status_code=500, detail="急停解除指令发送失败，请检查 ROS 节点连接！")
