"""当前服务的连接配置。地址变更不触发运动，不修改 ROS 消息。"""
from __future__ import annotations

import os
from contextlib import contextmanager
from threading import RLock
from typing import Literal
from urllib.parse import urlsplit

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from app.core.config import settings
from app.db import models
from app.db.database import SessionLocal


class ConnectionSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ros_mode: Literal["real", "mock"] = "real"
    drawing_mode: Literal["skip", "real", "mock"] = "real"
    emergency_mode: Literal["real", "mock"] = "real"
    ros_url: str = settings.ROSBRIDGE_URL
    drawing_ros_url: str = ""
    emergency_ros_url: str = ""
    pointcloud_url: str = os.getenv("POINTCLOUD_VIEW_BASE_URL", "http://localhost:5000")

    @model_validator(mode="after")
    def validate_connections(self):
        if (self.ros_mode == "real" or self.drawing_mode == "real") and self.emergency_mode != "real":
            raise ValueError("真实微调或图纸下发必须使用真实急停")
        for field in ("ros_url", "drawing_ros_url", "emergency_ros_url", "pointcloud_url"):
            value = getattr(self, field).strip().rstrip("/")
            setattr(self, field, value)
            if not value and field in {"drawing_ros_url", "emergency_ros_url"}:
                continue
            try:
                parsed = urlsplit(value)
                port = parsed.port
                if (parsed.scheme not in (("http", "https") if field == "pointcloud_url" else ("ws", "wss"))
                    or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment
                    or (port is not None and not 1 <= port <= 65535)):
                    raise ValueError()
            except ValueError:
                raise ValueError(f"{field} 地址格式不正确；ROS 使用 ws:// 或 wss://，三视图使用 http:// 或 https://")
        return self


class SettingsChange(BaseModel):
    expected_revision: int
    changes: dict


class RuntimeSettings:
    def __init__(self, sessions=SessionLocal):
        self.sessions = sessions
        self._config = ConnectionSettings()
        self._revision = 0
        self._lock = RLock()
        self._operations = 0

    def load(self):
        with self._lock, self.sessions() as db:
            row = db.get(models.RosDebugSettings, 1)
            if row:
                self._config = ConnectionSettings.model_validate_json(row.config_json)
                self._revision = row.revision

    def snapshot(self):
        with self._lock:
            return {**self._config.model_dump(), "revision": self._revision}

    def update(self, request: SettingsChange):
        with self._lock, self.sessions() as db:
            if request.expected_revision != self._revision:
                raise HTTPException(409, "配置已在其他窗口更新，请重新读取后修改")
            if self._operations or db.query(models.FineTuningBatch).filter(models.FineTuningBatch.target_key.is_not(None)).first():
                raise HTTPException(409, "存在进行中或待核实操作，请先处理完成再修改连接")
            try:
                config = ConnectionSettings.model_validate({**self._config.model_dump(), **request.changes})
            except ValidationError as exc:
                raise HTTPException(422, str(exc)) from exc
            revision = self._revision + 1
            row = db.get(models.RosDebugSettings, 1)
            if row is None:
                row = models.RosDebugSettings(id=1)
                db.add(row)
            row.revision, row.config_json = revision, config.model_dump_json()
            db.commit()
            self._config, self._revision = config, revision
            return self.snapshot()

    @contextmanager
    def operation(self, revision):
        # 保持当前动作的地址/模式快照；同步和异步调用都使用同一计数。
        with self._lock:
            if revision != self._revision:
                raise HTTPException(409, "连接配置已变更，请重新确认操作目标")
            self._operations += 1
        try:
            yield
        finally:
            with self._lock:
                self._operations -= 1


runtime_settings = RuntimeSettings()
