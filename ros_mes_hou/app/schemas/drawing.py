from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DrawingCreate(BaseModel):
    drawing_name: str
    drawing_description: Optional[str] = None
    notes: Optional[str] = None


class DrawingUpdate(BaseModel):
    drawing_name: Optional[str] = None
    drawing_description: Optional[str] = None
    notes: Optional[str] = None


class DrawingResponse(BaseModel):
    drawing_id: int
    drawing_name: str
    drawing_description: Optional[str] = None
    drawing_file: str
    creator_id: int
    create_time: Optional[datetime] = None
    modify_time: Optional[datetime] = None
    latest_version_id: Optional[int] = None
    del_flag: bool = False
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class DrawingVersionResponse(BaseModel):
    version_id: int
    drawing_id: int
    drawing_file: str
    creator_id: int
    create_time: Optional[datetime] = None
    modify_id: Optional[int] = None
    modify_time: Optional[datetime] = None
    del_flag: bool = False
    notes: Optional[str] = None

    class Config:
        from_attributes = True
