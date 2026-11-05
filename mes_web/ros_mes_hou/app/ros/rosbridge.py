# app/ros/rosbridge.py
"""rosbridge WebSocket 通道（ROS1/ROS2 通用实现）。

协议操作（advertise/publish/subscribe）两代 ROS 完全一致，
消息类型串与 header.stamp 字段名等差异由 `app.ros.profile.RosProfile` 承载。
"""
from __future__ import annotations

import asyncio
import json
import threading
import time
from typing import Any, AsyncIterator, Dict

try:
    import websockets
except ImportError:  # pragma: no cover - depends on deployment environment
    websockets = None

from app.core.config import settings
from app.ros.base import RosDispatcher, RosbridgeError
from app.ros.normalizer import normalize_feedback_message
from app.ros.profile import RosProfile, get_active_profile

# V2.1：module_id / device_id 不做静态配置，全部取自前端微调请求（record.module_id / record.device_id）
# device_id 即 AXIS 寻址单元（V2.1 三轴布局）：1~15=轴号（每臂 关节1=旋转/2=摆动/3=伸缩，
# 臂1=1/2/3、臂2=4/5/6 … 臂5=13/14/15），21~25=臂级

# V2：全局急停为系统级指令，module_id=0 / device_id=0（不使用静态模块编号），
# softstop_node 收到后转发 position=[0x01] 全局急停
SYSTEM_MODULE_ID = 0
SYSTEM_DEVICE_ID = 0


def _stamp(profile: RosProfile) -> Dict[str, int]:
    now = time.time()
    secs = int(now)
    nsecs = int((now - secs) * 1_000_000_000)
    first, second = profile.stamp_fields
    return {first: secs, second: nsecs}


def _zero_stamp(profile: RosProfile) -> Dict[str, int]:
    first, second = profile.stamp_fields
    return {first: 0, second: 0}


def _fine_tuning_topic_map(profile: RosProfile) -> Dict[str, Dict[str, Any]]:
    return {
        "rotation": {
            "topic": profile.topics["fine_tuning_rotation"],
            "message_type": profile.message_type("RotationCmd"),
        },
        "swing": {
            "topic": profile.topics["fine_tuning_swing"],
            "message_type": profile.message_type("SwingCmd"),
        },
        "telescopic": {
            "topic": profile.topics["fine_tuning_telescopic"],
            "message_type": profile.message_type("TelescopicCmd"),
        },
    }


def build_fine_tuning_publish_payload(
    parameter_name: str,
    position: float,
    module_id: int,
    device_id: int,
    profile: RosProfile | None = None,
) -> Dict[str, Any]:
    """构造微调下发消息。module_id/device_id 必须由前端请求传入，禁止节点内写死。"""
    profile = profile or get_active_profile()
    mapping = _fine_tuning_topic_map(profile).get(parameter_name)
    if mapping is None:
        raise RosbridgeError(f"unsupported fine-tuning parameter: {parameter_name}")
    try:
        module_id = int(module_id)
        device_id = int(device_id)
    except (TypeError, ValueError):
        raise RosbridgeError(
            f"invalid module_id/device_id: module_id={module_id!r}, device_id={device_id!r}")
    # V2.1 三轴布局：微调轴 device_id 必须落在 1~15 轴号空间
    if not (1 <= device_id <= 15):
        raise RosbridgeError(f"微调 device_id={device_id} 非法（V2.1 三轴布局允许轴号 1~15）")
    if module_id <= 0:
        raise RosbridgeError(f"微调 module_id={module_id} 非法（必须由前端下发正整数模块号）")

    # 伸缩轴单位契约（2026-10-25 ROS 端 3ed42f3 定稿）：话题边界两向均为 mm
    # （CAN 层的 0.01mm 由 ROS 节点内部换算），旋转/摆动为度——后端全部原样透传。
    return {
        "topic": mapping["topic"],
        "message_type": mapping["message_type"],
        "message": {
            "header": {"stamp": _stamp(profile), "frame_id": ""},
            "module_id": module_id,
            "device_id": device_id,
            "position": [float(position)],
        },
        "parameter_name": parameter_name,
    }


