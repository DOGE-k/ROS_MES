# app/schemas/hardware.py
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

# 基础模型，包含共有的字段
class HardwareBase(BaseModel):
    name: str
    type: Optional[str] = None
    status: Optional[str] = None
    ip_address: Optional[str] = None
    description: Optional[str] = None

# 用于创建数据时接收前端传参的模型
class HardwareCreate(HardwareBase):
    pass

# 用于返回给前端的模型（包含数据库自动生成的 id 和更新时间）
class HardwareResponse(HardwareBase):
    id: int
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True  # 允许将 SQLAlchemy ORM 模型直接转换为 Pydantic 字典

class HardwareFeedback(BaseModel):
    """
    机器人硬件反馈数据模型
    """
    joints: List[float]  # 关节角度
    status: str          # 状态描述
    timestamp: float     # 时间戳
    # 根据你实际的 ROS 话题数据结构来定义字段

# 紧急停止响应模型  
class EmergencyStopResponse(BaseModel):
    success: bool
    message: str
    timestamp: datetime = datetime.now()