from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any, AsyncIterator, Dict

try:
    import websockets
except ImportError:  # pragma: no cover - depends on deployment environment
    websockets = None


ROSBRIDGE_URL = os.getenv("ROSBRIDGE_URL", "ws://localhost:9010")

# ROS_COMM_MODULE_ID = 17  # 【已删除】V2 改为 module_id 外部传入，不再写死

FINE_TUNING_TOPIC_MAP: Dict[str, Dict[str, Any]] = {
    "rotation": {
        "topic": "/control/adjust_rotation_cmd",
        "message_type": "robot_control_backend/msg/RotationCmd",
    },
    "swing": {
        "topic": "/control/adjust_swing_cmd",
        "message_type": "robot_control_backend/msg/SwingCmd",
    },
    "telescopic": {
        "topic": "/control/adjust_telescopic_cmd",
        "message_type": "robot_control_backend/msg/TelescopicCmd",
    },
}
# 说明：V2 已删除 device_id=33/34/35，device_id 由上层调用方传入并校验（1~20）

FEEDBACK_TOPICS: Dict[str, str] = {
    "/hardware/rotation_feedback": "robot_control_backend/msg/RotationFeedback",
    "/hardware/swing_feedback": "robot_control_backend/msg/SwingFeedback",
    "/hardware/telescope_feedback": "robot_control_backend/msg/TelescopicFeedback",
    "/hardware/sensor_feedback": "robot_control_backend/msg/SensorFeedback",
    "/hardware/imu_angles": "robot_control_backend/msg/ImuFeedback",
}

DRAWING_PATH_TOPIC = "/frontend_pointcloud_topic"
DRAWING_PATH_MESSAGE_TYPE = "std_msgs/msg/String"
MODULE_CONFIRM_TOPIC = "/control/module_cmd"
MODULE_CONFIRM_MESSAGE_TYPE = "robot_control_backend/msg/IntCmd"
MODULE_CONFIRM_SUCCESS_TOPIC = "/hardware/module_confirm_success"
MODULE_CONFIRM_FEEDBACK_TOPIC = "/hardware/web_module_cmd"

# V2 全轴号标签：旋转 J1(1,5,9,13,17)、摆动 J2(2,6,10,14,18)、伸缩 J4(4,8,12,16,20)，J3 空置
FEEDBACK_LABELS: Dict[int, tuple] = {
    1: ("axis_encoder", "臂1·旋转轴编码器"),
    2: ("axis_encoder", "臂1·摆动轴编码器"),
    4: ("axis_encoder", "臂1·伸缩轴编码器"),
    5: ("axis_encoder", "臂2·旋转轴编码器"),
    6: ("axis_encoder", "臂2·摆动轴编码器"),
    8: ("axis_encoder", "臂2·伸缩轴编码器"),
    9: ("axis_encoder", "臂3·旋转轴编码器"),
    10: ("axis_encoder", "臂3·摆动轴编码器"),
    12: ("axis_encoder", "臂3·伸缩轴编码器"),
    13: ("axis_encoder", "臂4·旋转轴编码器"),
    14: ("axis_encoder", "臂4·摆动轴编码器"),
    16: ("axis_encoder", "臂4·伸缩轴编码器"),
    17: ("axis_encoder", "臂5·旋转轴编码器"),
    18: ("axis_encoder", "臂5·摆动轴编码器"),
    20: ("axis_encoder", "臂5·伸缩轴编码器"),
}
# 臂级 21~25（IMU/压力/失压）在 normalize_feedback_message 中按话题区分


class RosbridgeError(RuntimeError):
    pass


def _stamp() -> Dict[str, int]:
    """ROS2 Header.stamp 字段名为 sec / nanosec（ROS1 是 secs/nsecs）"""
    now = time.time()
    secs = int(now)
    nanosec = int((now - secs) * 1_000_000_000)
    return {"sec": secs, "nanosec": nanosec}


def build_fine_tuning_publish_payload(
    parameter_name: str, position: float, module_id: int, device_id: int
) -> Dict[str, Any]:
    mapping = FINE_TUNING_TOPIC_MAP.get(parameter_name)
    if mapping is None:
        raise RosbridgeError(f"unsupported fine-tuning parameter: {parameter_name}")

    module_id = int(module_id)
    device_id = int(device_id)
    if not 1 <= device_id <= 20:
        raise RosbridgeError(f"invalid device_id for fine-tuning: {device_id} (must be 1~20)")

    return {
        "topic": mapping["topic"],
        "message_type": mapping["message_type"],
        "message": {
            "header": {"stamp": _stamp(), "frame_id": ""},
            "module_id": module_id,
            "device_id": device_id,
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

    # 臂级 21~25：按话题区分 IMU / 压力
    if device_id >= 21:
        if "imu" in topic:
            data_type, feedback_type = "imu_pose", f"臂{device_id - 20}·陀螺仪姿态"
        else:
            data_type, feedback_type = "pressure_sensor", f"臂{device_id - 20}·压力传感器"
    else:
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
            for topic, msg_type in FEEDBACK_TOPICS.items():
                await ws.send(json.dumps({
                    "op": "subscribe",
                    "topic": topic,
                    "type": msg_type,
                }, ensure_ascii=False))

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