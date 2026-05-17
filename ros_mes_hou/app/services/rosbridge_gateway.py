from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any, AsyncIterator, Dict, List

try:
    import websockets
except ImportError:  # pragma: no cover - depends on deployment environment
    websockets = None


ROSBRIDGE_URL = os.getenv("ROSBRIDGE_URL", "ws://192.168.0.105:9090")
ROS_COMM_MODULE_ID = 17

FINE_TUNING_TOPIC_MAP: Dict[str, Dict[str, Any]] = {
    "rotation": {
        "topic": "/control/adjust_rotation_cmd",
        "message_type": "robot_control_backend/RotationCmd",
        "device_id": 33,
    },
    "swing": {
        "topic": "/control/adjust_swing_cmd",
        "message_type": "robot_control_backend/SwingCmd",
        "device_id": 34,
    },
    "telescopic": {
        "topic": "/control/adjust_telescopic_cmd",
        "message_type": "robot_control_backend/TelescopicCmd",
        "device_id": 35,
    },
}

FEEDBACK_TOPICS: List[str] = [
    "/hardware/rotation_feedback",
    "/hardware/swing_feedback",
    "/hardware/telescope_feedback",
    "/hardware/sensor_feedback",
]

FEEDBACK_LABELS = {
    33: ("axis_encoder", "旋转轴编码器"),
    34: ("axis_encoder", "摆动轴编码器"),
    35: ("axis_encoder", "伸缩轴编码器"),
    49: ("pressure_sensor", "压力传感器"),
}


class RosbridgeError(RuntimeError):
    pass


def _stamp() -> Dict[str, int]:
    now = time.time()
    secs = int(now)
    nsecs = int((now - secs) * 1_000_000_000)
    return {"secs": secs, "nsecs": nsecs}


def build_fine_tuning_publish_payload(parameter_name: str, position: float) -> Dict[str, Any]:
    mapping = FINE_TUNING_TOPIC_MAP.get(parameter_name)
    if mapping is None:
        raise RosbridgeError(f"unsupported fine-tuning parameter: {parameter_name}")

    return {
        "topic": mapping["topic"],
        "message_type": mapping["message_type"],
        "message": {
            "header": {"stamp": _stamp(), "frame_id": ""},
            "module_id": ROS_COMM_MODULE_ID,
            "device_id": mapping["device_id"],
            "position": [float(position)],
        },
        "parameter_name": parameter_name,
    }


def _position_value(value: Any) -> float:
    if isinstance(value, list):
        return float(value[0]) if value else 0.0
    return float(value)


def normalize_feedback_message(topic: str, msg: Dict[str, Any]) -> Dict[str, Any]:
    device_id = int(msg.get("device_id", 0))
    data_type, feedback_type = FEEDBACK_LABELS.get(device_id, ("unknown", "未知反馈"))
    header = msg.get("header") or {}
    stamp = header.get("stamp") if isinstance(header, dict) else None

    normalized = {
        "time_id": time.time(),
        "topic": topic,
        "header": stamp or header,
        "module_id": int(msg.get("module_id", 0)),
        "device_id": device_id,
        "position": _position_value(msg.get("position", 0)),
        "data_type": data_type,
        "feedback_type": feedback_type,
        "raw": msg,
    }
    if "id" in msg:
        normalized["id"] = msg["id"]
    return normalized


class RosbridgeDispatcher:
    def __init__(self, url: str = ROSBRIDGE_URL, timeout: float = 5.0):
        self.url = url
        self.timeout = timeout

    def dispatch(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if action != "fine_tuning":
            raise RosbridgeError(f"unsupported rosbridge action: {action}")
        return asyncio.run(self.publish(payload))

    async def publish(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if websockets is None:
            raise RosbridgeError("missing websockets dependency")

        topic = payload["topic"]
        advertise = {
            "op": "advertise",
            "topic": topic,
            "type": payload["message_type"],
        }
        publish = {
            "op": "publish",
            "topic": topic,
            "msg": payload["message"],
        }

        try:
            async with websockets.connect(self.url, close_timeout=1) as ws:
                await asyncio.wait_for(ws.send(json.dumps(advertise, ensure_ascii=False)), self.timeout)
                await asyncio.wait_for(ws.send(json.dumps(publish, ensure_ascii=False)), self.timeout)
        except Exception as exc:
            raise RosbridgeError(f"rosbridge publish failed: {exc}") from exc

        return {
            "sent": True,
            "mode": "rosbridge",
            "url": self.url,
            "action": "fine_tuning",
            "payload": payload,
        }


async def stream_feedback(url: str = ROSBRIDGE_URL) -> AsyncIterator[Dict[str, Any]]:
    if websockets is None:
        yield {"data_type": "error", "message": "missing websockets dependency"}
        return

    try:
        async with websockets.connect(url, close_timeout=1) as ws:
            for topic in FEEDBACK_TOPICS:
                await ws.send(json.dumps({"op": "subscribe", "topic": topic}, ensure_ascii=False))

            async for raw in ws:
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if event.get("op") != "publish":
                    continue
                topic = event.get("topic", "")
                if topic not in FEEDBACK_TOPICS:
                    continue
                yield normalize_feedback_message(topic, event.get("msg") or {})
    except Exception as exc:
        yield {"data_type": "error", "message": f"rosbridge feedback failed: {exc}"}


rosbridge_dispatcher = RosbridgeDispatcher()
