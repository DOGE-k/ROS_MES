# app/api/endpoints/finetuning.py

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.crud import finetuning as crud
from app.db.database import get_db
from app.schemas import finetuning as schemas
router = APIRouter()


@router.post("/", response_model=schemas.FineTuningApiResponse)
def create_record(
    record: schemas.FineTuningCreate,
    db: Session = Depends(get_db),
):
    """
    单轴微调：
    1. 记录 SQLite
    2. 返回前端需要的 data 数组
    """
    db_record = crud.create_fine_tuning_record(
        db=db,
        record=record,
        creater_id=1,
    )

    device_id = record.device_id or 0
    position = record.position if record.position is not None else db_record.new_value

    return {
        "code": 200,
        "message": "微调成功",
        "data": [
            {
                "device_id": int(device_id),
                "position": float(position),
                "type": "axis",
                "parameter_name": db_record.parameter_name,
            },
            {
                "device_id": -1,
                "position": 0.0,
                "type": "pressure",
            },
        ],
    }


@router.get("/", response_model=List[schemas.FineTuningResponse])
def read_records(
    skip: int = 0,
    limit: int = 100,
    module_id: Optional[int] = Query(None),
    unit_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """
    获取微调记录列表。
    """
    return crud.get_fine_tuning_records(db, skip=skip, limit=limit, module_id=module_id, unit_id=unit_id)


@router.post("/config")
def save_config(
    config: schemas.FineTuningConfigCreate,
    db: Session = Depends(get_db),
):
    """
    保存机械臂当前配置快照：
    存 SQLite
    """
    db_config = crud.save_fine_tuning_config(
        db=db,
        config=config,
        creater_id=1,
    )

    return {
        "code": 200,
        "message": "配置保存成功",
        "data": {
            "id": db_config.id,
            "module_id": db_config.module_id,
            "unit_id": db_config.unit_id,
            "sensor_id": db_config.sensor_id,
            "config": crud.parse_config(db_config),
            "creater_id": db_config.creater_id,
            "create_time": str(db_config.create_time),
            "notes": db_config.notes,
            "del_flag": db_config.del_flag,
        },
    }
