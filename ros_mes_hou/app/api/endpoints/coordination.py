# app/api/endpoints/coordination.py

from fastapi import APIRouter, Body, HTTPException

router = APIRouter()


@router.post("/send")
def send_coordination(payload: dict = Body(...)):
    device_id = payload.get("device_id")
    module_id = payload.get("module_id")
    unit_id = payload.get("unit_id")
    unit_row_id = payload.get("unit_row_id")
    drawing_id = payload.get("drawing_id")

    if device_id is None:
        raise HTTPException(status_code=422, detail="缺少 device_id")
    if module_id is None:
        raise HTTPException(status_code=422, detail="缺少 module_id")
    if unit_id is None:
        raise HTTPException(status_code=422, detail="缺少 unit_id")
    if unit_row_id is None:
        raise HTTPException(status_code=422, detail="缺少 unit_row_id")
    if drawing_id is None:
        raise HTTPException(status_code=422, detail="缺少 drawing_id")

    try:
        dispatch_payload = {
            "device_id": int(device_id),
            "module_id": int(module_id),
            "unit_id": int(unit_id),
            "unit_row_id": int(unit_row_id),
            "drawing_id": int(drawing_id),
        }
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="模块、机械臂或图纸编号格式错误")

    return {
        "code": 200,
        "message": "目标图纸下发成功",
        "data": dispatch_payload,
    }
