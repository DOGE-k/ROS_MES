# app/api/endpoints/coordination.py

from fastapi import APIRouter, Body, HTTPException

from app.services.ros_service import RosDispatchError, publish_ros_command

router = APIRouter()


@router.post("/")
def send_coordination(payload: dict = Body(...)):
    device_id = payload.get("device_id")
    module_id = payload.get("module_id")
    x = payload.get("x")
    y = payload.get("y")
    z = payload.get("z")

    if device_id is None:
        raise HTTPException(status_code=422, detail="缺少 device_id")

    if module_id is None:
        raise HTTPException(status_code=422, detail="缺少 module_id")

    if x is None or y is None or z is None:
        raise HTTPException(status_code=422, detail="缺少 x、y 或 z 坐标")

    try:
        dispatch_payload = {
            "device_id": int(device_id),
            "module_id": int(module_id),
            "x": float(x),
            "y": float(y),
            "z": float(z),
        }
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="坐标或设备编号格式错误")

    try:
        dispatch_result = publish_ros_command("coordination", dispatch_payload)
    except RosDispatchError as exc:
        raise HTTPException(status_code=503, detail=f"ROS 下发失败：{exc}") from exc

    return {
        "code": 200,
        "message": "坐标下发成功",
        "data": dispatch_payload,
        "dispatch": dispatch_result,
    }