# app/main.py

import uvicorn
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import app.db.models  # noqa: F401
from app.api.endpoints import (
    login,
    hardware_web,
    control,
    coordination,
    drawing,
    finetuning,
    ws_stream,
    register,
    user,
    module,
    ros,
)
from app.db.database import Base, engine
from app.services.ros_service import start_ros_thread

Base.metadata.create_all(bind=engine)


def migrate_schema():
    """为已有数据库添加新字段（兼容旧数据库文件）"""
    import sqlalchemy as sa
    from sqlalchemy import inspect

    inspector = inspect(engine)
    columns = [col["name"] for col in inspector.get_columns("users")]

    with engine.connect() as conn:
        if "email" not in columns:
            conn.execute(sa.text("ALTER TABLE users ADD COLUMN email VARCHAR(100) DEFAULT ''"))
        if "phone" not in columns:
            conn.execute(sa.text("ALTER TABLE users ADD COLUMN phone VARCHAR(20) DEFAULT ''"))
        if "avatar" not in columns:
            conn.execute(sa.text("ALTER TABLE users ADD COLUMN avatar VARCHAR(500) DEFAULT ''"))
        if "status" not in columns:
            conn.execute(sa.text("ALTER TABLE users ADD COLUMN status INTEGER DEFAULT 0"))
        if "last_login" not in columns:
            conn.execute(sa.text("ALTER TABLE users ADD COLUMN last_login DATETIME"))

        conn.execute(sa.text("UPDATE users SET status = 0 WHERE status IS NULL"))
        conn.commit()


migrate_schema()

UPLOADS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")
os.makedirs(os.path.join(UPLOADS_DIR, "avatars"), exist_ok=True)

app = FastAPI(
    title="ROS MES Backend",
    description="FastAPI + SQLite + ROS 节点一体化机械臂 MES 系统",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/api/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")


@app.on_event("startup")
def startup_event():
    start_ros_thread()


@app.get("/")
def read_root():
    return {
        "code": 200,
        "message": "ros_mes_hou FastAPI + ROS 节点启动成功！",
    }


app.include_router(login.router, prefix="/api", tags=["认证模块"])
app.include_router(register.router, prefix="/api", tags=["注册模块"])
app.include_router(user.router, prefix="/api/user", tags=["用户模块"])

app.include_router(ros.router, prefix="/api", tags=["ROS 测试接口"])
app.include_router(hardware_web.router, prefix="/api/hardware", tags=["硬件管理模块"])
app.include_router(module.router, prefix="/api/module", tags=["模块管理模块"])
app.include_router(control.router, prefix="/api/control", tags=["设备底层控制模块"])
app.include_router(coordination.router, prefix="/api/coordination", tags=["坐标下发模块"])
app.include_router(drawing.router, prefix="/api/drawing", tags=["图纸管理模块"])
app.include_router(finetuning.router, prefix="/api/finetuning", tags=["微调记录模块"])
app.include_router(ws_stream.router, prefix="/api/ws", tags=["实时数据流推送"])


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8080,
        reload=False,
    )