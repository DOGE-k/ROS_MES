# app/api/endpoints/control.py
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from app.api.deps import get_current_user
from app.db import models
from app.services import ros_control
from app.schemas.hardware import HardwareFeedback, EmergencyStopResponse

router = APIRouter()

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