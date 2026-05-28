from sqlalchemy.orm import Session

from app.db import models
from app.schemas import device as schemas


def get_devices(db: Session):
    return db.query(models.Module).filter(models.Module.del_flag == False).all()


def get_devices_by_model(db: Session, model_id: int):
    return db.query(models.Module).filter(
        models.Module.Type_ID == model_id,
        models.Module.del_flag == False,
    ).all()


def get_device(db: Session, device_id: int):
    return db.query(models.Module).filter(
        models.Module.Module_ID == device_id,
        models.Module.del_flag == False,
    ).first()


def get_device_by_model_and_address(db: Session, model_id: int, address: int):
    return db.query(models.Module).filter(
        models.Module.Type_ID == model_id,
        models.Module.ModuleAddress == str(address),
        models.Module.del_flag == False,
    ).first()


def create_device(db: Session, data: schemas.DeviceCreate):
    existing = get_device_by_model_and_address(db, data.Model_ID, data.DeviceAddress)
    if existing:
        return None
    db_item = models.Module(
        Type_ID=data.Model_ID,
        ModuleAddress=str(data.DeviceAddress),
        Moduledescript=data.Devicedescript,
        Notes=data.Notes,
        creater_id=data.creater_id,
    )
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


def update_device(db: Session, device_id: int, data: schemas.DeviceUpdate):
    db_item = get_device(db, device_id)
    if not db_item:
        return None
    update_data = data.model_dump(exclude_unset=True)
    if "DeviceAddress" in update_data and "Model_ID" in update_data:
        existing = get_device_by_model_and_address(db, update_data["Model_ID"], update_data["DeviceAddress"])
        if existing and existing.Module_ID != device_id:
            return False
    elif "DeviceAddress" in update_data:
        existing = get_device_by_model_and_address(db, db_item.Type_ID, update_data["DeviceAddress"])
        if existing and existing.Module_ID != device_id:
            return False
    field_map = {
        "Model_ID": "Type_ID",
        "Devicedescript": "Moduledescript",
        "DeviceAddress": "ModuleAddress",
        "Notes": "Notes",
    }
    for field, value in update_data.items():
        setattr(db_item, field_map[field], str(value) if field == "DeviceAddress" else value)
    db.commit()
    db.refresh(db_item)
    return db_item


def delete_device(db: Session, device_id: int):
    db_item = get_device(db, device_id)
    if not db_item:
        return False
    db_item.del_flag = True
    db.commit()
    return True
