from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.crud import device as crud
from app.db.database import get_db
from app.schemas import device as schemas

router = APIRouter()


@router.get("/")
def list_devices(db: Session = Depends(get_db)):
    items = crud.get_devices(db)
    return {"code": 200, "message": "获取模块列表成功", "data": items}


@router.get("/by_model/{model_id}")
def list_devices_by_model(model_id: int, db: Session = Depends(get_db)):
    items = crud.get_devices_by_model(db, model_id)
    return {"code": 200, "message": "获取模块列表成功", "data": items}


@router.get("/{device_id}")
def get_device(device_id: int, db: Session = Depends(get_db)):
    item = crud.get_device(db, device_id)
    if not item:
        raise HTTPException(status_code=404, detail="模块不存在")
    return {"code": 200, "message": "获取模块成功", "data": item}


@router.post("/")
def create_device(data: schemas.DeviceCreate, db: Session = Depends(get_db)):
    db_item = crud.create_device(db, data)
    if db_item is None:
        x = (data.DeviceAddress >> 4) & 0x0F
        y = data.DeviceAddress & 0x0F
        raise HTTPException(status_code=409, detail=f"该型号下坐标({x},{y})的模块已存在")
    return {"code": 200, "message": "新增模块成功", "data": db_item}


@router.put("/{device_id}")
def update_device(device_id: int, data: schemas.DeviceUpdate, db: Session = Depends(get_db)):
    db_item = crud.update_device(db, device_id, data)
    if db_item is None:
        raise HTTPException(status_code=404, detail="模块不存在")
    if db_item is False:
        raise HTTPException(status_code=409, detail="该型号下已存在相同坐标的模块")
    return {"code": 200, "message": "更新模块成功", "data": db_item}


@router.delete("/{device_id}")
def delete_device(device_id: int, db: Session = Depends(get_db)):
    success = crud.delete_device(db, device_id)
    if not success:
        raise HTTPException(status_code=404, detail="模块不存在")
    return {"code": 200, "message": "删除模块成功", "data": {"device_id": device_id}}
