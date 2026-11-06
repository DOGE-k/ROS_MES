from __future__ import annotations

import os
import time
from contextlib import nullcontext
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener

from fastapi import APIRouter, Body, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import models
from app.db.database import get_db
from app.ros import get_ros_dispatcher
from app.ros.base import RosbridgeError
from app.ros.rosbridge import build_drawing_path_publish_payload

router = APIRouter()

POINTCLOUD_VIEW_BASE_URL = os.getenv("POINTCLOUD_VIEW_BASE_URL", "http://localhost:5000")
POINTCLOUD_VIEW_NAMES = {"top", "front", "side"}
# 点云视图服务通常与后端同机/内网，强制绕过 HTTP_PROXY，避免代理拖垮 2s 超时
_VIEW_OPENER = build_opener(ProxyHandler({}))
# ROS 端脚本目录统一收敛到 app/core/config.py（ROS_SCRIPTS_DIR，可用环境变量覆盖）
ROS_SCRIPT_DIR = settings.ROS_SCRIPTS_DIR


def build_pointcloud_view_urls(connection_revision: int | None = None) -> dict:
    return {
        view_name: f"/api/coordination/views/{view_name}" + (f"?connection_revision={connection_revision}" if connection_revision is not None else "")
        for view_name in sorted(POINTCLOUD_VIEW_NAMES)
    }


def fetch_pointcloud_view(view_name: str, base_url: str | None = None) -> tuple[bytes, str]:
    if view_name not in POINTCLOUD_VIEW_NAMES:
        raise HTTPException(status_code=404, detail="unknown pointcloud view")

    # SSRF 防护：目标 URL 的协议与主机必须与配置的视图服务完全一致，且 view_name 已白名单
    base_url = base_url or POINTCLOUD_VIEW_BASE_URL
    base = urlsplit(base_url)
    if base.scheme not in ("http", "https") or not base.netloc:
        raise HTTPException(status_code=502, detail="pointcloud view service config invalid")
    url = f"{base_url.rstrip('/')}/get_view/{view_name}"
    target = urlsplit(url)
    if (target.scheme, target.netloc) != (base.scheme, base.netloc):
        raise HTTPException(status_code=502, detail="pointcloud view service config invalid")

    request = Request(url, headers={"Cache-Control": "no-cache"})
    try:
        with _VIEW_OPENER.open(request, timeout=2.0) as response:
            content_type = response.headers.get("Content-Type", "image/png")
            return response.read(), content_type
    except URLError as exc:
        raise HTTPException(status_code=502, detail=f"pointcloud view service unavailable: {exc}") from exc


def wait_for_pointcloud_views(timeout_seconds: float = 5.0, interval_seconds: float = 0.5, *, base_url: str | None = None) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            for view_name in POINTCLOUD_VIEW_NAMES:
                content, _ = fetch_pointcloud_view(view_name, base_url)
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
def proxy_pointcloud_view(view_name: str, connection_revision: int | None = None):
    if view_name not in POINTCLOUD_VIEW_NAMES:
        raise HTTPException(404, "unknown pointcloud view")
    config = get_ros_dispatcher().connection_settings
    if config["drawing_mode"] == "skip":
        raise HTTPException(409, "当前选择不使用图纸，没有可用三视图")
    if connection_revision is not None and connection_revision != config["revision"]:
        raise HTTPException(409, "连接设置已更改，请重新下发或读取当前图纸视图")
    if config["drawing_mode"] == "mock":
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360"><rect width="640" height="360" fill="#eef4ff"/><path d="M80 280H560M120 320V60" stroke="#84a4dc"/><text x="200" y="155" font-size="26" fill="#24549b">SIMULATED {view_name.upper()}</text><text x="175" y="205" font-size="20" fill="#47658a">Mock preview - no real point cloud</text></svg>'
        return Response(svg, media_type="image/svg+xml", headers={"Cache-Control": "no-store"})
    content, media_type = fetch_pointcloud_view(view_name, config["pointcloud_url"])
    return Response(content=content, media_type=media_type)


@router.post("/send")
def send_coordination(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    dispatcher=None,
    wait_for_views=wait_for_pointcloud_views,
):
    dispatcher = dispatcher or get_ros_dispatcher()
    if payload.get("connection_revision") is not None and payload["connection_revision"] != getattr(dispatcher, "revision", None):
        raise HTTPException(409, "连接配置已更改，请重新确认机械臂后下发图纸")
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
    source = payload.get("drawing_source", "database")
    drawing_mode = getattr(dispatcher, "connection_settings", {}).get("drawing_mode", "real")
    if drawing_mode == "skip":
        raise HTTPException(409, "当前选择不使用图纸，不允许下发图纸")
    if not isinstance(source, str) or source not in {"database", "builtin_mock"}:
        raise HTTPException(422, "invalid drawing source")
    if source == "builtin_mock" and (drawing_mode != "mock" or drawing_id is not None):
        raise HTTPException(422, "内置图纸仅用于模拟下发，不接受业务图纸编号")
    if source == "database" and drawing_id is None:
        raise HTTPException(status_code=422, detail="missing drawing_id")

    try:
        dispatch_payload = {
            "device_id": int(device_id),
            "module_id": int(module_id),
            "unit_id": int(unit_id),
            "unit_row_id": int(unit_row_id),
            "drawing_id": int(drawing_id) if drawing_id is not None else None,
            "drawing_source": source,
        }
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="invalid module, unit, or drawing id") from exc

    if source == "builtin_mock":
        # 内置示例不创建业务图纸，也不构造可发送给真实 ROS 的路径。
        ros_payload = {"drawing_source": "builtin_mock"}
    else:
        drawing = db.query(models.Drawing).filter(
            models.Drawing.Drawing_ID == dispatch_payload["drawing_id"], models.Drawing.del_flag == False).first()
        if not drawing:
            raise HTTPException(status_code=404, detail="drawing not found")
        if not drawing.Drawingfile:
            raise HTTPException(status_code=422, detail="drawing file path is empty")
        ros_payload = build_drawing_path_publish_payload(to_ros_node_relative_path(drawing.Drawingfile))
    ros_payload["business"] = dispatch_payload

    with dispatcher.operation() if hasattr(dispatcher, "operation") else nullcontext():
        try:
            dispatch_result = dispatcher.dispatch("drawing_path", ros_payload)
        except RosbridgeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        simulated = dispatch_result.get("simulated") is True
        views_ready = True if simulated else (
            wait_for_views(base_url=dispatcher.connection_settings["pointcloud_url"])
            if wait_for_views is wait_for_pointcloud_views and hasattr(dispatcher, "connection_settings") else wait_for_views())
        if not views_ready:
            raise HTTPException(status_code=504, detail="pointcloud views generation timed out")

        return {
            "code": 200,
            "message": "图纸下发模拟成功，三视图为模拟预览" if simulated else "target drawing path dispatched and pointcloud views are ready",
            "simulated": simulated,
            "data": dispatch_payload,
            "dispatch": dispatch_result,
            "views": build_pointcloud_view_urls(getattr(dispatcher, "revision", None)),
        }
