# app/schemas/finetuning.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class FineTuningBase(BaseModel):
    hardware_id: int            # 关联的硬件 ID
    parameter_name: str         # 修改的参数名，比如 "joint_1_speed"
    old_value: Optional[float] = None
    new_value: float            # 新参数值

# 接收前端传来的数据
class FineTuningCreate(FineTuningBase):
    pass

# 返回给前端的数据格式
class FineTuningResponse(FineTuningBase):
    id: int
    adjusted_by: Optional[str] = None  # 记录操作人
    adjusted_at: Optional[datetime] = None

    class Config:
        from_attributes = True