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


ROSBRIDGE_URL = os.getenv("ROSBRIDGE_URL", "ws://localhost:9010")
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
    "/hardware/imu_angles",
]

DRAWING_PATH_TOPIC = "/frontend_pointcloud_topic"
DRAWING_PATH_MESSAGE_TYPE = "std_msgs/String"
MODULE_CONFIRM_TOPIC = "/control/module_cmd"
MODULE_CONFIRM_MESSAGE_TYPE = "robot_control_backend/IntCmd"
MODULE_CONFIRM_SUCCESS_TOPIC = "/control/module_confirm_success"
MODULE_CONFIRM_FEEDBACK_TOPIC = "/hardware/web_module_cmd"

FEEDBACK_LABELS = {
    33: ("axis_encoder", "旋转轴编码器"),
    34: ("axis_encoder", "摆动轴编码器"),
    35: ("axis_encoder", "伸缩轴编码器"),
    41: ("rotation_axis_encoder", "旋转轴编码器"),
    42: ("swing_axis_encoder", "摆动轴编码器"),
    43: ("telescope_axis_encoder", "伸缩轴编码器"),
    49: ("pressure_sensor", "压力传感器"),
    50: ("imu_pose", "陀螺仪姿态"),
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


def build_drawing_path_publish_payload(file_path: str) -> Dict[str, Any]:
    return {
        "topic": DRAWING_PATH_TOPIC,
        "message_type": DRAWING_PATH_MESSAGE_TYPE,
        "message": {
            "data": json.dumps({"file_path": file_path}, ensure_ascii=False, separators=(",", ":")),
        },
    }


def build_module_confirm_publish_payload(module_id: int) -> Dict[str, Any]:
    return {
        "topic": MODULE_CONFIRM_TOPIC,
        "message_type": MODULE_CONFIRM_MESSAGE_TYPE,
        "message": {
            "header": {"stamp": _stamp(), "frame_id": ""},
            "module_id": int(module_id),
            "device_id": 0,
            "position": [100],
        },
    }


def _position_value(value: Any) -> float:
    if isinstance(value, list):
        return float(value[0]) if value else 0.0
    return float(value)


def _float_value(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def normalize_feedback_message(topic: str, msg: Dict[str, Any]) -> Dict[str, Any]:
    device_id = int(msg.get("device_id", 0))
    data_type, feedback_type = FEEDBACK_LABELS.get(device_id, ("unknown", "unknown feedback"))
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

    if data_type == "imu_pose":
        normalized.update(
            {
                "swing_angle": _float_value(msg.get("swing_angle")),
                "rotation_angle": _float_value(msg.get("rotation_angle")),
                "x": _float_value(msg.get("x")),
                "y": _float_value(msg.get("y")),
                "z": _float_value(msg.get("z")),
            }
        )

    return normalized


class RosbridgeDispatcher:
    def __init__(self, url: str = ROSBRIDGE_URL, timeout: float = 5.0):
        self.url = url
        self.timeout = timeout

    def dispatch(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if action not in {"fine_tuning", "drawing_path", "module_confirm"}:
            raise RosbridgeError(f"unsupported rosbridge action: {action}")
        return asyncio.run(self.publish(action, payload))

    async def publish(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if websockets is None:
            raise RosbridgeError("missing websockets dependency")

        advertise_json = json.dumps(
            {
                "op": "advertise",
                "topic": payload["topic"],
                "type": payload["message_type"],
            },
            ensure_ascii=False,
        )
        publish_json = json.dumps(
            {
                "op": "publish",
                "topic": payload["topic"],
                "msg": payload["message"],
            },
            ensure_ascii=False,
        )
        confirm_msg = None

        try:
            async with websockets.connect(self.url, close_timeout=1) as ws:
                if action == "module_confirm":
                    for confirm_topic in (MODULE_CONFIRM_SUCCESS_TOPIC, MODULE_CONFIRM_FEEDBACK_TOPIC):
                        subscribe_json = json.dumps(
                            {
                                "op": "subscribe",
                                "topic": confirm_topic,
                                "type": MODULE_CONFIRM_MESSAGE_TYPE,
                            },
                            ensure_ascii=False,
                        )
                        await asyncio.wait_for(ws.send(subscribe_json), self.timeout)

                await asyncio.wait_for(ws.send(advertise_json), self.timeout)
                await asyncio.sleep(0.1)
                await asyncio.wait_for(ws.send(publish_json), self.timeout)

                if action == "module_confirm":
                    confirm_msg = await self._wait_for_module_confirm_success(ws, payload)
        except ConnectionRefusedError as exc:
            raise RosbridgeError(f"unable to connect to rosbridge: {self.url}") from exc
        except asyncio.TimeoutError as exc:
            raise RosbridgeError(f"rosbridge timeout while waiting for {action}: {self.url}") from exc
        except Exception as exc:
            raise RosbridgeError(f"rosbridge publish failed: {exc}. URL: {self.url}") from exc

        return {
            "sent": True,
            "mode": "rosbridge",
            "url": self.url,
            "action": action,
            "payload": payload,
            "confirmed": action != "module_confirm" or confirm_msg is not None,
            "confirm_topic": MODULE_CONFIRM_SUCCESS_TOPIC if action == "module_confirm" else None,
            "confirm_message": confirm_msg,
        }

    async def _wait_for_module_confirm_success(self, ws: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
        expected_module_id = int(payload["message"]["module_id"])

        while True:
            raw = await asyncio.wait_for(ws.recv(), self.timeout)
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if event.get("op") != "publish":
                continue
            topic = event.get("topic")
            if topic not in {MODULE_CONFIRM_SUCCESS_TOPIC, MODULE_CONFIRM_FEEDBACK_TOPIC}:
                continue

            msg = event.get("msg") or {}
            module_id = int(msg.get("module_id", -1))
            device_id = int(msg.get("device_id", -1))
            position = msg.get("position") or []

            if (
                topic == MODULE_CONFIRM_FEEDBACK_TOPIC
                and module_id == expected_module_id
                and device_id == 0
                and position
                and int(position[0]) == 1
            ):
                raise RosbridgeError(f"module confirm failed: module_id={expected_module_id}")

            if (
                module_id == expected_module_id
                and device_id == 0
                and position
                and int(position[0]) == 100
            ):
                return msg


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
