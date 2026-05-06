from fastapi import APIRouter, Body, Depends, HTTPException

from app.api.deps import get_current_user
from app.db import models
from app.services.ros_dispatcher import RosDispatchError, ros_dispatcher

router = APIRouter()


@router.post("/")
def send_coordination(
    payload: dict = Body(...),
    current_user: models.User = Depends(get_current_user),
):
    device_id = payload.get("device_id")
    x = payload.get("x")
    y = payload.get("y")
    z = payload.get("z")
    module_id = payload.get("module_id")

    if device_id is None:
        raise HTTPException(status_code=422, detail="缺少 device_id")
    if x is None or y is None or z is None:
        raise HTTPException(status_code=422, detail="缺少 x、y 或 z 坐标")

    try:
        device_id = int(device_id)
        x = float(x)
        y = float(y)
        z = float(z)
        module_id = int(module_id) if module_id is not None else None
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="坐标或设备编号格式错误")

    dispatch_payload = {
        "device_id": device_id,
        "module_id": module_id,
        "x": x,
        "y": y,
        "z": z,
        "operator": current_user.username,
    }

    try:
        dispatch_result = ros_dispatcher.dispatch("coordination", dispatch_payload)
    except RosDispatchError as exc:
        raise HTTPException(status_code=502, detail=f"ROS 下发失败：{exc}") from exc

    return {
        "code": 200,
        "message": "坐标下发成功",
        "data": dispatch_payload,
        "dispatch": dispatch_result,
    }
