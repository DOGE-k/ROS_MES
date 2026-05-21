# app/core/config.py
import os
from typing import List

from dotenv import load_dotenv

load_dotenv()


class Settings:
    PROJECT_NAME: str = "ROS MES Backend"
    API_STR: str = os.getenv("API_STR", "/api")
    # 数据库文件位于项目根目录（ros_mes_hou 的上一级）
    # __file__ = app/core/config.py
    # 需要向上 4 级: app/core/config.py -> app/core -> app -> ros_mes_hou -> ROS_MES (项目根目录)
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'ros_database.db')}")
    BACKEND_CORS_ORIGINS: List[str] = [
        origin.strip()
        for origin in os.getenv("BACKEND_CORS_ORIGINS", "*").split(",")
        if origin.strip()
    ]


settings = Settings()
