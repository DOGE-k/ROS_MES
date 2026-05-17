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
    device_id: Optional[int] = None,
):
    query = db.query(models.FineTuning)
    if device_id is not None:
        query = query.filter(models.FineTuning.Device_ID == device_id)
    return (
        query.order_by(models.FineTuning.adjusted_at.desc(), models.FineTuning.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_latest_position(db: Session, device_id: int) -> Optional[float]:
    latest = (
        db.query(models.FineTuning)
        .filter(models.FineTuning.Device_ID == device_id)
        .order_by(models.FineTuning.adjusted_at.desc(), models.FineTuning.id.desc())
        .first()
    )
    return latest.new_value if latest else None


def get_device_snapshot(db: Session, device_id: int) -> Dict[str, Any]:
    device = (
        db.query(models.Device)
        .filter(models.Device.Device_ID == device_id, models.Device.del_flag == False)
        .first()
    )
    if not device:
        return {"DeviceAddress": None, "Devicedescript": None}
    return {
        "DeviceAddress": device.DeviceAddress,
        "Devicedescript": device.Devicedescript,
    }


def create_fine_tuning_record(
    db: Session,
    record: schemas.FineTuningCreate,
    username: str,
):
    device_id = int(record.device_id)
    new_value = record.position if record.position is not None else record.new_value
    previous = get_latest_position(db, device_id)
    device_snapshot = get_device_snapshot(db, device_id)

    db_record = models.FineTuning(
        Device_ID=device_id,
        DeviceAddress=device_snapshot["DeviceAddress"],
        Devicedescript=device_snapshot["Devicedescript"],
        parameter_name=record.parameter_name or f"module_{record.module_id or 0}_position",
        old_value=record.old_value if record.old_value is not None else previous,
        new_value=float(new_value),
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
