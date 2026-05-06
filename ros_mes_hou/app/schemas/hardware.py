# app/schemas/hardware.py
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class HardwareBase(BaseModel):
    name: str
    type: Optional[str] = None
    status: Optional[str] = None
    ip_address: Optional[str] = None
    description: Optional[str] = None


class HardwareCreate(HardwareBase):
    pass


class HardwareUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = None
    ip_address: Optional[str] = None
    description: Optional[str] = None


class HardwareResponse(HardwareBase):
    id: int
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class HardwareFeedback(BaseModel):
    """机器人硬件反馈数据模型。"""

    joints: List[float]
    status: str
    timestamp: float


class EmergencyStopResponse(BaseModel):
    success: bool
    message: str
    timestamp: datetime = datetime.now()
