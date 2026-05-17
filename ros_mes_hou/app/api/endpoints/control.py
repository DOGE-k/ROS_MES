# app/api/endpoints/control.py
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from app.api.deps import get_current_user
from app.crud import finetuning as finetuning_crud
from app.db import models
from app.db.database import get_db
from app.schemas import finetuning as finetuning_schemas
from app.services import ros_control
from app.services.ros_dispatcher import RosDispatchError, ros_dispatcher
from app.services.rosbridge_gateway import (
    RosbridgeError,
    build_fine_tuning_publish_payload,
    rosbridge_dispatcher,
    stream_feedback,
)
from app.schemas.hardware import HardwareFeedback, EmergencyStopResponse
from sqlalchemy.orm import Session

router = APIRouter()


@router.post("/finetuning", response_model=finetuning_schemas.FineTuningApiResponse)
def send_fine_tuning(
    record: finetuning_schemas.FineTuningCreate,
    db: Session = Depends(get_db),
    dispatcher=rosbridge_dispatcher,
):
    db_record = finetuning_crud.create_fine_tuning_record(
        db=db,
        record=record,
        username="web_frontend",
    )
    business_device_id = int(record.device_id or db_record.Device_ID)
    position = float(record.position if record.position is not None else db_record.new_value)
    payload = build_fine_tuning_publish_payload(db_record.parameter_name, position)
    payload["business"] = {
        "module_id": record.module_id,
        "device_id": business_device_id,
        "unit_id": record.unit_id,
        "unit_row_id": record.unit_row_id,
    }

    try:
        dispatch_result = dispatcher.dispatch("fine_tuning", payload)
    except (RosDispatchError, RosbridgeError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "code": 200,
        "message": "微调下发成功",
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
        async for feedback in stream_feedback():
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
    result = await ros_control.test_serial_connection()
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
    status_data = await ros_control.get_hardware_status()
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
    success = await ros_control.trigger_emergency_stop()
    
    if success:
        return {
            "success": True,
            "message": "急停指令已成功下发至底层节点！",
            "timestamp": datetime.now()
        }
    else:
        raise HTTPException(status_code=500, detail="急停指令发送失败，请检查 ROS 节点连接！")
