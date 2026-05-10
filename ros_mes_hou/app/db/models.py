# app/db/models.py
from sqlalchemy import Boolean, Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.sql import func

from app.db.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password = Column(String(255), nullable=False)
    role = Column(String(20), default="operator")
    email = Column(String(100), default="")
    phone = Column(String(20), default="")
    avatar = Column(String(500), default="")
    status = Column(Integer, default=0)
    last_login = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Hardware(Base):
    __tablename__ = "hardware"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), index=True, nullable=False)
    type = Column(String(50))
    status = Column(String(20))
    ip_address = Column(String(50))
    description = Column(String(255))
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class FineTuning(Base):
    __tablename__ = "fine_tuning"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    hardware_id = Column(Integer, ForeignKey("hardware.id"))
    parameter_name = Column(String(100), nullable=False)
    old_value = Column(Float)
    new_value = Column(Float, nullable=False)
    adjusted_by = Column(String(50))
    adjusted_at = Column(DateTime(timezone=True), server_default=func.now())


class FineTuningConfig(Base):
    __tablename__ = "fine_tuning_config"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    module_id = Column(Integer, index=True, nullable=False)
    device_id = Column(Integer, index=True, nullable=False)
    config_json = Column(Text, nullable=False)
    saved_by = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Drawing(Base):
    __tablename__ = "drawings"

    drawing_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    drawing_name = Column(String(200), nullable=False)
    drawing_description = Column(Text, nullable=True)
    drawing_file = Column(String(500), nullable=False)
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    create_time = Column(DateTime(timezone=True), server_default=func.now())
    modify_time = Column(DateTime(timezone=True), nullable=True)
    latest_version_id = Column(Integer, ForeignKey("drawings_version.version_id"), nullable=True)
    del_flag = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)


class DrawingVersion(Base):
    __tablename__ = "drawings_version"

    version_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    drawing_id = Column(Integer, ForeignKey("drawings.drawing_id"), nullable=False)
    drawing_file = Column(String(500), nullable=False)
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    create_time = Column(DateTime(timezone=True), server_default=func.now())
    modify_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    modify_time = Column(DateTime(timezone=True), nullable=True)
    del_flag = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)
