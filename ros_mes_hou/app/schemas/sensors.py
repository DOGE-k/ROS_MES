from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SensorBase(BaseModel):
    sensor_ID: int
    sensordescript: Optional[str] = None
    IsRead: int = 1
    Device_ID: int
    Unit_ID: int
    unit_row_id: int
    Unit_address: int
    Notes: Optional[str] = None


class SensorCreate(SensorBase):
    creater_id: int = 1


class SensorUpdate(BaseModel):
    sensor_ID: Optional[int] = None
    sensordescript: Optional[str] = None
    IsRead: Optional[int] = None
    Device_ID: Optional[int] = None
    Unit_ID: Optional[int] = None
    unit_row_id: Optional[int] = None
    Unit_address: Optional[int] = None
    Notes: Optional[str] = None


class SensorResponse(SensorBase):
    id: int
    creater_id: int
    Createtime: Optional[datetime] = None
    del_flag: bool = False

    class Config:
        from_attributes = True
