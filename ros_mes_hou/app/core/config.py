# app/core/config.py
import os
from typing import List

from dotenv import load_dotenv

load_dotenv()


class Settings:
    PROJECT_NAME: str = "ROS MES Backend"
    API_STR: str = os.getenv("API_STR", "/api")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./mes_database.db")
    BACKEND_CORS_ORIGINS: List[str] = [
        origin.strip()
        for origin in os.getenv("BACKEND_CORS_ORIGINS", "*").split(",")
        if origin.strip()
    ]


settings = Settings()
