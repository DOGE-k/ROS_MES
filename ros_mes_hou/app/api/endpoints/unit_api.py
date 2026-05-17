from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.crud import unit as crud
from app.db.database import get_db
from app.schemas import unit as schemas

router = APIRouter()


@router.get("/")
def list_units(db: Session = Depends(get_db)):
    items = crud.get_units(db)
    return {"code": 200, "message": "获取机械臂列表成功", "data": items}


@router.get("/by_device/{device_id}")
def list_units_by_device(device_id: int, db: Session = Depends(get_db)):
    items = crud.get_units_by_device(db, device_id)
    return {"code": 200, "message": "获取机械臂列表成功", "data": items}


@router.get("/{unit_id}")
def get_unit(unit_id: int, db: Session = Depends(get_db)):
    item = crud.get_unit(db, unit_id)
    if not item:
        raise HTTPException(status_code=404, detail="机械臂不存在")
    return {"code": 200, "message": "获取机械臂成功", "data": item}


@router.post("/")
def create_unit(data: schemas.UnitCreate, db: Session = Depends(get_db)):
    db_item = crud.create_unit(db, data)
    if db_item is None:
        raise HTTPException(status_code=409, detail="该机械臂ID已被占用")
    return {"code": 200, "message": "新增机械臂成功", "data": db_item}


@router.put("/{unit_id}")
def update_unit(unit_id: int, data: schemas.UnitUpdate, db: Session = Depends(get_db)):
    db_item = crud.update_unit(db, unit_id, data)
    if not db_item:
        raise HTTPException(status_code=404, detail="机械臂不存在")
    return {"code": 200, "message": "更新机械臂成功", "data": db_item}


@router.delete("/{unit_id}")
def delete_unit(unit_id: int, db: Session = Depends(get_db)):
    success = crud.delete_unit(db, unit_id)
    if not success:
        raise HTTPException(status_code=404, detail="机械臂不存在")
    return {"code": 200, "message": "删除机械臂成功", "data": {"unit_id": unit_id}}
