# app/api/endpoints/finetuning.py

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.crud import finetuning as crud
from app.db.database import get_db
from app.schemas import finetuning as schemas
from app.services.ros_service import RosDispatchError, publish_ros_command

router = APIRouter()


@router.post("/", response_model=schemas.FineTuningApiResponse)
def create_record(
    record: schemas.FineTuningCreate,
    db: Session = Depends(get_db),
):
    """
    单轴微调：
    1. 记录 SQLite
    2. 发布 ROS topic
    3. 返回前端需要的 data 数组
    """
    username = "web_frontend"

    db_record = crud.create_fine_tuning_record(
        db=db,
        record=record,
        username=username,
    )

    device_id = record.device_id or db_record.hardware_id
    position = record.position if record.position is not None else db_record.new_value

    dispatch_payload = {
        "module_id": record.module_id,
        "device_id": int(device_id),
        "position": float(position),
        "operator": username,
        "record_id": db_record.id,
    }

    try:
        dispatch_result = publish_ros_command("fine_tuning", dispatch_payload)
    except RosDispatchError as exc:
        raise HTTPException(status_code=503, detail=f"ROS 下发失败：{exc}") from exc

    return {
        "code": 200,
        "message": "微调成功",
        "data": [
            {
                "device_id": int(device_id),
                "position": float(position),
                "type": "axis",
            },
            {
                "device_id": -1,
                "position": 0.0,
                "type": "pressure",
            },
        ],
        "dispatch": dispatch_result,
    }


@router.get("/", response_model=List[schemas.FineTuningResponse])
def read_records(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """
    获取微调记录列表。
    """
    return crud.get_fine_tuning_records(db, skip=skip, limit=limit)


@router.post("/config")
def save_config(
    config: schemas.FineTuningConfigCreate,
    db: Session = Depends(get_db),
):
    """
    保存机械臂当前配置快照：
    1. 存 SQLite
    2. 通知 ROS
    """
    username = "web_frontend"

    db_config = crud.save_fine_tuning_config(
        db=db,
        config=config,
        username=username,
    )

    dispatch_payload = {
        "config_id": db_config.id,
        "module_id": config.module_id,
        "device_id": config.device_id,
        "config": config.model_dump(),
        "operator": username,
    }

    try:
        dispatch_result = publish_ros_command(
            "save_fine_tuning_config",
            dispatch_payload,
        )
    except RosDispatchError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"ROS 配置保存通知失败：{exc}",
        ) from exc

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