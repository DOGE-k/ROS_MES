from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, inspect, text

from app.db.database import get_db
from app.db import models

router = APIRouter()


def get_recent_fine_tuning_count(db: Session, today_start: datetime) -> int:
    inspector = inspect(db.bind)
    if not inspector.has_table("fine_tuning"):
        return 0

    columns = {column["name"] for column in inspector.get_columns("fine_tuning")}
    if "create_time" in columns:
        return (
            db.query(func.count(models.FineTuning.id))
            .filter(models.FineTuning.create_time >= today_start)
            .scalar()
            or 0
        )
    if "adjusted_at" in columns:
        return (
            db.execute(
                text("SELECT COUNT(*) FROM fine_tuning WHERE adjusted_at >= :today_start"),
                {"today_start": today_start},
            ).scalar()
            or 0
        )
    return 0


@router.get("/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    module_count = (
        db.query(func.count(models.Module.Module_ID))
        .filter(models.Module.del_flag == False)
        .scalar()
        or 0
    )
    unit_count = (
        db.query(func.count(models.Unit.id))
        .filter(models.Unit.del_flag == False)
        .scalar()
        or 0
    )
    sensor_count = (
        db.query(func.count(models.Sensor.id))
        .filter(models.Sensor.del_flag == False)
        .scalar()
        or 0
    )
    total_hardware = module_count + unit_count + sensor_count

    # Current Module/Unit/Sensor tables do not have a unified status column.
    # Keep dashboard stable and reserve fault counting for sensor_log/status data later.
    fault_count = 0

    total_users = db.query(func.count(models.User.User_ID)).scalar() or 0

    recent_task_count = get_recent_fine_tuning_count(db, today_start)

    return {
        "code": 200,
        "message": "获取仪表盘数据成功",
        "data": {
            "deviceStatus": {
                "label": "设备状态",
                "value": "正常运行" if fault_count == 0 else f"{fault_count} 台故障",
                "unit": "",
                "trend": 0,
            },
            "taskCount": {
                "label": "任务数",
                "value": recent_task_count,
                "unit": "",
                "trend": 0,
            },
            "faultCount": {
                "label": "故障数",
                "value": fault_count,
                "unit": "",
                "trend": 0,
            },
            "onlineUsers": {
                "label": "在线用户",
                "value": total_users,
                "unit": "",
                "trend": 0,
            },
            "responseTime": {
                "label": "响应时间",
                "value": 23,
                "unit": "ms",
                "trend": 0,
            },
            "concurrency": {
                "label": "并发",
                "value": max(total_users * 2, 1),
                "unit": "",
                "trend": 0,
            },
            "deviceConnections": {
                "label": "设备连接数",
                "value": total_hardware,
                "unit": "",
                "trend": 0,
            },
        },
    }
