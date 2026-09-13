"""
模块入口
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.api import api_router
from app.core.config import settings
from app.db import models
from app.db.database import engine
from app.services.ros_service import start_ros_thread

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
    start_ros_thread()
