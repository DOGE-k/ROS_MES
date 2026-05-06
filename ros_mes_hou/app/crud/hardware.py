# app/crud/hardware.py
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db import models
from app.schemas import hardware as schemas


def get_all_hardware(db: Session):
    return db.query(models.Hardware).order_by(models.Hardware.id.desc()).all()


def search_hardware(db: Session, keyword: str = "", status: str = "", type_: str = ""):
    query = db.query(models.Hardware)

    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            or_(
                models.Hardware.name.like(like),
                models.Hardware.ip_address.like(like),
                models.Hardware.description.like(like),
            )
        )
    if status:
        query = query.filter(models.Hardware.status == status)
    if type_:
        query = query.filter(models.Hardware.type == type_)

    return query.order_by(models.Hardware.id.desc()).all()


def create_hardware(db: Session, hardware: schemas.HardwareCreate):
    db_hardware = models.Hardware(**hardware.model_dump())
    db.add(db_hardware)
    db.commit()
    db.refresh(db_hardware)
    return db_hardware


def update_hardware(db: Session, hardware_id: int, hardware: schemas.HardwareUpdate):
    db_hardware = db.query(models.Hardware).filter(models.Hardware.id == hardware_id).first()
    if not db_hardware:
        return None

    update_data = hardware.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_hardware, field, value)

    db.commit()
    db.refresh(db_hardware)
    return db_hardware
