# app/schemas/hardware.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

# 基础模型，包含共有的字段
class HardwareBase(BaseModel):
    name: str
    type: Optional[str] = None
    status: Optional[str] = None
    ip_address: Optional[str] = None
    description: Optional[str] = None

# 用于创建数据时接收前端传参的模型
class HardwareCreate(HardwareBase):
    pass

# 用于返回给前端的模型（包含数据库自动生成的 id 和更新时间）
class HardwareResponse(HardwareBase):
    id: int
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True  # 允许将 SQLAlchemy ORM 模型直接转换为 Pydantic 字典