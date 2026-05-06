from fastapi import APIRouter, Body, Depends, HTTPException

from app.api.deps import get_current_user
from app.db import models
from app.services.ros_dispatcher import RosDispatchError, ros_dispatcher

router = APIRouter()


@router.post("/")
def lock_and_dispatch_module(
    payload: dict = Body(...),
    current_user: models.User = Depends(get_current_user),
):
    x = (
        payload.get("x")
        or payload.get("X")
        or payload.get("targetX")
        or payload.get("moduleX")
        or payload.get("col")
    )
    y = (
        payload.get("y")
        or payload.get("Y")
        or payload.get("targetY")
        or payload.get("moduleY")
        or payload.get("row")
    )

    position = payload.get("position")
    if isinstance(position, dict):
        x = x or position.get("x")
        y = y or position.get("y")

    if x is None or y is None:
        raise HTTPException(status_code=422, detail="缺少 x 或 y 坐标")

    try:
        x = int(x)
        y = int(y)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="x 和 y 必须是数字")

    if not (1 <= x <= 8 and 1 <= y <= 8):
        raise HTTPException(status_code=400, detail="坐标范围必须是 1 到 8")

    dispatch_payload = {
        "x": x,
        "y": y,
        "operator": current_user.username,
        "raw": payload,
    }

    try:
        dispatch_result = ros_dispatcher.dispatch("module_lock", dispatch_payload)
    except RosDispatchError as exc:
        raise HTTPException(status_code=502, detail=f"ROS 下发失败：{exc}") from exc

    return {
        "code": 200,
        "message": "模块锁定并下发成功",
        "data": {"x": x, "y": y},
        "dispatch": dispatch_result,
    }
