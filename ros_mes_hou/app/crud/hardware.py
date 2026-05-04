# app/crud/hardware.py
from sqlalchemy.orm import Session
from app.db import models
from app.schemas import hardware as schemas

# 获取所有硬件列表
def get_all_hardware(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Hardware).offset(skip).limit(limit).all()

# 新增硬件
def create_hardware(db: Session, hardware: schemas.HardwareCreate):
    # 将前端传来的数据解包并转为数据库 ORM 对象
    db_hardware = models.Hardware(**hardware.model_dump())
    db.add(db_hardware)
    db.commit()             # 提交事务
    db.refresh(db_hardware) # 刷新获取数据库生成的 ID
    return db_hardware