# app/api/endpoints/control.py
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from app.api.deps import get_current_user
from app.db import models
from app.services import ros_control
from app.schemas.hardware import HardwareFeedback, EmergencyStopResponse

router = APIRouter()

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
    print(f"警告：操作员 {current_user.username} 触发了紧急停止！")
    success = await ros_control.trigger_emergency_stop()
    
    if success:
        return {
            "success": True,
            "message": "急停指令已成功下发至底层节点！",
            "timestamp": datetime.now()
        }
    else:
        raise HTTPException(status_code=500, detail="急停指令发送失败，请检查 ROS 节点连接！")