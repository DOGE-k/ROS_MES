# app/crud/finetuning.py
import json
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.db import models
from app.schemas import finetuning as schemas


def get_fine_tuning_records(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    module_id: Optional[int] = None,
    unit_id: Optional[int] = None,
):
    query = db.query(models.FineTuning)
    if module_id is not None:
        query = query.filter(models.FineTuning.module_id == module_id)
    if unit_id is not None:
        query = query.filter(models.FineTuning.unit_id == unit_id)
    return (
        query.order_by(models.FineTuning.create_time.desc(), models.FineTuning.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_latest_position(
    db: Session,
    module_id: int,
    unit_id: int,
    parameter_name: Optional[str] = None,
) -> Optional[float]:
    query = db.query(models.FineTuning).filter(
        models.FineTuning.module_id == module_id,
        models.FineTuning.unit_id == unit_id,
    )
    if parameter_name:
        query = query.filter(models.FineTuning.parameter_name == parameter_name)

    latest = (
        query
        .order_by(models.FineTuning.create_time.desc(), models.FineTuning.id.desc())
        .first()
    )
    return latest.new_value if latest else None


def create_fine_tuning_record(
    db: Session,
    record: schemas.FineTuningCreate,
    creater_id: int = 1,
):
    module_id = int(record.module_id)
    unit_id = int(record.unit_id)
    new_value = record.position if record.position is not None else record.new_value
    parameter_name = record.parameter_name or f"module_{module_id}_unit_{unit_id}_position"
    previous = get_latest_position(db, module_id, unit_id, parameter_name)

    db_record = models.FineTuning(
        module_id=module_id,
        unit_id=unit_id,
        module_address=module_id,
        module_descript=None,
        parameter_name=parameter_name,
        old_value=record.old_value if record.old_value is not None else previous,
        new_value=float(new_value),
        creater_id=creater_id,
    )

    db.add(db_record)
    db.commit()
    db.refresh(db_record)
    return db_record


def save_fine_tuning_config(
    db: Session,
    config: schemas.FineTuningConfigCreate,
    creater_id: int = 1,
):
    config_dict: Dict[str, Any] = config.model_dump()
    db_config = models.FineTuningConfig(
        module_id=config.module_id,
        unit_id=config.unit_id,
        sensor_id=int(config.sensor_id),
        config_json=json.dumps(config_dict, ensure_ascii=False),
        creater_id=creater_id,
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
