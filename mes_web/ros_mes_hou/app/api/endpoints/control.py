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
from app.ros.rosbridge import build_fine_tuning_publish_payload
from app.schemas.hardware import HardwareFeedback, EmergencyStopResponse
from sqlalchemy.orm import Session

router = APIRouter()


@router.post("/finetuning", response_model=finetuning_schemas.FineTuningApiResponse)
def send_fine_tuning(
    record: finetuning_schemas.FineTuningCreate,
    db: Session = Depends(get_db),
    dispatcher=None,
):
    dispatcher = dispatcher or get_ros_dispatcher()
    business_module_id = int(record.module_id or 0)
    business_device_id = int(record.device_id or 0)
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
        "message": "微调指令已写入 rosbridge 连接，尚无设备确认",
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
    success = await get_ros_dispatcher().trigger_emergency_stop()

    if success:
        return {
            "success": True,
            "message": "急停指令已成功下发至底层节点！",
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
    success = await get_ros_dispatcher().release_emergency_stop()

    if success:
        return {
            "success": True,
            "message": "急停解除指令已成功下发至底层节点！",
            "timestamp": datetime.now()
        }
    else:
        raise HTTPException(status_code=500, detail="急停解除指令发送失败，请检查 ROS 节点连接！")