def build_drawing_path_publish_payload(
    file_path: str,
    profile: RosProfile | None = None,
) -> Dict[str, Any]:
    profile = profile or get_active_profile()
    return {
        "topic": profile.topics["drawing_path"],
        "message_type": profile.std_message_type("String"),
        "message": {
            "data": json.dumps({"file_path": file_path}, ensure_ascii=False, separators=(",", ":")),
        },
    }


def build_module_confirm_publish_payload(
    module_id: int,
    seg: int,
    arm: int,
    profile: RosProfile | None = None,
) -> Dict[str, Any]:
    """构造模块确认握手消息。

    当前会话式握手契约：
      - position = [100, seg, arm]；100=触发握手，seg=下位机组号 0~14，
        arm=全局机械臂编号 1~5；
      - module_id = 业务模块号，无范围限制，ROS 端原样回执用于 ACK 匹配；
      - 回执：module_id 原样返回、device_id=0、position[0]=100 成功 / 1 失败。
    """
    profile = profile or get_active_profile()
    try:
        module_id = int(module_id)
        seg = int(seg)
        arm = int(arm)
    except (TypeError, ValueError) as exc:
        raise RosbridgeError(
            f"模块确认参数非法：module_id={module_id!r}, seg={seg!r}, arm={arm!r}"
        ) from exc
    if module_id <= 0:
        raise RosbridgeError(f"模块确认 module_id={module_id} 非法（必须为正整数）")
    if not (0 <= seg <= 14):
        raise RosbridgeError(f"模块确认 seg={seg} 非法（允许范围 0~14）")
    if not (1 <= arm <= 5):
        raise RosbridgeError(f"模块确认 arm={arm} 非法（允许范围 1~5）")
    return {
        "topic": profile.topics["module_cmd"],
        "message_type": profile.message_type("IntCmd"),
        "message": {
            "header": {"stamp": _stamp(profile), "frame_id": ""},
            "module_id": module_id,
            "device_id": 0,
            "position": [100, seg, arm],
        },
    }


def resolve_module_seg(module_id: int) -> int:
    """从后端显式配置中取得业务模块对应的 ROS SEG。"""
    try:
        module_id = int(module_id)
        mapping = json.loads(settings.ROS_MODULE_SEG_MAP or "{}")
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RosbridgeError("ROS_MODULE_SEG_MAP 不是合法 JSON 映射") from exc
    if not isinstance(mapping, dict):
        raise RosbridgeError("ROS_MODULE_SEG_MAP 必须是 JSON 对象")
    raw_seg = mapping.get(str(module_id), mapping.get(module_id))
    if raw_seg is None:
        raise RosbridgeError(
            f"模块 module_id={module_id} 未配置 ROS SEG 映射，请配置 ROS_MODULE_SEG_MAP"
        )
    try:
        seg = int(raw_seg)
    except (TypeError, ValueError) as exc:
        raise RosbridgeError(f"模块 module_id={module_id} 的 SEG 映射无效：{raw_seg!r}") from exc
    if not (0 <= seg <= 14):
        raise RosbridgeError(f"模块 module_id={module_id} 的 SEG={seg} 超出范围 0~14")
    return seg


def resolve_arm_from_unit_id(unit_id: int) -> int:
    """把业务机械臂 Unit_ID 映射为 ROS arm 1~5。"""
    try:
        unit_id = int(unit_id)
    except (TypeError, ValueError) as exc:
        raise RosbridgeError(f"机械臂 unit_id 非法：{unit_id!r}") from exc
    # 调试数据允许直接使用 1~5；正式种子数据使用 32 的倍数。
    if 1 <= unit_id <= 5:
        return unit_id
    if unit_id > 0 and unit_id % 32 == 0:
        arm = unit_id // 32
        if 1 <= arm <= 5:
            return arm
    raise RosbridgeError(
        f"机械臂 unit_id={unit_id} 无法映射为 arm（支持 1~5 或 32/64/96/128/160）"
    )


