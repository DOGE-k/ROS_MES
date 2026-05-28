from sqlalchemy.orm import Session

from app.db import models
from app.schemas import unit as schemas


def get_units(db: Session):
    return db.query(models.Unit).filter(models.Unit.del_flag == False).all()


def get_units_by_device(db: Session, device_id: int):
    return db.query(models.Unit).filter(
        models.Unit.Module_ID == device_id,
        models.Unit.del_flag == False,
    ).all()


def get_unit(db: Session, unit_id: int):
    return db.query(models.Unit).filter(
        models.Unit.id == unit_id,
        models.Unit.del_flag == False,
    ).first()


def get_unit_by_module_and_arm_id(db: Session, module_id: int, arm_id: int):
    return db.query(models.Unit).filter(
        models.Unit.Module_ID == module_id,
        models.Unit.Unit_ID == arm_id,
        models.Unit.del_flag == False,
    ).first()


def create_unit(db: Session, data: schemas.UnitCreate):
    existing = get_unit_by_module_and_arm_id(db, data.Module_ID, data.Unit_ID)
    if existing:
        return None
    db_item = models.Unit(**data.model_dump(exclude={"Device_ID"}))
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


def update_unit(db: Session, unit_id: int, data: schemas.UnitUpdate):
    db_item = get_unit(db, unit_id)
    if not db_item:
        return None
    update_data = data.model_dump(exclude_unset=True)
    update_data.pop("Device_ID", None)
    if "Unit_ID" in update_data:
        existing = get_unit_by_module_and_arm_id(db, db_item.Module_ID, update_data["Unit_ID"])
        if existing and existing.id != unit_id:
            return False
    if "Module_ID" in update_data:
        existing = get_unit_by_module_and_arm_id(
            db,
            update_data["Module_ID"],
            update_data.get("Unit_ID", db_item.Unit_ID),
        )
        if existing and existing.id != unit_id:
            return False
    for field, value in update_data.items():
        setattr(db_item, field, value)
    db.commit()
    db.refresh(db_item)
    return db_item


def delete_unit(db: Session, unit_id: int):
    db_item = get_unit(db, unit_id)
    if not db_item:
        return False
    db_item.del_flag = True
    db.commit()
    return True
