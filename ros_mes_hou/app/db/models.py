# app/db/models.py
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.sql import func

from app.db.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password = Column(String(255), nullable=False)  # 建议存储加密后的密码
    role = Column(String(20), default="operator")  # 用户角色，例如：admin, operator
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
    """保存“机械臂姿态微调与压力监控”页面的一次配置快照。"""

    __tablename__ = "fine_tuning_config"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    module_id = Column(Integer, index=True, nullable=False)
    device_id = Column(Integer, index=True, nullable=False)
    config_json = Column(Text, nullable=False)
    saved_by = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
