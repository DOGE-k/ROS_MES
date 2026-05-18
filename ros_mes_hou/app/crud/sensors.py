from sqlalchemy.orm import Session

from app.db import models
from app.schemas import sensors as schemas


def get_sensors(db: Session):
    return db.query(models.Sensor).filter(models.Sensor.del_flag == False).all()


def get_sensors_by_unit(db: Session, unit_row_id: int):
    return db.query(models.Sensor).filter(
        models.Sensor.unit_row_id == unit_row_id,
        models.Sensor.del_flag == False,
    ).all()


def get_sensor(db: Session, sensor_id: int):
    return db.query(models.Sensor).filter(
        models.Sensor.id == sensor_id,
        models.Sensor.del_flag == False,
    ).first()


def get_sensor_by_device_and_sensor_id(db: Session, device_id: int, sensor_id: int):
    return db.query(models.Sensor).filter(
        models.Sensor.Device_ID == device_id,
        models.Sensor.sensor_ID == sensor_id,
        models.Sensor.del_flag == False,
    ).first()


def create_sensor(db: Session, data: schemas.SensorCreate):
    existing = get_sensor_by_device_and_sensor_id(db, data.Device_ID, data.sensor_ID)
    if existing:
        return None
    db_item = models.Sensor(**data.model_dump())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


def update_sensor(db: Session, sensor_id: int, data: schemas.SensorUpdate):
    db_item = get_sensor(db, sensor_id)
    if not db_item:
        return None
    update_data = data.model_dump(exclude_unset=True)
    target_device_id = update_data.get("Device_ID", db_item.Device_ID)
    target_sensor_id = update_data.get("sensor_ID", db_item.sensor_ID)
    existing = get_sensor_by_device_and_sensor_id(db, target_device_id, target_sensor_id)
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
