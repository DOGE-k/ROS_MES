from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.crud import model as crud
from app.crud import sensors as sensor_crud
from app.crud import unit as unit_crud
from app.db import models as db_models
from app.db.database import get_db
from app.schemas import model as schemas

router = APIRouter()


def serialize_model(type_item):
    return {
        "Model_ID": type_item.Type_ID,
        "Modelname": type_item.Typename,
        "Modeldescripte": type_item.Typedescripte,
        "creater_id": type_item.creater_id,
        "Createtime": type_item.Createtime,
        "del_flag": type_item.del_flag,
        "Notes": type_item.Notes,
        "Type_ID": type_item.Type_ID,
        "Typename": type_item.Typename,
        "Typedescripte": type_item.Typedescripte,
    }


@router.get("/")
def list_models(db: Session = Depends(get_db)):
    items = crud.get_models(db)
    return {"code": 200, "message": "获取型号列表成功", "data": [serialize_model(item) for item in items]}


@router.get("/tree")
def get_device_tree(db: Session = Depends(get_db)):
    types = db.query(db_models.Type).filter(db_models.Type.del_flag == False).all()
    tree = []
    for type_item in types:
        model_node = {
            "id": f"model-{type_item.Type_ID}",
            "label": type_item.Typename,
            "type": "model",
            "raw_id": type_item.Type_ID,
            "children": [],
        }
        modules = db.query(db_models.Module).filter(
            db_models.Module.Type_ID == type_item.Type_ID,
            db_models.Module.del_flag == False,
        ).all()
        for module in modules:
            device_node = {
                "id": f"device-{module.Module_ID}",
                "label": module.Moduledescript or f"模块{module.Module_ID}",
                "type": "device",
                "raw_id": module.Module_ID,
                "module_id": module.Module_ID,
                "children": [],
            }
            units = unit_crud.get_units_by_device(db, module.Module_ID)
            for unit in units:
                unit_node = {
                    "id": f"unit-{unit.id}",
                    "label": unit.UnitDescript or f"机械臂{unit.Unit_ID}",
                    "type": "unit",
                    "raw_id": unit.id,
                    "arm_type": unit.Unit_ID,
                    "module_id": unit.Module_ID,
                    "device_id": module.Module_ID,
                    "children": [],
                }
                sensors = sensor_crud.get_sensors_by_unit(db, unit.id)
                for sensor in sensors:
                    unit_node["children"].append({
                        "id": f"sensor-{sensor.id}",
                        "label": sensor.sensordescript or f"传感器{sensor.sensor_ID}",
                        "type": "sensor",
                        "raw_id": sensor.id,
                        "sensor_type": sensor.sensor_ID,
                        "module_id": sensor.Module_ID,
                        "device_id": sensor.Module_ID,
                    })
                device_node["children"].append(unit_node)
            model_node["children"].append(device_node)
        tree.append(model_node)
    return {"code": 200, "message": "获取设备树成功", "data": tree}


@router.get("/{model_id}")
def get_model(model_id: int, db: Session = Depends(get_db)):
    item = crud.get_model(db, model_id)
    if not item:
        raise HTTPException(status_code=404, detail="型号不存在")
    return {"code": 200, "message": "获取型号成功", "data": serialize_model(item)}


@router.post("/")
def create_model(data: schemas.ModelCreate, db: Session = Depends(get_db)):
    db_item = crud.create_model(db, data)
    return {"code": 200, "message": "新增型号成功", "data": serialize_model(db_item)}


@router.put("/{model_id}")
def update_model(model_id: int, data: schemas.ModelUpdate, db: Session = Depends(get_db)):
    db_item = crud.update_model(db, model_id, data)
    if not db_item:
        raise HTTPException(status_code=404, detail="型号不存在")
    return {"code": 200, "message": "更新型号成功", "data": serialize_model(db_item)}


@router.delete("/{model_id}")
def delete_model(model_id: int, db: Session = Depends(get_db)):
    success = crud.delete_model(db, model_id)
    if not success:
        raise HTTPException(status_code=404, detail="型号不存在")
    return {"code": 200, "message": "删除型号成功", "data": {"model_id": model_id}}
