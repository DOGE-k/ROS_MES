from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ModelBase(BaseModel):
    Modelname: str
    Modeldescripte: Optional[str] = None
    Notes: Optional[str] = None


class ModelCreate(ModelBase):
    pass


class ModelUpdate(BaseModel):
    Modelname: Optional[str] = None
    Modeldescripte: Optional[str] = None
    Notes: Optional[str] = None


class ModelResponse(ModelBase):
    Model_ID: int
    creater_id: int
    Createtime: Optional[datetime] = None
    del_flag: bool = False

    class Config:
        from_attributes = True
