# app/schemas/hardware.py
from datetime import datetime
from typing import List, Literal

from pydantic import BaseModel, Field


class HardwareFeedback(BaseModel):
    """机器人硬件反馈数据模型。"""

    joints: List[float]
    status: str
    timestamp: float
    simulated: bool = False


class EmergencyStopResponse(BaseModel):
    success: bool
    message: str
    timestamp: datetime = datetime.now()
    simulated: bool = False


class ManualEmergencyRelease(BaseModel):
    operator_confirmed: Literal[True]
    expected_generation: int = Field(ge=0)
    connection_revision: int = Field(ge=0)
