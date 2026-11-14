"""
模块入口
"""
import logging
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# Windows 控制台默认 GBK，直接输出中文日志里的表情会 UnicodeEncodeError；
# 统一按 UTF-8 输出，无法编码的字符替换掉，保证业务日志总能打出来。
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

# uvicorn 只配置自己的 logger；业务代码走 root，必须显式给 INFO 级别的输出
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-5s [%(name)s] %(message)s", datefmt="%H:%M:%S")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.api import api_router
from app.core.config import settings
from app.db import models
from app.db.database import engine
from app.db.schema import ensure_schema
from app.ros import get_ros_dispatcher
from app.ros.finetuning_batch import batch_manager
from app.ros.runtime_settings import runtime_settings

app = FastAPI(title=settings.PROJECT_NAME, openapi_url=f"{settings.API_STR}/openapi.json")

if settings.BACKEND_CORS_ORIGINS:
    cors_origins = [str(origin) for origin in settings.BACKEND_CORS_ORIGINS]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        # 安全修复：按 CORS 规范，allow_origins 为 "*" 时不能同时携带凭据；
        # 本系统使用 Authorization 头而非 Cookie，credentials 关闭不影响现有功能。
        # 如需限定来源，请在 .env 中设置 BACKEND_CORS_ORIGINS=http://<前端地址>:5173
        allow_credentials="*" not in cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.API_STR)

UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/api/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


@app.on_event("startup")
def on_startup():
    models.Base.metadata.create_all(bind=engine)
    # create_all 不会修改已存在表的列；fine_tuning 的新列与可空约束在此补齐
    ensure_schema(engine)
    runtime_settings.load()
    batch_manager.recover()
    # ROS1 适配器启动 rospy 原生节点线程；ROS2 适配器启动 /robot_status 后台订阅
    get_ros_dispatcher().start_native_node()


@app.on_event("shutdown")
def on_shutdown():
    # 结束后台 ROS 连接（ROS1 的 rospy 线程为 daemon 随进程退出；ROS2 订阅线程由此停止）
    get_ros_dispatcher().stop()
