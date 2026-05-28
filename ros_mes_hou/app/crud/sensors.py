from sqlalchemy.orm import Session

from app.db import models
from app.schemas import sensors as schemas


def get_sensors(db: Session):
    return db.query(models.Sensor).filter(models.Sensor.del_flag == False).all()


def get_sensors_by_unit(db: Session, unit_id: int):
    unit = db.query(models.Unit).filter(
        models.Unit.id == unit_id,
        models.Unit.del_flag == False,
    ).first()
    if unit:
        return db.query(models.Sensor).filter(
            models.Sensor.Module_ID == unit.Module_ID,
            models.Sensor.Unit_ID == unit.Unit_ID,
            models.Sensor.del_flag == False,
        ).all()
    return db.query(models.Sensor).filter(
        models.Sensor.Unit_ID == unit_id,
        models.Sensor.del_flag == False,
    ).all()


def get_sensor(db: Session, sensor_id: int):
    return db.query(models.Sensor).filter(
        models.Sensor.id == sensor_id,
        models.Sensor.del_flag == False,
    ).first()


def get_sensor_by_module_and_sensor_id(db: Session, module_id: int, sensor_id: int):
    return db.query(models.Sensor).filter(
        models.Sensor.Module_ID == module_id,
        models.Sensor.sensor_ID == sensor_id,
        models.Sensor.del_flag == False,
    ).first()


def create_sensor(db: Session, data: schemas.SensorCreate):
    module_id = data.Module_ID
    if module_id is None and data.unit_row_id is not None:
        unit = db.query(models.Unit).filter(
            models.Unit.id == data.unit_row_id,
            models.Unit.del_flag == False,
        ).first()
        if unit:
            module_id = unit.Module_ID
    if module_id is None:
        return None
    existing = get_sensor_by_module_and_sensor_id(db, module_id, data.sensor_ID)
    if existing:
        return None
    create_data = data.model_dump(exclude={"Device_ID", "unit_row_id"})
    create_data["Module_ID"] = module_id
    db_item = models.Sensor(**create_data)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


def update_sensor(db: Session, sensor_id: int, data: schemas.SensorUpdate):
    db_item = get_sensor(db, sensor_id)
    if not db_item:
        return None
    update_data = data.model_dump(exclude_unset=True)
    if update_data.get("Module_ID") is None and update_data.get("unit_row_id") is not None:
        unit = db.query(models.Unit).filter(
            models.Unit.id == update_data["unit_row_id"],
            models.Unit.del_flag == False,
        ).first()
        if unit:
            update_data["Module_ID"] = unit.Module_ID
            update_data.setdefault("Unit_ID", unit.Unit_ID)
    update_data.pop("Device_ID", None)
    update_data.pop("unit_row_id", None)
    target_module_id = update_data.get("Module_ID", db_item.Module_ID)
    target_sensor_id = update_data.get("sensor_ID", db_item.sensor_ID)
    existing = get_sensor_by_module_and_sensor_id(db, target_module_id, target_sensor_id)
    if existing and existing.id != sensor_id:
        return None
    for field, value in update_data.items():
        setattr(db_item, field, value)
    db.commit()
    db.refresh(db_item)
    return db_item


def delete_sensor(db: Session, sensor_id: int):
    db_item = get_sensor(db, sensor_id)
    if not db_item:
        return False
    db_item.del_flag = True
    db.commit()
    return True
