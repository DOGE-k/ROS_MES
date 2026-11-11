"""局部停（模块停 / 单轴停）记录与下发拦截。

与全局急停分开：
- 全局急停写 `control_safety`，整机联锁；
- 局部停写 `control_stop_holds`，只锁本模块或本轴，其他模块不受影响。

边界：局部停只发送协议的停止帧（`[0x08, module_id]` / `[0x0C, 1]`）并记 MES 记录；
设备侧是否锁存、如何解除取决于固件，协议里只有全局 `[0x04]` 解除。清除记录只是恢复
MES 的下发能力，不发送解除指令，也不代表设备已可运动。
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from app.db import models
from app.ros.base import RosbridgeError
from app.ros.control_session import _iso, utcnow_naive
from app.ros.rosbridge import resolve_arm_from_unit_id

SCOPE_MODULE = "module"
SCOPE_ARM = "arm"
SCOPE_AXIS = "axis"
AXIS_PARAMETERS = ("rotation", "swing", "telescopic")
AXES_PER_ARM = 3
BLOCK_MESSAGE = "该目标已执行局部停（模块停/臂停/轴停），需操作员确认清除后才能继续下发"


def axis_number(unit_id: int, parameter_name: str) -> int:
    """按 V2 轴编码把业务机械臂 + 参数名换算为 1~15 轴号。"""
    arm = resolve_arm_from_unit_id(unit_id)
    return (arm - 1) * 3 + AXIS_PARAMETERS.index(parameter_name) + 1


def axis_numbers_for_arm(arm: int) -> set:
    """某台机械臂的 3 个轴号（臂2 → {4,5,6}）。"""
    start = (int(arm) - 1) * AXES_PER_ARM + 1
    return set(range(start, start + AXES_PER_ARM))


def arm_of_axis(axis: int) -> int:
    return (int(axis) - 1) // AXES_PER_ARM + 1


def axes_for(unit_id: int, parameters: Iterable[str]) -> set:
    axes = set()
    for name in parameters:
        if name in AXIS_PARAMETERS:
            axes.add(axis_number(unit_id, name))
    return axes


class StopHoldManager:
    def snapshot(self, row: models.ControlStopHold) -> Dict[str, Any]:
        return {
            "id": row.id,
            "mode": row.mode,
            "scope": row.scope,
            "module_id": int(row.module_id),
            "device_id": row.device_id,
            "state": row.state,
            "message": row.message,
            "created_at": _iso(row.created_at),
            "cleared_at": _iso(row.cleared_at),
            "cleared_reason": row.cleared_reason,
            "active": row.cleared_at is None,
        }

    def _active_query(self, db, mode: str):
        return db.query(models.ControlStopHold).filter(
            models.ControlStopHold.mode == mode,
            models.ControlStopHold.cleared_at.is_(None),
        )

    def create(self, db, *, mode: str, scope: str, module_id: int,
               device_id: Optional[int] = None, state: str = "requested",
               message: Optional[str] = None, creator_id: int = 1) -> Dict[str, Any]:
        row = models.ControlStopHold(
            mode=mode, scope=scope, module_id=int(module_id), device_id=device_id,
            state=state, message=message, creator_id=creator_id,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return self.snapshot(row)

    def update_state(self, db, hold_id: int, state: str, message: Optional[str] = None) -> Optional[Dict[str, Any]]:
        row = db.get(models.ControlStopHold, hold_id)
        if row is None:
            return None
        row.state = state
        if message is not None:
            row.message = message
        db.commit()
        db.refresh(row)
        return self.snapshot(row)

    def active(self, db, mode: str = "real") -> list:
        rows = self._active_query(db, mode).order_by(models.ControlStopHold.created_at.desc()).all()
        return [self.snapshot(row) for row in rows]

    def clear(self, db, hold_id: int, *, mode: str = "real", reason: str = "operator_cleared"):
        row = db.get(models.ControlStopHold, hold_id)
        if row is None or row.mode != mode:
            return None
        if row.cleared_at is None:
            row.cleared_at = utcnow_naive()
            row.cleared_reason = reason
            db.commit()
            db.refresh(row)
        return self.snapshot(row)

    def clear_module(self, db, module_id: int, *, mode: str = "real", reason: str = "operator_cleared") -> int:
        rows = self._active_query(db, mode).filter(models.ControlStopHold.module_id == int(module_id)).all()
        for row in rows:
            row.cleared_at = utcnow_naive()
            row.cleared_reason = reason
        if rows:
            db.commit()
        return len(rows)

    def blocked(self, db, module_id: int, *, axes: Optional[Iterable[int]] = None,
                mode: str = "real") -> Optional[Dict[str, Any]]:
        """返回命中的局部停记录；`axes` 为 None 表示无法判定轴，按整模块拦截。"""
        wanted = None if axes is None else {int(item) for item in axes}
        rows = self._active_query(db, mode).filter(models.ControlStopHold.module_id == int(module_id)).all()
        for row in rows:
            if row.scope == SCOPE_MODULE:
                return self.snapshot(row)
            if wanted is None:
                return self.snapshot(row)
            if row.device_id is None:
                continue
            if row.scope == SCOPE_ARM:
                arm = int(row.device_id)
                if any(arm_of_axis(axis) == arm for axis in wanted):
                    return self.snapshot(row)
                continue
            if int(row.device_id) in wanted:
                return self.snapshot(row)
        return None

    def assert_available(self, db, module_id: int, *, axes: Optional[Iterable[int]] = None,
                         mode: str = "real") -> None:
        hold = self.blocked(db, module_id, axes=axes, mode=mode)
        if hold is not None:
            raise RosbridgeError(BLOCK_MESSAGE)


def validate_target(*, scope: str, module_id: int, device_id: Optional[int]) -> None:
    """下发前的参数校验：模块必须可映射 SEG；臂号 1~5；轴号 1~15。"""
    if scope not in (SCOPE_MODULE, SCOPE_ARM, SCOPE_AXIS):
        raise RosbridgeError(f"局部停 scope 非法：{scope!r}（支持 module/arm/axis）")
    if module_id is None or int(module_id) <= 0:
        raise RosbridgeError("局部停缺少有效模块号")
    if scope == SCOPE_ARM:
        if device_id is None:
            raise RosbridgeError("臂停必须指定臂号 device_id")
        if not 1 <= int(device_id) <= 5:
            raise RosbridgeError(f"臂停臂号 {device_id} 非法（允许 1~5）")
    if scope == SCOPE_AXIS:
        if device_id is None:
            raise RosbridgeError("单轴停必须指定轴号 device_id")
        if not 1 <= int(device_id) <= 15:
            raise RosbridgeError(f"单轴停轴号 {device_id} 非法（允许 1~15）")


stop_holds = StopHoldManager()
