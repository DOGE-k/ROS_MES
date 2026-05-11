from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.database import get_db
from app.db import models

router = APIRouter()


@router.get("/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    total_hardware = db.query(func.count(models.Hardware.id)).scalar() or 0

    online_hardware = (
        db.query(func.count(models.Hardware.id))
        .filter(models.Hardware.status == "normal")
        .scalar()
        or 0
    )

    fault_count = (
        db.query(func.count(models.Hardware.id))
        .filter(models.Hardware.status == "fault")
        .scalar()
        or 0
    )

    total_users = db.query(func.count(models.User.User_ID)).scalar() or 0

    recent_task_count = (
        db.query(func.count(models.FineTuning.id))
        .filter(models.FineTuning.adjusted_at >= today_start)
        .scalar()
        or 0
    )

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
