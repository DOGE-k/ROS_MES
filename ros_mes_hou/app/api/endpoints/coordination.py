import os
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

from fastapi import APIRouter, Body, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.db import models
from app.db.database import get_db
from app.services.rosbridge_gateway import (
    RosbridgeError,
    build_drawing_path_publish_payload,
    rosbridge_dispatcher,
)

router = APIRouter()

POINTCLOUD_VIEW_BASE_URL = os.getenv("POINTCLOUD_VIEW_BASE_URL", "http://localhost:5000")
POINTCLOUD_VIEW_NAMES = {"top", "front", "side"}
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
ROS_SCRIPT_DIR = os.path.join(PROJECT_ROOT, "robot_control_backend", "scripts")


def build_pointcloud_view_urls() -> dict:
    return {
        view_name: f"/api/coordination/views/{view_name}"
        for view_name in sorted(POINTCLOUD_VIEW_NAMES)
    }


def fetch_pointcloud_view(view_name: str) -> tuple[bytes, str]:
    if view_name not in POINTCLOUD_VIEW_NAMES:
        raise HTTPException(status_code=404, detail="unknown pointcloud view")

    url = f"{POINTCLOUD_VIEW_BASE_URL.rstrip('/')}/get_view/{view_name}"
    request = Request(url, headers={"Cache-Control": "no-cache"})
    try:
        with urlopen(request, timeout=2.0) as response:
            content_type = response.headers.get("Content-Type", "image/png")
            return response.read(), content_type
    except URLError as exc:
        raise HTTPException(status_code=502, detail=f"pointcloud view service unavailable: {exc}") from exc


def wait_for_pointcloud_views(timeout_seconds: float = 5.0, interval_seconds: float = 0.5) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            for view_name in POINTCLOUD_VIEW_NAMES:
                content, _ = fetch_pointcloud_view(view_name)
                if not content:
                    raise ValueError("empty pointcloud view")
            return True
        except Exception:
            time.sleep(interval_seconds)
    return False


def to_ros_node_relative_path(file_path: str) -> str:
    relative_path = os.path.relpath(os.path.abspath(file_path), ROS_SCRIPT_DIR)
    return relative_path.replace(os.sep, "/")


@router.get("/views/{view_name}")
def proxy_pointcloud_view(view_name: str):
    content, media_type = fetch_pointcloud_view(view_name)
    return Response(content=content, media_type=media_type)


@router.post("/send")
def send_coordination(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    dispatcher=rosbridge_dispatcher,
    wait_for_views=wait_for_pointcloud_views,
):
    device_id = payload.get("device_id")
    module_id = payload.get("module_id")
    unit_id = payload.get("unit_id")
    unit_row_id = payload.get("unit_row_id")
    drawing_id = payload.get("drawing_id")

    if device_id is None:
        raise HTTPException(status_code=422, detail="missing device_id")
    if module_id is None:
        raise HTTPException(status_code=422, detail="missing module_id")
    if unit_id is None:
        raise HTTPException(status_code=422, detail="missing unit_id")
    if unit_row_id is None:
        raise HTTPException(status_code=422, detail="missing unit_row_id")
    if drawing_id is None:
        raise HTTPException(status_code=422, detail="missing drawing_id")

    try:
        dispatch_payload = {
            "device_id": int(device_id),
            "module_id": int(module_id),
            "unit_id": int(unit_id),
            "unit_row_id": int(unit_row_id),
            "drawing_id": int(drawing_id),
        }
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="invalid module, unit, or drawing id") from exc

    drawing = (
        db.query(models.Drawing)
        .filter(
            models.Drawing.Drawing_ID == dispatch_payload["drawing_id"],
            models.Drawing.del_flag == False,
        )
        .first()
    )
    if not drawing:
        raise HTTPException(status_code=404, detail="drawing not found")
    if not drawing.Drawingfile:
        raise HTTPException(status_code=422, detail="drawing file path is empty")

    ros_file_path = to_ros_node_relative_path(drawing.Drawingfile)
    ros_payload = build_drawing_path_publish_payload(ros_file_path)
    ros_payload["business"] = dispatch_payload

    try:
        dispatch_result = dispatcher.dispatch("drawing_path", ros_payload)
    except RosbridgeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if not wait_for_views():
        raise HTTPException(status_code=504, detail="pointcloud views generation timed out")

    return {
        "code": 200,
        "message": "target drawing path dispatched and pointcloud views are ready",
        "data": dispatch_payload,
        "dispatch": dispatch_result,
        "views": build_pointcloud_view_urls(),
    }
