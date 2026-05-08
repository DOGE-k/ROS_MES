# app/db/models.py
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
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
    type = Column(String(50))  # 硬件类型：如 sensor, motor, camera
    status = Column(String(20))  # 状态：如 online, offline, error
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
    adjusted_by = Column(String(50))  # 记录是谁调整的
    adjusted_at = Column(DateTime(timezone=True), server_default=func.now())


class FineTuningConfig(Base):
    """保存"机械臂姿态微调与压力监控"页面的一次配置快照。"""

    __tablename__ = "fine_tuning_config"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    module_id = Column(Integer, index=True, nullable=False)
    device_id = Column(Integer, index=True, nullable=False)
    config_json = Column(Text, nullable=False)
    saved_by = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Drawing(Base):
    """图纸管理 - 点云图与JSON数据"""

    __tablename__ = "drawings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(200), nullable=False, comment="图纸名称")
    file_path = Column(String(500), nullable=True, comment="上传文件存储路径")
    json_data = Column(Text, nullable=True, comment="JSON数据内容")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
