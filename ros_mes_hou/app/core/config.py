# app/core/config.py
import os
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

class Settings:
    PROJECT_NAME: str = "ROS MES Backend"
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./mes_database.db")

settings = Settings()