class RosbridgeClient:
    """rosbridge WebSocket 一次性客户端：每次下发新建连接，subscribe 后逐条收事件。"""

    def __init__(
        self,
        profile: RosProfile,
        url: str | None = None,
        timeout: float = 5.0,
        module_confirm_timeout: float | None = None,
    ):
        self.profile = profile
        self.url = url or settings.ROSBRIDGE_URL
        self.timeout = timeout
        # 模块确认回执等待上限：V2.1 会话式握手含 30s 等宣告窗口，必须远大于普通超时
        self.module_confirm_timeout = module_confirm_timeout or settings.MODULE_CONFIRM_ACK_WAIT_S

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
        success_topic = self.profile.topics["module_confirm_success"]
        failed_topic = self.profile.topics["module_confirm_failed"]

        try:
            async with websockets.connect(self.url, close_timeout=1) as ws:
                if action == "module_confirm":
                    for confirm_topic in (success_topic, failed_topic):
                        subscribe_json = json.dumps(
                            {
                                "op": "subscribe",
                                "topic": confirm_topic,
                                "type": self.profile.message_type("IntCmd"),
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
            # 普通发布只证明向连接写出了消息，没有等待设备接受或到位。
            "confirmed": confirm_msg is not None if action == "module_confirm" else None,
            "confirmation_status": "confirmed" if action == "module_confirm" else "not_requested",
            "confirm_topic": success_topic if action == "module_confirm" else None,
            "confirm_message": confirm_msg,
        }

    async def _wait_for_module_confirm_success(self, ws: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
        expected_module_id = int(payload["message"]["module_id"])
        success_topic = self.profile.topics["module_confirm_success"]
        failed_topic = self.profile.topics["module_confirm_failed"]

        while True:
            raw = await asyncio.wait_for(ws.recv(), self.module_confirm_timeout)
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if event.get("op") != "publish":
                continue
            topic = event.get("topic")
            if topic not in {success_topic, failed_topic}:
                continue

            msg = event.get("msg") or {}
            module_id = int(msg.get("module_id", -1))
            device_id = int(msg.get("device_id", -1))
            position = msg.get("position") or []

            # 失败码契约：ROS 端 V2.1 已将 RESULT_FAILED 对齐为 1（此前发 -1 的
            # 不一致已由 ROS 端修复），这里维持 position[0]==1 判失败
            if (
                topic == failed_topic
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

    async def publish_softstop(self) -> bool:
        """全局急停：/control/softstop 的 typeless publish（与 ROS1 现网行为一致）。"""
        if websockets is None:
            print("[紧急故障] websockets 库未安装，无法发送急停指令")
            return False

        softstop_topic = self.profile.topics["softstop"]
        emergency_msg = json.dumps(
            {
                "op": "publish",
                "topic": softstop_topic,
                "msg": {
                    "header": {"stamp": _zero_stamp(self.profile), "frame_id": ""},
                    "module_id": SYSTEM_MODULE_ID,
                    "device_id": SYSTEM_DEVICE_ID,
                    "position": [0x01],
                },
            },
            ensure_ascii=False,
        )

        try:
            async with websockets.connect(self.url, close_timeout=1) as ws:
                await asyncio.wait_for(ws.send(emergency_msg), timeout=2.0)
            print(f"[急停] 指令已发送: {softstop_topic}")
            return True
        except asyncio.TimeoutError:
            print("[紧急故障] 急停 WebSocket 发送超时")
            return False
        except Exception as exc:
            print(f"[紧急故障] 急停系统异常: {exc}")
            return False

    async def publish_stop_release(self) -> bool:
        """急停解除：/control/softstop_release（softstop_node 转发 /arm/cmd_vel [0x04]）。"""
        if websockets is None:
            print("[紧急故障] websockets 库未安装，无法发送急停解除指令")
            return False

        release_topic = self.profile.topics["softstop_release"]
        release_msg = json.dumps(
            {
                "op": "publish",
                "topic": release_topic,
                "msg": {
                    "header": {"stamp": _zero_stamp(self.profile), "frame_id": ""},
                    "module_id": SYSTEM_MODULE_ID,
                    "device_id": SYSTEM_DEVICE_ID,
                    "position": [0x01],
                },
            },
            ensure_ascii=False,
        )

        try:
            async with websockets.connect(self.url, close_timeout=1) as ws:
                await asyncio.wait_for(ws.send(release_msg), timeout=2.0)
            print(f"[急停解除] 指令已发送: {release_topic}")
            return True
        except asyncio.TimeoutError:
            print("[紧急故障] 急停解除 WebSocket 发送超时")
            return False
        except Exception as exc:
            print(f"[紧急故障] 急停解除系统异常: {exc}")
            return False

    async def publish_web_cmd(self, command: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """测试通道：向 /web_cmd 发布 JSON 指令（std_msgs/String）。

        与 ROS1 rospy 原生通道（app/ros/ros1/native.py）同一消息契约：
        data = JSON {"command": ..., "payload": ...}。
        """
        if websockets is None:
            raise RosbridgeError("missing websockets dependency")

        topic = self.profile.topics["web_cmd"]
        advertise_json = json.dumps(
            {
                "op": "advertise",
                "topic": topic,
                "type": self.profile.std_message_type("String"),
            },
            ensure_ascii=False,
        )
        publish_json = json.dumps(
            {
                "op": "publish",
                "topic": topic,
                "msg": {
                    "data": json.dumps(
                        {"command": command, "payload": payload}, ensure_ascii=False
                    )
                },
            },
            ensure_ascii=False,
        )

        try:
            async with websockets.connect(self.url, close_timeout=1, open_timeout=3) as ws:
                await asyncio.wait_for(ws.send(advertise_json), self.timeout)
                await asyncio.sleep(0.1)
                await asyncio.wait_for(ws.send(publish_json), self.timeout)
        except ConnectionRefusedError as exc:
            raise RosbridgeError(f"unable to connect to rosbridge: {self.url}") from exc
        except asyncio.TimeoutError as exc:
            raise RosbridgeError(f"rosbridge timeout while publishing web_cmd: {self.url}") from exc
        except Exception as exc:
            raise RosbridgeError(f"rosbridge web_cmd publish failed: {exc}. URL: {self.url}") from exc

        return {"topic": topic, "command": command, "payload": payload, "mode": "rosbridge"}

    async def stream_feedback(self) -> AsyncIterator[Dict[str, Any]]:
        if websockets is None:
            yield {"data_type": "error", "message": "missing websockets dependency"}
            return

        feedback_topics = [
            self.profile.topics[key]
            for key in ("feedback_rotation", "feedback_swing", "feedback_telescope",
                        "feedback_sensor", "feedback_imu",
                        "feedback_pressure_avg", "feedback_vacuum_loss",
                        "feedback_cmd_ack")
        ]

        try:
            async with websockets.connect(self.url, close_timeout=1) as ws:
                for topic in feedback_topics:
                    await ws.send(json.dumps({"op": "subscribe", "topic": topic}, ensure_ascii=False))

                async for raw in ws:
                    try:
                        event = json.loads(raw)
                    except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
                        continue
                    if not isinstance(event, dict) or event.get("op") != "publish":
                        continue
                    topic = event.get("topic", "")
                    if topic not in feedback_topics:
                        continue
                    try:
                        feedback = normalize_feedback_message(topic, event.get("msg"), self.profile.topics)
                    except (TypeError, ValueError, OverflowError):
                        # 单条格式损坏的消息不能终止整条反馈连接。
                        continue
                    yield feedback
        except Exception as exc:
            yield {"data_type": "error", "message": f"rosbridge feedback failed: {exc}"}




class _RosbridgeStatusWatcher:
    """常驻后台线程：订阅 /robot_status，维护 rosbridge 连接状态与最新测试状态。

    - 连接断开自动重连（5 秒间隔），连接状态反映在 connected 标志上；
    - 收到的状态若是 JSON 对象则合并进缓存，普通字符串则记为 robot_status；
    - 所有数据均来自 ROS 端测试程序，缓存恒带 test_data=True 标记。
    ROS1/ROS2 共用（测试页通道已统一走 rosbridge，不再依赖 rospy）。
    """

    RECONNECT_INTERVAL_S = 5.0

    def __init__(self, profile: RosProfile, url: str):
        self._profile = profile
        self._url = url
        self._stop = threading.Event()
        self._thread = None
        self._lock = threading.Lock()
        self.connected = False
        self.latest_status = {
            "robot_status": "unknown",
            "node": "ros_rosbridge",
            "test_data": True,
        }

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._run, name="ros-status-watcher", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {**self.latest_status, "ros_ready": self.connected}

    def _set_connected(self, value: bool) -> None:
        with self._lock:
            self.connected = value

    def _ingest(self, raw: str, status_topic: str) -> None:
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            return
        if event.get("op") != "publish" or event.get("topic") != status_topic:
            return
        data = (event.get("msg") or {}).get("data")
        with self._lock:
            if isinstance(data, str):
                try:
                    parsed = json.loads(data)
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, dict):
                    self.latest_status.update(parsed)
                else:
                    self.latest_status["robot_status"] = data
            self.latest_status["test_data"] = True

    def _run(self) -> None:
        asyncio.run(self._main())

    async def _main(self) -> None:
        status_topic = self._profile.topics["robot_status"]
        subscribe_json = json.dumps(
            {
                "op": "subscribe",
                "topic": status_topic,
                "type": self._profile.std_message_type("String"),
            }
        )

        while not self._stop.is_set():
            try:
                async with websockets.connect(
                    self._url, close_timeout=1, open_timeout=3
                ) as ws:
                    await ws.send(subscribe_json)
                    self._set_connected(True)
                    while not self._stop.is_set():
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
                        except asyncio.TimeoutError:
                            continue  # 周期醒来检查停止标志，保证 stop() 秒级生效
                        self._ingest(raw, status_topic)
            except Exception:
                pass  # 连接失败/中断：走统一重连
            finally:
                self._set_connected(False)

            # 断线后等待重连间隔（可被 stop() 快速打断）
            deadline = time.monotonic() + self.RECONNECT_INTERVAL_S
            while not self._stop.is_set() and time.monotonic() < deadline:
                time.sleep(0.1)


class RosbridgeTransport(RosDispatcher):
    """基于 rosbridge 通道的适配器基类：ROS1/ROS2 共用的下发/反馈/急停实现。

    子类只需声明 `profile` 类属性并按需补充原生节点通道。
    """

    def __init__(self):
        self.client = RosbridgeClient(self.profile)
        self._watcher = _RosbridgeStatusWatcher(self.profile, self.client.url)

    def dispatch(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.client.dispatch(action, payload)

    async def stream_feedback(self) -> AsyncIterator[Dict[str, Any]]:
        async for feedback in self.client.stream_feedback():
            yield feedback

    async def trigger_emergency_stop(self) -> bool:
        return await self.client.publish_softstop()

    async def release_emergency_stop(self) -> bool:
        return await self.client.publish_stop_release()

    def start_native_node(self) -> None:
        """启动 /robot_status 后台订阅（测试页状态来源；子类可叠加各自的后台通道）。"""
        self._watcher.start()

    def stop(self) -> None:
        self._watcher.stop()

    def publish_web_cmd(self, command: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        # 测试页通道统一走 rosbridge（干净 venv 无 rospy 也能用，ROS1/ROS2 行为一致）
        return asyncio.run(self.client.publish_web_cmd(command, payload))

    @property
    def native_status(self) -> Dict[str, Any]:
        return self._watcher.snapshot()

    async def release_emergency_stop(self) -> bool:
        return await self.client.publish_stop_release()
