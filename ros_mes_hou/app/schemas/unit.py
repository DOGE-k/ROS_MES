from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class UnitBase(BaseModel):
    UnitDescript: Optional[str] = None
    Device_ID: int
    Notes: Optional[str] = None


class UnitCreate(UnitBase):
    Unit_ID: int
    creater_id: int = 1


class UnitUpdate(BaseModel):
    UnitDescript: Optional[str] = None
    Device_ID: Optional[int] = None
    Notes: Optional[str] = None


class UnitResponse(UnitBase):
    id: int
    Unit_ID: int
    creater_id: int
    Createtime: Optional[datetime] = None
    del_flag: bool = False

    class Config:
        from_attributes = True
