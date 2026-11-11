# app/api/endpoints/module.py

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.ros import get_ros_dispatcher
from app.ros.base import RosbridgeError
from app.ros.control_session import session_manager
from app.ros.rosbridge import (
    build_module_confirm_publish_payload,
    resolve_arm_from_unit_id,
    resolve_module_seg,
)

router = APIRouter()


def first_not_none(*values):
    for value in values:
        if value is not None:
            return value
    return None


def _register_session(db, *, module_id, seg, device_id, x, y, unit_ids, dispatcher) -> dict:
    """握手成功后登记可续接会话。

    写入失败不影响已完成的物理握手，但必须在响应里如实标注 session_error，
    前端据此提示“本次不可续接”，不能让失败看起来像成功。
    """
    if not isinstance(db, Session):
        # 直接调用（内部脚本/单测未解析 Depends）时不落会话
        return {"session_id": None, "session_error": "no_db"}
    try:
        record = session_manager.create(
            db, module_id=module_id, seg=seg, unit_ids=unit_ids, device_id=device_id,
            x=x, y=y, connection_revision=getattr(dispatcher, "revision", None),
        )
        return {"session_id": record["id"], "session": record}
    except Exception as exc:  # SQLite 写锁等异常不应把已完成的握手判为失败
        print(f"[会话] 登记失败，本次不可续接：{exc}")
        return {"session_id": None, "session_error": str(exc)}


@router.post("/")
def lock_and_dispatch_module(payload: dict = Body(...), db: Session = Depends(get_db), dispatcher=None):
    dispatcher = dispatcher or get_ros_dispatcher()
    if payload.get("connection_revision") is not None and payload["connection_revision"] != getattr(dispatcher, "revision", None):
        raise HTTPException(409, "连接设置已更改，请重新读取设置后确认机械臂")
    x = first_not_none(
        payload.get("x"),
        payload.get("X"),
        payload.get("targetX"),
        payload.get("moduleX"),
        payload.get("col"),
    )

    y = first_not_none(
        payload.get("y"),
        payload.get("Y"),
        payload.get("targetY"),
        payload.get("moduleY"),
        payload.get("row"),
    )

    position = payload.get("position")
    module_id = payload.get("module_id")
    device_id = payload.get("device_id")
    unit_ids_raw = first_not_none(payload.get("unit_ids"), payload.get("unitIds"))
    if not isinstance(unit_ids_raw, list) or not unit_ids_raw:
        raise HTTPException(status_code=422, detail="缺少 unit_ids：请选择至少一台机械臂")
    if len(unit_ids_raw) > 5:
        raise HTTPException(status_code=422, detail="unit_ids 最多选择 5 台机械臂")
    try:
        unit_ids = [int(item) for item in unit_ids_raw]
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="unit_ids 必须全部是整数") from exc
    if len(set(unit_ids)) != len(unit_ids):
        raise HTTPException(status_code=422, detail="unit_ids 不能重复")

    if isinstance(position, dict):
        x = first_not_none(x, position.get("x"))
        y = first_not_none(y, position.get("y"))

    if x is None or y is None:
        raise HTTPException(status_code=422, detail="missing x or y coordinate")

    try:
        x = int(x)
        y = int(y)
        module_id = int(module_id) if module_id is not None else x * 16 + y
        device_id = int(device_id) if device_id is not None else None
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="invalid module parameters")

    try:
        seg = resolve_module_seg(module_id)
    except RosbridgeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    dispatch_payload = {
        "x": x,
        "y": y,
        "module_id": module_id,
        "device_id": device_id,
        "unit_ids": unit_ids,
        "position": position,
        "raw": payload,
    }

    arms = []
    for unit_id in unit_ids:
        try:
            arms.append(resolve_arm_from_unit_id(unit_id))
        except RosbridgeError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    confirmations = []
    for index, (unit_id, arm) in enumerate(zip(unit_ids, arms)):
        try:
            ros_payload = build_module_confirm_publish_payload(
                module_id, seg=seg, arm=arm
            )
            ros_payload["business"] = {
                **dispatch_payload,
                "unit_id": unit_id,
                "arm": arm,
                "seg": seg,
            }
            dispatch_result = dispatcher.dispatch("module_confirm", ros_payload)
            if dispatch_result.get("confirmed") is False:
                raise RosbridgeError(f"module confirm failed: unit_id={unit_id}, arm={arm}")
            confirmations.append({
                "unit_id": unit_id,
                "arm": arm,
                "confirmed": bool(dispatch_result.get("confirmed", True)),
                "dispatch": dispatch_result,
            })
        except RosbridgeError as exc:
            raise HTTPException(
                status_code=502,
                detail={
                    "message": "机械臂模块确认失败，已停止后续确认",
                    "failed_unit_id": unit_id,
                    "failed_arm": arm,
                    "confirmed_unit_ids": [item["unit_id"] for item in confirmations],
                    "pending_unit_ids": unit_ids[index:],
                    "reason": str(exc),
                },
            ) from exc

    return {
        "code": 200,
        "message": "module locked and confirmation command dispatched",
        "data": {**dispatch_payload, "seg": seg, "confirmations": confirmations,
                 "connection_revision": getattr(dispatcher, "revision", None),
                 **_register_session(db, module_id=module_id, seg=seg, device_id=device_id, x=x, y=y,
                                     unit_ids=unit_ids, dispatcher=dispatcher)},
        "dispatch": {
            "action": "module_confirm",
            "confirmed": True,
            "count": len(confirmations),
            "confirmations": confirmations,
        },
    }
