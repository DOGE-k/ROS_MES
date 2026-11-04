from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.crud import sensors as crud
from app.db.database import get_db
from app.schemas import sensors as schemas

router = APIRouter()


@router.get("/")
def list_sensors(db: Session = Depends(get_db)):
    items = crud.get_sensors(db)
    return {"code": 200, "message": "获取传感器列表成功", "data": items}


@router.get("/by_unit/{unit_id}")
def list_sensors_by_unit(unit_id: int, db: Session = Depends(get_db)):
    items = crud.get_sensors_by_unit(db, unit_id)
    return {"code": 200, "message": "获取传感器列表成功", "data": items}


@router.get("/{sensor_id}")
def get_sensor(sensor_id: int, db: Session = Depends(get_db)):
    item = crud.get_sensor(db, sensor_id)
    if not item:
        raise HTTPException(status_code=404, detail="传感器不存在")
    return {"code": 200, "message": "获取传感器成功", "data": item}


@router.post("/")
def create_sensor(data: schemas.SensorCreate, db: Session = Depends(get_db)):
    try:
        db_item = crud.create_sensor(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if db_item is None:
        raise HTTPException(status_code=409, detail=f"该机械臂下已存在名称为「{data.sensordescript}」的传感器")
    return {"code": 200, "message": "新增传感器成功", "data": db_item}


@router.put("/{sensor_id}")
def update_sensor(sensor_id: int, data: schemas.SensorUpdate, db: Session = Depends(get_db)):
    try:
        db_item = crud.update_sensor(db, sensor_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if db_item is False:
        raise HTTPException(status_code=409, detail="目标机械臂下已存在该类型的传感器")
    if db_item is None:
        raise HTTPException(status_code=404, detail="传感器不存在")
    return {"code": 200, "message": "更新传感器成功", "data": db_item}


@router.delete("/{sensor_id}")
def delete_sensor(sensor_id: int, db: Session = Depends(get_db)):
    success = crud.delete_sensor(db, sensor_id)
    if not success:
        raise HTTPException(status_code=404, detail="传感器不存在")
    return {"code": 200, "message": "删除传感器成功", "data": {"sensor_id": sensor_id}}
