# app/schemas/finetuning.py
from datetime import datetime
from typing import Any, Dict, List, Optional, Literal

from pydantic import BaseModel, Field, model_validator


class FineTuningCreate(BaseModel):
    module_id: Optional[int] = None
    device_id: Optional[int] = None
    Device_ID: Optional[int] = None
    unit_id: Optional[int] = None
    position: Optional[float] = None
    parameter_name: Optional[str] = None
    old_value: Optional[float] = None
    new_value: Optional[float] = None

    @model_validator(mode="after")
    def validate_payload(self):
        if self.device_id is None and self.Device_ID is not None:
            self.device_id = self.Device_ID
        if self.position is None and self.new_value is not None:
            self.position = self.new_value
        if self.module_id is None:
            raise ValueError("fine-tuning payload requires module_id")
        if self.unit_id is None:
            raise ValueError("fine-tuning payload requires unit_id")
        if self.position is None and self.new_value is None:
            raise ValueError("fine-tuning payload requires position or new_value")
        return self


class FineTuningResponse(BaseModel):
    id: int
    module_id: int
    unit_id: int
    module_address: Optional[int] = None
    module_descript: Optional[str] = None
    parameter_name: str
    old_value: Optional[float] = None
    new_value: float
    creater_id: int
    create_time: Optional[datetime] = None
    notes: Optional[str] = None
    del_flag: bool = False

    class Config:
        from_attributes = True


class FineTuningPoint(BaseModel):
    device_id: int
    position: float
    type: str = "axis"
    parameter_name: Optional[str] = None


class BatchAdjustment(BaseModel):
    parameter_name: Literal["rotation", "swing", "telescopic"]
    position: float = Field(ge=-360, le=360, allow_inf_nan=False)


class FineTuningBatchCreate(BaseModel):
    request_id: str = Field(min_length=8, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    module_id: int = Field(gt=0)
    unit_id: int = Field(gt=0)
    connection_revision: Optional[int] = Field(default=None, ge=0)
    adjustments: List[BatchAdjustment] = Field(min_length=1, max_length=3)

    @model_validator(mode="after")
    def validate_adjustments(self):
        names = [item.parameter_name for item in self.adjustments]
        if len(set(names)) != len(names) or any(item.position == 0 for item in self.adjustments):
            raise ValueError("每轴仅允许一个非零增量")
        return self


class BatchAcknowledge(BaseModel):
    operator_confirmed: Literal[True]


class FineTuningApiResponse(BaseModel):
    code: int = 200
    message: str
    data: List[FineTuningPoint]
    dispatch: Optional[Dict[str, Any]] = None


class FineTuningConfigDevice(BaseModel):
    device_id: Optional[int] = None
    sensor_id: Optional[int] = None
    unit_id: Optional[int] = None
    parameter_name: Optional[str] = None
    label: Optional[str] = None
    initial: Optional[float] = 0
    adjust: Optional[float] = 0
    current: Optional[float] = 0


class FineTuningConfigCreate(BaseModel):
    module_id: int
    unit_id: int
    sensor_id: Optional[int] = None
    device_id: Optional[int] = None
    is_debug: bool = False
    drawing_id: Optional[int] = Field(default=None, gt=0)
    drawing_source: Literal["database", "builtin_mock"] = "database"
    connection_revision: Optional[int] = Field(default=None, ge=0)
    x: Optional[float] = 0
    y: Optional[float] = 0
    z: Optional[float] = 0
    feedback_state: Dict[str, Any] = Field(default_factory=dict)
    devices: List[FineTuningConfigDevice] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_sensor_id(self):
        if self.drawing_source == "builtin_mock" and (self.is_debug or self.drawing_id is not None):
            raise ValueError("builtin mock drawing must not bind a business drawing or skip drawing")
        if self.is_debug and self.drawing_id is not None:
            raise ValueError("debug fine-tuning config must not bind a drawing")
        if self.sensor_id is None and self.device_id is not None:
            self.sensor_id = self.device_id
        if self.sensor_id is None and self.devices:
            first_device = self.devices[0]
            self.sensor_id = first_device.sensor_id or first_device.device_id
        if self.sensor_id is None:
            raise ValueError("fine-tuning config requires sensor_id or device_id")
        return self


class FineTuningConfigResponse(BaseModel):
    id: int
    module_id: int
    unit_id: int
    sensor_id: int
    config: Dict[str, Any]
    creater_id: int
    create_time: Optional[datetime] = None
    notes: Optional[str] = None
    del_flag: bool = False
