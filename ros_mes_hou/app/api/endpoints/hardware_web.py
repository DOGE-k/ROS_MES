# app/api/endpoints/hardware_web.py

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.crud import hardware as crud
from app.db import models
from app.db.database import get_db
from app.schemas import hardware as schemas

router = APIRouter()


def format_hardware(item: models.Hardware):
    return {
        "id": item.id,
        "device_id": item.id,
        "hardware_id": item.id,
        "name": item.name,
        "hardware_name": item.name,
        "type": item.type,
        "hardware_type": item.type,
        "status": item.status,
        "ip_address": item.ip_address,
        "description": item.description,
        "specification": item.description,
        "updated_at": str(item.updated_at) if item.updated_at else "",
        "create_time": str(item.updated_at) if item.updated_at else "",
    }


@router.get("/")
def read_hardware_list(db: Session = Depends(get_db)):
    hardware_list = crud.get_all_hardware(db)

    return {
        "code": 200,
        "message": "获取硬件列表成功",
        "data": [format_hardware(item) for item in hardware_list],
    }


@router.get("/select")
def select_hardware(
    keyword: str = Query("", description="按名称、IP、描述模糊搜索"),
    status: str = Query("", description="按状态筛选"),
    type: str = Query("", description="按设备类型筛选"),  # noqa: A002
    db: Session = Depends(get_db),
):
    hardware_list = crud.search_hardware(
        db,
        keyword=keyword,
        status=status,
        type_=type,
    )

    return {
        "code": 200,
        "message": "查询硬件成功",
        "data": [format_hardware(item) for item in hardware_list],
    }


@router.post("/")
def create_new_hardware(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    name = payload.get("name") or payload.get("hardware_name")
    hardware_type = payload.get("type") or payload.get("hardware_type")
    status = payload.get("status", "normal")
    ip_address = payload.get("ip_address", "")
    description = payload.get("description") or payload.get("specification") or ""

    if not name:
        raise HTTPException(status_code=422, detail="缺少硬件名称")

    hardware = schemas.HardwareCreate(
        name=name,
        type=hardware_type,
        status=status,
        ip_address=ip_address,
        description=description,
    )

    db_hardware = crud.create_hardware(db=db, hardware=hardware)

    return {
        "code": 200,
        "message": "新增硬件成功",
        "data": format_hardware(db_hardware),
    }


@router.put("/{hardware_id}")
def update_hardware(
    hardware_id: int,
    hardware: schemas.HardwareUpdate,
    db: Session = Depends(get_db),
):
    db_hardware = crud.update_hardware(
        db=db,
        hardware_id=hardware_id,
        hardware=hardware,
    )

    if not db_hardware:
        raise HTTPException(status_code=404, detail="硬件不存在")

    return {
        "code": 200,
        "message": "更新硬件成功",
        "data": format_hardware(db_hardware),
    }


@router.patch("/{hardware_id}")
def patch_hardware(
    hardware_id: int,
    hardware: schemas.HardwareUpdate,
    db: Session = Depends(get_db),
):
    db_hardware = crud.update_hardware(
        db=db,
        hardware_id=hardware_id,
        hardware=hardware,
    )

    if not db_hardware:
        raise HTTPException(status_code=404, detail="硬件不存在")

    return {
        "code": 200,
        "message": "更新硬件成功",
        "data": format_hardware(db_hardware),
    }


@router.delete("/{hardware_id}")
def delete_hardware(
    hardware_id: int,
    db: Session = Depends(get_db),
):
    hardware = db.query(models.Hardware).filter(models.Hardware.id == hardware_id).first()

    if not hardware:
        raise HTTPException(status_code=404, detail="硬件不存在")

    db.delete(hardware)
    db.commit()

    return {
        "code": 200,
        "message": "删除成功",
        "data": {
            "id": hardware_id,
        },
    }