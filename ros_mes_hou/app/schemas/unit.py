from datetime import datetime
from typing import Optional

from pydantic import BaseModel, model_validator


class UnitBase(BaseModel):
    UnitDescript: Optional[str] = None
    Module_ID: Optional[int] = None
    Device_ID: Optional[int] = None
    Notes: Optional[str] = None

    @model_validator(mode="after")
    def normalize_module_id(self):
        if self.Module_ID is None and self.Device_ID is not None:
            self.Module_ID = self.Device_ID
        if self.Module_ID is None:
            raise ValueError("unit requires Module_ID")
        return self


class UnitCreate(UnitBase):
    Unit_ID: int
    creater_id: int = 1


class UnitUpdate(BaseModel):
    UnitDescript: Optional[str] = None
    Module_ID: Optional[int] = None
    Device_ID: Optional[int] = None
    Notes: Optional[str] = None

    @model_validator(mode="after")
    def normalize_module_id(self):
        if self.Module_ID is None and self.Device_ID is not None:
            self.Module_ID = self.Device_ID
        return self


class UnitResponse(UnitBase):
    id: int
    Unit_ID: int
    creater_id: int
    Createtime: Optional[datetime] = None
    del_flag: bool = False

    class Config:
        from_attributes = True
