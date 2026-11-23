"""
模块入口
"""
import logging
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from app.core.logging_setup import describe_logging, ensure_utf8_streams, setup_logging

# Windows 控制台默认 GBK，直接输出中文日志里的表情会 UnicodeEncodeError；
# 统一按 UTF-8 输出，无法编码的字符替换掉，保证业务日志总能打出来。
ensure_utf8_streams()
# 统一日志入口：控制台 + logs/backend.log（滚动），带 req=<id> 关联 ID。
# 必须在其它 app 模块导入前配置，避免导入期日志被丢掉。
setup_logging()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.api import api_router
from app.core.config import settings
from app.core.request_log import RequestLogMiddleware
from app.db import models
from app.db.database import engine
from app.db.schema import ensure_schema
from app.ros import get_ros_dispatcher
from app.ros.finetuning_batch import batch_manager
from app.ros.runtime_settings import runtime_settings

app = FastAPI(title=settings.PROJECT_NAME, openapi_url=f"{settings.API_STR}/openapi.json")
logger = logging.getLogger(__name__)

# 请求级日志：一次动作一行（轮询降级、写操作 INFO、慢请求 WARNING、5xx ERROR），
# 并回写 X-Request-ID，便于把 HTTP 请求与批次/ROS 日志串起来
app.add_middleware(RequestLogMiddleware)

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
    dispatcher = get_ros_dispatcher()
    dispatcher.start_native_node()
    # 启动横幅：测试时先确认"这次跑的是哪套配置"，避免拿旧进程的日志判断新代码
    logger.info(
        "后端启动 | pid=%s | ROS_VERSION=%s | 执行模式=%s | 连接 revision=%s | 数据库=%s | %s",
        os.getpid(), os.getenv("ROS_VERSION", "1"),
        getattr(dispatcher, "emergency_mode", "unknown"),
        getattr(dispatcher, "revision", "?"),
        settings.DATABASE_URL, describe_logging(),
    )


@app.on_event("shutdown")
def on_shutdown():
    # 结束后台 ROS 连接（ROS1 的 rospy 线程为 daemon 随进程退出；ROS2 订阅线程由此停止）
    logger.info("后端停止 | pid=%s", os.getpid())
    get_ros_dispatcher().stop()
