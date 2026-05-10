"""
模块入口
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.api import api_router
from app.core.config import settings
from app.db import models
from app.db.database import SessionLocal, engine

app = FastAPI(title=settings.PROJECT_NAME, openapi_url=f"{settings.API_STR}/openapi.json")

if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.API_STR)

UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


def create_initial_user():
    db = SessionLocal()
    try:
        existing = db.query(models.User).filter(models.User.username == "admin").first()
        if not existing:
            import hashlib

            sha = hashlib.sha256()
            sha.update("admin123".encode("utf-8"))
            hashed_password = sha.hexdigest()
            admin_user = models.User(username="admin", password=hashed_password, role="admin")
            db.add(admin_user)
            db.commit()
            print("Initial admin user created (admin / admin123)")
        else:
            print("Admin user already exists")
    finally:
        db.close()


def migrate_drawing_table():
    db = SessionLocal()
    try:
        import sqlalchemy as sa
        from sqlalchemy import inspect

        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()

        if "drawing" in existing_tables and "drawings" not in existing_tables:
            db.execute(sa.text("ALTER TABLE drawing RENAME TO drawings"))
            db.commit()
            print("Renamed 'drawing' table to 'drawings'")
            existing_tables = inspector.get_table_names()

        if "drawings" in existing_tables:
            columns = [col["name"] for col in inspector.get_columns("drawings")]

            rename_map = {
                "id": "drawing_id",
                "name": "drawing_name",
                "file_path": "drawing_file",
                "created_at": "create_time",
                "updated_at": "modify_time",
            }
            for old_name, new_name in rename_map.items():
                if old_name in columns and new_name not in columns:
                    db.execute(sa.text(f"ALTER TABLE drawings RENAME COLUMN {old_name} TO {new_name}"))
                    db.commit()
                    print(f"Renamed drawings.{old_name} to drawings.{new_name}")

            columns = [col["name"] for col in inspector.get_columns("drawings")]

            columns_to_add = [
                ("drawing_description", "TEXT"),
                ("creator_id", "INTEGER DEFAULT 1"),
                ("latest_version_id", "INTEGER"),
                ("del_flag", "BOOLEAN DEFAULT 0"),
                ("notes", "TEXT"),
            ]
            for col_name, col_type in columns_to_add:
                if col_name not in columns:
                    db.execute(sa.text(f"ALTER TABLE drawings ADD COLUMN {col_name} {col_type}"))
                    db.commit()
                    print(f"Added drawings.{col_name}")

            if "json_data" in columns:
                db.execute(sa.text("ALTER TABLE drawings DROP COLUMN json_data"))
                db.commit()
                print("Dropped drawings.json_data")

        if "drawings_version" in existing_tables:
            columns = [col["name"] for col in inspector.get_columns("drawings_version")]

            columns_to_add = [
                ("create_time", "DATETIME DEFAULT CURRENT_TIMESTAMP"),
                ("modify_id", "INTEGER"),
                ("modify_time", "DATETIME"),
                ("del_flag", "BOOLEAN DEFAULT 0"),
                ("notes", "TEXT"),
            ]
            for col_name, col_type in columns_to_add:
                if col_name not in columns:
                    db.execute(sa.text(f"ALTER TABLE drawings_version ADD COLUMN {col_name} {col_type}"))
                    db.commit()
                    print(f"Added drawings_version.{col_name}")

    finally:
        db.close()


def migrate_user_schema():
    """为 users 表添加新字段（兼容旧数据库文件）"""
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


@app.on_event("startup")
def on_startup():
    models.Base.metadata.create_all(bind=engine)
    create_initial_user()
    migrate_drawing_table()
    migrate_user_schema()
