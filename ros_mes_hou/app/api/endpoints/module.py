# app/api/endpoints/module.py

from fastapi import APIRouter, Body, HTTPException

from app.services.ros_service import RosDispatchError, publish_ros_command

router = APIRouter()


def first_not_none(*values):
    for value in values:
        if value is not None:
            return value
    return None


@router.post("/")
def lock_and_dispatch_module(payload: dict = Body(...)):
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

    if isinstance(position, dict):
        x = first_not_none(x, position.get("x"))
        y = first_not_none(y, position.get("y"))

    if x is None or y is None:
        raise HTTPException(status_code=422, detail="缺少 x 或 y 坐标")

    try:
        x = int(x)
        y = int(y)
        module_id = int(module_id) if module_id is not None else x * 16 + y
        device_id = int(device_id) if device_id is not None else None
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="模块参数格式错误")

    dispatch_payload = {
        "x": x,
        "y": y,
        "module_id": module_id,
        "device_id": device_id,
        "position": position,
        "raw": payload,
    }

    try:
        dispatch_result = publish_ros_command("module_lock", dispatch_payload)
    except RosDispatchError as exc:
        raise HTTPException(status_code=503, detail=f"ROS 下发失败：{exc}") from exc

    return {
        "code": 200,
        "message": "模块锁定并下发成功",
        "data": dispatch_payload,
        "dispatch": dispatch_result,
    }