# app/api/endpoints/finetuning.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.db.database import get_db
from app.schemas import finetuning as schemas
from app.crud import finetuning as crud
from app.api.deps import get_current_user
from app.db import models

router = APIRouter()

@router.post("/", response_model=schemas.FineTuningResponse)
def create_record(
    record: schemas.FineTuningCreate,
    db: Session = Depends(get_db),
    # 强制要求登录，并拿到当前登录用户的信息
    current_user: models.User = Depends(get_current_user) 
):
    """
    新增微调记录：自动记录当前操作人的用户名
    """
    # 将获取到的 username 传给 crud 层
    return crud.create_fine_tuning_record(db=db, record=record, username=current_user.username)

@router.get("/", response_model=List[schemas.FineTuningResponse])
def read_records(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user) # 同样需要登录才能查看
):
    """
    获取微调记录列表
    """
    return crud.get_fine_tuning_records(db, skip=skip, limit=limit)