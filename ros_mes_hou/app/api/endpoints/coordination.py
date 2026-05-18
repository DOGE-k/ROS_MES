from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import models
from app.db.database import get_db
from app.services.rosbridge_gateway import (
    RosbridgeError,
    build_drawing_path_publish_payload,
    rosbridge_dispatcher,
)

router = APIRouter()


@router.post("/send")
def send_coordination(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    dispatcher=rosbridge_dispatcher,
):
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
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="模块、机械臂或图纸编号格式错误") from exc

    drawing = (
        db.query(models.Drawing)
        .filter(
            models.Drawing.Drawing_ID == dispatch_payload["drawing_id"],
            models.Drawing.del_flag == False,
        )
        .first()
    )
    if not drawing:
        raise HTTPException(status_code=404, detail="图纸不存在")
    if not drawing.Drawingfile:
        raise HTTPException(status_code=422, detail="图纸文件路径为空")

    ros_payload = build_drawing_path_publish_payload(drawing.Drawingfile)
    ros_payload["business"] = dispatch_payload

    try:
        dispatch_result = dispatcher.dispatch("drawing_path", ros_payload)
    except RosbridgeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "code": 200,
        "message": "目标图纸路径下发成功",
        "data": dispatch_payload,
        "dispatch": dispatch_result,
    }
