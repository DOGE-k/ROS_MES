# app/api/endpoints/control.py
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from app.api.deps import get_current_user
from app.crud import finetuning as finetuning_crud
from app.db import models
from app.db.database import get_db
from app.schemas import finetuning as finetuning_schemas
from app.ros import get_ros_dispatcher
from app.ros.base import RosDispatchError, RosbridgeError
from app.ros.rosbridge import build_fine_tuning_publish_payload, resolve_arm_from_unit_id
from app.ros.finetuning_batch import batch_manager
from app.ros.runtime_settings import runtime_settings, SettingsChange
from app.schemas.hardware import HardwareFeedback, EmergencyStopResponse
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
        mode=getattr(client, "execution_mode", "real"), safety_mode=getattr(client, "safety_mode", "real"))
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
