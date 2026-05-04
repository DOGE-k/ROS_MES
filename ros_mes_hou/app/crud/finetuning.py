# app/crud/finetuning.py
from sqlalchemy.orm import Session
from app.db import models
from app.schemas import finetuning as schemas

def get_fine_tuning_records(db: Session, skip: int = 0, limit: int = 100):
    # 按时间倒序排列，最新的修改在最前面
    return db.query(models.FineTuning).order_by(models.FineTuning.adjusted_at.desc()).offset(skip).limit(limit).all()

def create_fine_tuning_record(db: Session, record: schemas.FineTuningCreate, username: str):
    # 将前端传来的数据转化为字典，并强制加入 adjusted_by 字段
    db_record = models.FineTuning(**record.model_dump(), adjusted_by=username)
    db.add(db_record)
    db.commit()
    db.refresh(db_record)
    return db_record