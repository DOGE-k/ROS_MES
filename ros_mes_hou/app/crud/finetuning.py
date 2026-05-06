# app/crud/finetuning.py
import json
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.db import models
from app.schemas import finetuning as schemas


def get_fine_tuning_records(db: Session, skip: int = 0, limit: int = 100):
    # 按时间倒序排列，最新的修改在最前面
    return (
        db.query(models.FineTuning)
        .order_by(models.FineTuning.adjusted_at.desc(), models.FineTuning.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_latest_position(db: Session, device_id: int) -> Optional[float]:
    latest = (
        db.query(models.FineTuning)
        .filter(models.FineTuning.hardware_id == device_id)
        .order_by(models.FineTuning.adjusted_at.desc(), models.FineTuning.id.desc())
        .first()
    )
    return latest.new_value if latest else None


def create_fine_tuning_record(
    db: Session,
    record: schemas.FineTuningCreate,
    username: str,
):
    """创建微调记录。

    新版前端传 device_id / position，这里映射到历史表结构，避免直接破坏旧表。
    """

    if record.device_id is not None and record.position is not None:
        device_id = int(record.device_id)
        previous = get_latest_position(db, device_id)
        db_record = models.FineTuning(
            hardware_id=device_id,
            parameter_name=f"module_{record.module_id or 0}_position",
            old_value=previous,
            new_value=float(record.position),
            adjusted_by=username,
        )
    else:
        db_record = models.FineTuning(
            hardware_id=int(record.hardware_id),
            parameter_name=str(record.parameter_name),
            old_value=record.old_value,
            new_value=float(record.new_value),
            adjusted_by=username,
        )

    db.add(db_record)
    db.commit()
    db.refresh(db_record)
    return db_record


def save_fine_tuning_config(
    db: Session,
    config: schemas.FineTuningConfigCreate,
    username: str,
):
    config_dict: Dict[str, Any] = config.model_dump()
    db_config = models.FineTuningConfig(
        module_id=config.module_id,
        device_id=config.device_id,
        config_json=json.dumps(config_dict, ensure_ascii=False),
        saved_by=username,
    )
    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    return db_config


def parse_config(db_config: models.FineTuningConfig) -> Dict[str, Any]:
    try:
        return json.loads(db_config.config_json)
    except Exception:
        return {}
