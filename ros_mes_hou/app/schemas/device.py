from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DeviceBase(BaseModel):
    Model_ID: int
    Devicedescript: Optional[str] = None
    DeviceAddress: int
    Notes: Optional[str] = None


class DeviceCreate(DeviceBase):
    creater_id: int = 1


class DeviceUpdate(BaseModel):
    Model_ID: Optional[int] = None
    Devicedescript: Optional[str] = None
    DeviceAddress: Optional[int] = None
    Notes: Optional[str] = None


class DeviceResponse(DeviceBase):
    Device_ID: int
    creater_id: int
    Createtime: Optional[datetime] = None
    del_flag: bool = False

    class Config:
        from_attributes = True
