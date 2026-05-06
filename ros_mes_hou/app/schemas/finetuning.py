# app/schemas/finetuning.py
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class FineTuningCreate(BaseModel):
    """兼容旧版记录格式和新版前端微调格式。

    旧版字段：hardware_id / parameter_name / old_value / new_value
    新版字段：module_id / device_id / position
    """

    hardware_id: Optional[int] = None
    parameter_name: Optional[str] = None
    old_value: Optional[float] = None
    new_value: Optional[float] = None

    module_id: Optional[int] = None
    device_id: Optional[int] = None
    position: Optional[float] = None

    @model_validator(mode="after")
    def validate_payload(self):
        has_new_front_payload = self.device_id is not None and self.position is not None
        has_legacy_payload = (
            self.hardware_id is not None
            and self.parameter_name is not None
            and self.new_value is not None
        )
        if not has_new_front_payload and not has_legacy_payload:
            raise ValueError(
                "微调参数不完整：新版格式需要 device_id 与 position；"
                "旧版格式需要 hardware_id、parameter_name 与 new_value"
            )
        return self


class FineTuningResponse(BaseModel):
    id: int
    hardware_id: int
    parameter_name: str
    old_value: Optional[float] = None
    new_value: float
    adjusted_by: Optional[str] = None
    adjusted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class FineTuningPoint(BaseModel):
    device_id: int
    position: float
    type: str = "axis"


class FineTuningApiResponse(BaseModel):
    code: int = 200
    message: str
    data: List[FineTuningPoint]
    dispatch: Optional[Dict[str, Any]] = None


class FineTuningConfigDevice(BaseModel):
    device_id: Optional[int] = None
    label: Optional[str] = None
    initial: float = 0
    adjust: Optional[float] = 0
    current: float = 0


class FineTuningConfigCreate(BaseModel):
    module_id: int
    device_id: int
    x: float = 0
    y: float = 0
    z: float = 0
    devices: List[FineTuningConfigDevice] = Field(default_factory=list)


class FineTuningConfigResponse(BaseModel):
    id: int
    module_id: int
    device_id: int
    config: Dict[str, Any]
    saved_by: Optional[str] = None
    created_at: Optional[datetime] = None
