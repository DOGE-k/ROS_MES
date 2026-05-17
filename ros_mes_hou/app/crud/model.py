from sqlalchemy.orm import Session

from app.db import models
from app.schemas import model as schemas


def get_models(db: Session):
    return db.query(models.ModelTooling).filter(models.ModelTooling.del_flag == False).all()


def get_model(db: Session, model_id: int):
    return db.query(models.ModelTooling).filter(
        models.ModelTooling.Model_ID == model_id,
        models.ModelTooling.del_flag == False,
    ).first()


def create_model(db: Session, data: schemas.ModelCreate):
    db_item = models.ModelTooling(**data.model_dump())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


def update_model(db: Session, model_id: int, data: schemas.ModelUpdate):
    db_item = get_model(db, model_id)
    if not db_item:
        return None
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_item, field, value)
    db.commit()
    db.refresh(db_item)
    return db_item


def delete_model(db: Session, model_id: int):
    db_item = get_model(db, model_id)
    if not db_item:
        return False
    db_item.del_flag = True
    db.commit()
    return True
