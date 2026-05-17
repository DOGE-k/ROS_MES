from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.crud import device as dev_crud
from app.crud import model as crud
from app.crud import sensors as sensor_crud
from app.crud import unit as unit_crud
from app.db.database import get_db
from app.schemas import model as schemas

router = APIRouter()


@router.get("/")
def list_models(db: Session = Depends(get_db)):
    items = crud.get_models(db)
    return {"code": 200, "message": "获取型号列表成功", "data": items}


@router.get("/tree")
def get_device_tree(db: Session = Depends(get_db)):
    models = crud.get_models(db)
    tree = []
    for m in models:
        model_node = {
            "id": f"model-{m.Model_ID}",
            "label": m.Modelname,
            "type": "model",
            "raw_id": m.Model_ID,
            "children": [],
        }
        devices = dev_crud.get_devices_by_model(db, m.Model_ID)
        for d in devices:
            device_node = {
                "id": f"device-{d.Device_ID}",
                "label": f"模块({(d.DeviceAddress >> 4) & 0x0F},{d.DeviceAddress & 0x0F})",
                "type": "device",
                "raw_id": d.Device_ID,
                "children": [],
            }
            units = unit_crud.get_units_by_device(db, d.Device_ID)
            for u in units:
                unit_node = {
                    "id": f"unit-{u.id}",
                    "label": u.UnitDescript or f"机械臂{u.Unit_ID}",
                    "type": "unit",
                    "raw_id": u.id,
                    "arm_type": u.Unit_ID,
                    "device_id": d.Device_ID,
                    "children": [],
                }
                sensors = sensor_crud.get_sensors_by_unit(db, u.id)
                for s in sensors:
                    unit_node["children"].append({
                        "id": f"sensor-{s.id}",
                        "label": s.sensordescript or f"传感器{s.sensor_ID}",
                        "type": "sensor",
                        "raw_id": s.id,
                        "sensor_type": s.sensor_ID,
                        "device_id": s.Device_ID,
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
    return {"code": 200, "message": "获取型号成功", "data": item}


@router.post("/")
def create_model(data: schemas.ModelCreate, db: Session = Depends(get_db)):
    db_item = crud.create_model(db, data)
    return {"code": 200, "message": "新增型号成功", "data": db_item}


@router.put("/{model_id}")
def update_model(model_id: int, data: schemas.ModelUpdate, db: Session = Depends(get_db)):
    db_item = crud.update_model(db, model_id, data)
    if not db_item:
        raise HTTPException(status_code=404, detail="型号不存在")
    return {"code": 200, "message": "更新型号成功", "data": db_item}


@router.delete("/{model_id}")
def delete_model(model_id: int, db: Session = Depends(get_db)):
    success = crud.delete_model(db, model_id)
    if not success:
        raise HTTPException(status_code=404, detail="型号不存在")
    return {"code": 200, "message": "删除型号成功", "data": {"model_id": model_id}}
