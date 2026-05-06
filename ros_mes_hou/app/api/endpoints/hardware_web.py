# app/api/endpoints/hardware_web.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List

from app.api.deps import get_current_user
from app.crud import hardware as crud
from app.db import models
from app.db.database import get_db
from app.schemas import hardware as schemas

router = APIRouter()


@router.get("/", response_model=List[schemas.HardwareResponse])
def read_hardware_list(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """获取硬件列表。"""
    return crud.get_all_hardware(db)


@router.get("/select", response_model=List[schemas.HardwareResponse])
def select_hardware(
    keyword: str = Query("", description="按名称、IP、描述模糊搜索"),
    status: str = Query("", description="按状态筛选"),
    type: str = Query("", description="按设备类型筛选"),  # noqa: A002 - 保持和前端字段一致
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """硬件查询/筛选接口，对应前端原本缺失的 /hardware/select。"""
    return crud.search_hardware(db, keyword=keyword, status=status, type_=type)


@router.post("/", response_model=schemas.HardwareResponse)
def create_new_hardware(
    hardware: schemas.HardwareCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return crud.create_hardware(db=db, hardware=hardware)


@router.put("/{hardware_id}", response_model=schemas.HardwareResponse)
def update_hardware(
    hardware_id: int,
    hardware: schemas.HardwareUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    db_hardware = crud.update_hardware(db=db, hardware_id=hardware_id, hardware=hardware)
    if not db_hardware:
        raise HTTPException(status_code=404, detail="硬件不存在")
    return db_hardware


@router.patch("/{hardware_id}", response_model=schemas.HardwareResponse)
def patch_hardware(
    hardware_id: int,
    hardware: schemas.HardwareUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    db_hardware = crud.update_hardware(db=db, hardware_id=hardware_id, hardware=hardware)
    if not db_hardware:
        raise HTTPException(status_code=404, detail="硬件不存在")
    return db_hardware


@router.delete("/{hardware_id}")
def delete_hardware(
    hardware_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    hardware = db.query(models.Hardware).filter(models.Hardware.id == hardware_id).first()

    if not hardware:
        raise HTTPException(status_code=404, detail="硬件不存在")

    db.delete(hardware)
    db.commit()

    return {
        "code": 200,
        "message": "删除成功",
        "data": {"id": hardware_id},
    }
