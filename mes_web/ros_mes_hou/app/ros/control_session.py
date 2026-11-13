"""微调会话记录：把一次成功的模块握手登记为可续接会话。

边界说明（不要扩大解释）：
- 本表只记录 MES 侧的会话事实：业务模块号、ROS 组号、已确认机械臂、连接版本。
- 登记不代表设备侧仍保持绑定；ROS 的会话表在 module_confirme_node 内存中，节点重启或
  机械臂断电即失效，本侧无法查询，只能按记录续接，UI 必须标注未经设备复核。
- 续接只读本表并滑动有效期，不发送模块确认，也不自动重发任何运动指令。
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, Optional

from app.db import models

REASON_CLOSED = "closed"
REASON_SUPERSEDED = "superseded"
REASON_CONNECTION_CHANGED = "connection_changed"
REASON_EXPIRED = "expired"
REASON_MISSING = "missing"


def utcnow_naive() -> datetime:
    """统一时间基准：SQLite 的 CURRENT_TIMESTAMP 为 UTC 且无时区，这里保持同口径。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(value: Optional[datetime]) -> Optional[str]:
    if not value:
        return None
    # 库里存的是无时区 UTC，补 Z 以免前端按本地时间解析导致有效期偏差。
    return value.isoformat() + ("Z" if value.tzinfo is None else "")


class ControlSessionManager:
    """会话记录的读写与失效判定；有效期由前端偏好按请求传入，不落库。"""

    def snapshot(self, row: models.ControlSession, ttl_seconds: Optional[int] = None) -> Dict[str, Any]:
        expires_at = None
        if row.last_active_at is not None and ttl_seconds:
            expires_at = _iso(row.last_active_at + timedelta(seconds=int(ttl_seconds)))
        try:
            unit_ids = json.loads(row.unit_ids_json or "[]")
        except (TypeError, ValueError):
            unit_ids = []
        return {
            "id": row.id,
            "module_id": int(row.module_id),
            "device_id": row.device_id,
            "x": row.x,
            "y": row.y,
            "seg": int(row.seg),
            "unit_ids": [int(item) for item in unit_ids if isinstance(item, (int, str))],
            "connection_revision": row.connection_revision,
            "creator_id": row.creator_id,
            "created_at": _iso(row.created_at),
            "last_active_at": _iso(row.last_active_at),
            "expires_at": expires_at,
            "invalidated_at": _iso(row.invalidated_at),
            "invalid_reason": row.invalid_reason,
        }

    def _active_rows(self, db) -> Iterable[models.ControlSession]:
        return db.query(models.ControlSession).filter(models.ControlSession.invalidated_at.is_(None))

    def invalidate(self, db, *, seg: Optional[int] = None, unit_ids: Optional[Iterable[int]] = None,
                   reason: str = REASON_SUPERSEDED) -> int:
        """作废同一物理目标上的旧会话：组号相同或机械臂有交集即视为被新握手取代。"""
        targets = {int(item) for item in (unit_ids or [])}
        count = 0
        for row in list(self._active_rows(db)):
            try:
                row_units = {int(item) for item in json.loads(row.unit_ids_json or "[]")}
            except (TypeError, ValueError):
                row_units = set()
            if (seg is not None and int(row.seg) == int(seg)) or (targets and row_units & targets):
                row.invalidated_at = utcnow_naive()
                row.invalid_reason = reason
                count += 1
        if count:
            db.commit()
        return count

    def invalidate_all(self, db, reason: str = REASON_CONNECTION_CHANGED) -> int:
        count = 0
        for row in list(self._active_rows(db)):
            row.invalidated_at = utcnow_naive()
            row.invalid_reason = reason
            count += 1
        if count:
            db.commit()
        return count

    def create(self, db, *, module_id: int, seg: int, unit_ids: Iterable[int],
               device_id: Optional[int] = None, x: Optional[int] = None, y: Optional[int] = None,
               connection_revision: Optional[int] = None, creator_id: int = 1) -> Dict[str, Any]:
        units = [int(item) for item in unit_ids]
        # 先作废旧会话再登记，避免刚写入的记录被自己的清理逻辑命中。
        self.invalidate(db, seg=seg, unit_ids=units, reason=REASON_SUPERSEDED)
        row = models.ControlSession(
            id=str(uuid.uuid4()),
            module_id=int(module_id),
            device_id=device_id,
            x=x,
            y=y,
            seg=int(seg),
            unit_ids_json=json.dumps(units),
            connection_revision=connection_revision,
            creator_id=creator_id,
            last_active_at=utcnow_naive(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return self.snapshot(row)

    def _invalid_reason(self, row: models.ControlSession, ttl_seconds: Optional[int],
                        current_revision: Optional[int]) -> Optional[str]:
        if row.invalidated_at is not None:
            return row.invalid_reason or REASON_CLOSED
        if current_revision is not None and row.connection_revision is not None \
                and int(row.connection_revision) != int(current_revision):
            return REASON_CONNECTION_CHANGED
        if ttl_seconds and row.last_active_at is not None:
            if utcnow_naive() > row.last_active_at + timedelta(seconds=int(ttl_seconds)):
                return REASON_EXPIRED
        return None

    def _finalize(self, db, row: models.ControlSession, reason: str) -> None:
        row.invalidated_at = utcnow_naive()
        row.invalid_reason = reason
        db.commit()

    def state(self, db, *, ttl_seconds: Optional[int] = None,
              current_revision: Optional[int] = None) -> Dict[str, Any]:
        """最近一条会话的有效性；session 只返回当前可续接的记录。"""
        latest = (db.query(models.ControlSession)
                  .order_by(models.ControlSession.created_at.desc()).first())
        active = (self._active_rows(db)
                  .order_by(models.ControlSession.created_at.desc()).first())
        if active is None:
            reason = latest.invalid_reason if latest is not None else None
            return {"session": None, "latest": self.snapshot(latest) if latest else None,
                    "reason": reason or (REASON_MISSING if latest is None else REASON_CLOSED)}
        reason = self._invalid_reason(active, ttl_seconds, current_revision)
        if reason is not None:
            self._finalize(db, active, reason)
            return {"session": None, "latest": self.snapshot(active, ttl_seconds), "reason": reason}
        return {"session": self.snapshot(active, ttl_seconds),
                "latest": self.snapshot(active, ttl_seconds), "reason": None}

    def resume(self, db, session_id: str, *, ttl_seconds: Optional[int] = None,
               current_revision: Optional[int] = None) -> Dict[str, Any]:
        """校验并滑动有效期；无效时返回原因，不抛异常（前端据 reason 提示并重新握手）。"""
        row = db.get(models.ControlSession, session_id)
        if row is None:
            return {"valid": False, "reason": REASON_MISSING, "session": None}
        reason = self._invalid_reason(row, ttl_seconds, current_revision)
        if reason is not None:
            if row.invalidated_at is None:
                self._finalize(db, row, reason)
            return {"valid": False, "reason": reason, "session": None}
        row.last_active_at = utcnow_naive()
        db.commit()
        db.refresh(row)
        return {"valid": True, "reason": None, "session": self.snapshot(row, ttl_seconds)}

    def close(self, db, session_id: str, reason: str = REASON_CLOSED):
        row = db.get(models.ControlSession, session_id)
        if row is None:
            return None
        if row.invalidated_at is None:
            self._finalize(db, row, reason)
        return self.snapshot(row)


session_manager = ControlSessionManager()
