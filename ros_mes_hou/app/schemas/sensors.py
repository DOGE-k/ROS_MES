from datetime import datetime
from typing import Optional

from pydantic import BaseModel, model_validator


class SensorBase(BaseModel):
    sensor_ID: int
    sensordescript: Optional[str] = None
    IsRead: int = 1
    Module_ID: Optional[int] = None
    Device_ID: Optional[int] = None
    Unit_ID: int
    unit_row_id: Optional[int] = None
    Unit_address: int
    Notes: Optional[str] = None

    @model_validator(mode="after")
    def normalize_module_id(self):
        if self.Module_ID is None and self.Device_ID is not None:
            self.Module_ID = self.Device_ID
        return self


class SensorCreate(SensorBase):
    creater_id: int = 1


class SensorUpdate(BaseModel):
    sensor_ID: Optional[int] = None
    sensordescript: Optional[str] = None
    IsRead: Optional[int] = None
    Module_ID: Optional[int] = None
    Device_ID: Optional[int] = None
    Unit_ID: Optional[int] = None
    unit_row_id: Optional[int] = None
    Unit_address: Optional[int] = None
    Notes: Optional[str] = None

    @model_validator(mode="after")
    def normalize_module_id(self):
        if self.Module_ID is None and self.Device_ID is not None:
            self.Module_ID = self.Device_ID
        return self


class SensorResponse(SensorBase):
    id: int
    creater_id: int
    Createtime: Optional[datetime] = None
    del_flag: bool = False

    class Config:
        from_attributes = True
