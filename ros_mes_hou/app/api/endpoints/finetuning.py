# app/api/endpoints/finetuning.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.api.deps import get_current_user
from app.crud import finetuning as crud
from app.db import models
from app.db.database import get_db
from app.schemas import finetuning as schemas
from app.services.ros_dispatcher import RosDispatchError, ros_dispatcher

router = APIRouter()


@router.post("/", response_model=schemas.FineTuningApiResponse)
def create_record(
    record: schemas.FineTuningCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """单轴微调：记录数据库 + 下发 ROS + 返回前端需要的统一格式。"""

    db_record = crud.create_fine_tuning_record(
        db=db,
        record=record,
        username=current_user.username,
    )

    device_id = record.device_id or db_record.hardware_id
    position = record.position if record.position is not None else db_record.new_value

    payload = {
        "module_id": record.module_id,
        "device_id": device_id,
        "position": position,
        "operator": current_user.username,
        "record_id": db_record.id,
    }

    try:
        dispatch_result = ros_dispatcher.dispatch("fine_tuning", payload)
    except RosDispatchError as exc:
        raise HTTPException(status_code=502, detail=f"ROS 下发失败：{exc}") from exc

    # 前端当前逻辑要求 res.data 是数组：
    # - 匹配 device_id 的项更新当前轴位置；
    # - 其他项更新压力传感器显示。
    # 压力值后续可从真实 ROS 反馈替换，这里先保证接口闭环。
    return {
        "code": 200,
        "message": "微调成功",
        "data": [
            {"device_id": int(device_id), "position": float(position), "type": "axis"},
            {"device_id": -1, "position": 0.0, "type": "pressure"},
        ],
        "dispatch": dispatch_result,
    }


@router.get("/", response_model=List[schemas.FineTuningResponse])
def read_records(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """获取微调记录列表。"""
    return crud.get_fine_tuning_records(db, skip=skip, limit=limit)


@router.post("/config")
def save_config(
    config: schemas.FineTuningConfigCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """保存机械臂当前配置快照。"""

    db_config = crud.save_fine_tuning_config(
        db=db,
        config=config,
        username=current_user.username,
    )

    payload = {
        "config_id": db_config.id,
        "module_id": config.module_id,
        "device_id": config.device_id,
        "config": config.model_dump(),
        "operator": current_user.username,
    }

    try:
        dispatch_result = ros_dispatcher.dispatch("save_fine_tuning_config", payload)
    except RosDispatchError as exc:
        raise HTTPException(status_code=502, detail=f"ROS 配置保存通知失败：{exc}") from exc

    return {
        "code": 200,
        "message": "配置保存成功",
        "data": {
            "id": db_config.id,
            "module_id": db_config.module_id,
            "device_id": db_config.device_id,
            "config": crud.parse_config(db_config),
            "saved_by": db_config.saved_by,
            "created_at": str(db_config.created_at),
        },
        "dispatch": dispatch_result,
    }
