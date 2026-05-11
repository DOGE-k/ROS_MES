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
app.mount("/api/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


def create_initial_user():
    db = SessionLocal()
    try:
        existing = db.query(models.User).filter(models.User.Username == "admin").first()
        if not existing:
            from app.core.security import get_password_hash

            admin_user = models.User(
                Username="admin",
                Password=get_password_hash("admin123"),
                Type_ID=1,
                Creator_ID=1,
            )
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)

            admin_user.Creator_ID = admin_user.User_ID
            db.commit()

            print("Initial admin user created (admin / admin123)")
        else:
            print("Admin user already exists")
    finally:
        db.close()


def migrate_drawing_table():
    """迁移 drawings 和 drawings_version 表到新规范"""
    import sqlalchemy as sa
    from sqlalchemy import inspect

    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    new_drawings_columns = {"Drawing_ID", "Drawingname", "Drawingdescripte", "Drawingfile",
                            "Creator_ID", "Createtime", "Modifytime", "NewVersion_ID",
                            "del_flag", "Notes"}
    new_versions_columns = {"DrawingsVersion_ID", "Drawing_ID", "Drawingfile", "Creator_ID",
                            "Createtime", "Modify_ID", "Modifytime", "del_flag", "Notes"}

    if "drawings" in existing_tables:
        columns = [col["name"] for col in inspector.get_columns("drawings")]
        existing_set = set(columns)
        if existing_set.issuperset(new_drawings_columns):
            pass
        else:
            print("Detected old drawings table schema, dropping and recreating...")
            models.Drawing.__table__.drop(engine)
            models.Drawing.__table__.create(engine)
            print("Drawings table recreated with new schema")

    if "drawings_version" in existing_tables:
        columns = [col["name"] for col in inspector.get_columns("drawings_version")]
        existing_set = set(columns)
        if existing_set.issuperset(new_versions_columns):
            pass
        else:
            print("Detected old drawings_version table schema, dropping and recreating...")
            models.DrawingVersion.__table__.drop(engine)
            models.DrawingVersion.__table__.create(engine)
            print("Drawings_version table recreated with new schema")


def migrate_user_schema():
    """迁移 users 表到新规范（兼容旧数据库文件）"""
    import sqlalchemy as sa
    from sqlalchemy import inspect

    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    if "users" not in existing_tables:
        return

    columns = [col["name"] for col in inspector.get_columns("users")]
    new_columns = {"User_ID", "Username", "Password", "Type_ID", "Creator_ID",
                   "Createtime", "Islock", "Locktime", "Name", "Headimage",
                   "Birthday", "Sex", "Modifytime", "del_flag", "Notes"}

    existing_column_names = set(columns)

    if existing_column_names.issuperset(new_columns):
        return

    print("Detected old users table schema, dropping and recreating...")
    models.User.__table__.drop(engine)
    models.User.__table__.create(engine)
    print("Users table recreated with new schema")


@app.on_event("startup")
def on_startup():
    models.Base.metadata.create_all(bind=engine)
    migrate_user_schema()
    create_initial_user()
    migrate_drawing_table()
