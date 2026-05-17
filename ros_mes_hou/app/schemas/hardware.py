# app/schemas/hardware.py
from datetime import datetime
from typing import List

from pydantic import BaseModel


class HardwareFeedback(BaseModel):
    """机器人硬件反馈数据模型。"""

    joints: List[float]
    status: str
    timestamp: float


class EmergencyStopResponse(BaseModel):
    success: bool
    message: str
    timestamp: datetime = datetime.now()
