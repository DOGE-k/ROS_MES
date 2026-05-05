# app/api/endpoints/hardware.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.db.database import get_db
from app.db import models
from app.schemas import hardware as schemas
from app.crud import hardware as crud
from app.api.deps import get_current_user

router = APIRouter()

# 获取硬件列表接口 (GET 请求)
@router.get("/", response_model=List[schemas.HardwareResponse])
def read_hardware_list(
    db: Session = Depends(get_db),
    # 注入认证依赖，如果不通过认证，此函数不会被执行
    current_user: models.User = Depends(get_current_user) 
):
    """
    受保护的接口：必须在请求头中携带有效的 JWT。
    Header 格式：Authorization: Bearer <your_token>
    """
    # 此时可以访问 current_user 对象获取当前调用者的信息
    hardware_list = crud.get_all_hardware(db)
    return hardware_list

# 新增硬件接口 (POST 请求)
@router.post("/", response_model=schemas.HardwareResponse)
def create_new_hardware(hardware: schemas.HardwareCreate, db: Session = Depends(get_db)):
    return crud.create_hardware(db=db, hardware=hardware)

#删除硬件接口
@router.delete("/{hardware_id}")
def delete_hardware(
    hardware_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
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
            "id": hardware_id
        }
    }