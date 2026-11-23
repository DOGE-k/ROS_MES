# app/ros/rosbridge.py
"""rosbridge WebSocket 通道（ROS1/ROS2 通用实现）。

协议操作（advertise/publish/subscribe）两代 ROS 完全一致，
消息类型串与 header.stamp 字段名等差异由 `app.ros.profile.RosProfile` 承载。
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from typing import Any, AsyncIterator, Dict, List

try:
    import websockets
except ImportError:  # pragma: no cover - depends on deployment environment
    websockets = None

from app.core.config import settings
from app.ros.base import RosDispatcher, RosbridgeError
from app.ros.normalizer import normalize_feedback_message
from app.ros.profile import RosProfile, get_active_profile

logger = logging.getLogger(__name__)

# V2.1：module_id / device_id 不做静态配置，全部取自前端微调请求（record.module_id / record.device_id）
# device_id 即 AXIS 寻址单元（V2.1 三轴布局）：1~15=轴号（每臂 关节1=旋转/2=摆动/3=伸缩，
# 臂1=1/2/3、臂2=4/5/6 … 臂5=13/14/15），21~25=臂级

# V2：全局急停为系统级指令，module_id=0 / device_id=0（不使用静态模块编号），
# softstop_node 收到后转发 position=[0x01] 全局急停
SYSTEM_MODULE_ID = 0
SYSTEM_DEVICE_ID = 0

# 急停类指令（急停/解除/局部停）不等待设备回执，必须靠传输层尽量保证送达：
# advertise 后留时间让 rosbridge 建好 Publisher，publish 后留时间让帧交给 rospy，
# 再优雅关闭连接。整条链路失败按次数重试，全部失败才返回 False。
STOP_ADVERTISE_WAIT_S = 0.1
STOP_PUBLISH_DRAIN_S = 0.1
STOP_SEND_RETRIES = 3


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


def build_axis_zero_publish_payload(
    module_id: int,
    unit_id: int,
    profile: RosProfile | None = None,
) -> Dict[str, Any]:
    """构造人工校零命令：device_id=0，position=[arm]，仅复位该臂 ROS 软件基准。"""
    profile = profile or get_active_profile()
    arm = resolve_arm_from_unit_id(unit_id)
    module_id = int(module_id)
    if module_id <= 0:
        raise RosbridgeError(f"校零 module_id={module_id} 非法（必须由前端下发正整数模块号）")
    return {
        "topic": profile.topics["axis_zero"],
        "message_type": profile.message_type("IntCmd"),
        "message": {
            "header": {"stamp": _stamp(profile), "frame_id": ""},
            "module_id": module_id,
            "device_id": SYSTEM_DEVICE_ID,
            "position": [arm],
        },
        "arm": arm,
    }


class _AdjustCommandLink:
    """微调指令常驻链路：独立线程跑常驻事件循环，维持一条 WS 长连接。

    背景：微调走同步 dispatch，原先每次 asyncio.run() 新建事件循环、跑完即销毁，
    常驻连接无法跨调用存活；且每次 advertise→sleep(0.1)→publish→立即关连接，
    存在 rosbridge 订阅握手窗口——订阅者未就绪时 publish 的帧会被丢弃
    （±70 旋转 / -10 伸缩偶发丢失的根因）。

    本类在独立线程里跑一个常驻 asyncio 事件循环，维持一条 WS 长连接：
      - 启动即 advertise 三个微调话题 + 订阅 adjust_ack 回执话题，之后只发 publish，
        不再有每次的握手窗口；
      - send() 通过 run_coroutine_threadsafe 提交到该循环复用长连接；
      - 每条微调带 request_id，control_node 回 adjust_ack 才算确认送达；
        超时/断链标记"未确认"，**不自动重发运动指令**（避免机械臂重复动作）。
    """

    def __init__(self, profile: RosProfile, url: str, timeout: float = 3.0):
        self._profile = profile
        self._url = url
        self._timeout = timeout
        self._cmd_topics = [
            (m["topic"], m["message_type"]) for m in _fine_tuning_topic_map(profile).values()
        ]
        self._ack_topic = profile.topics["adjust_ack"]
        self._ack_type = profile.message_type("AdjustAck")
        self._loop = None
        self._thread = None
        self._ws = None
        self._ready = None                # asyncio.Event（常驻循环内）：连接+订阅就绪
        self._loop_up = threading.Event()  # 常驻事件循环已启动
        self._pending = {}                # request_id -> asyncio.Future（仅常驻循环内访问）
        self._req_lock = threading.Lock()
        self._req_seq = 0
        self._start_lock = threading.Lock()
        self._started = False

    def start(self) -> None:
        with self._start_lock:
            if self._started:
                return
            self._started = True
            self._thread = threading.Thread(
                target=self._thread_main, name="adjust-cmd-link", daemon=True)
            self._thread.start()

    def _thread_main(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._ready = asyncio.Event()
        self._loop_up.set()
        self._loop.create_task(self._connection_manager())
        self._loop.run_forever()

    def _next_request_id(self) -> int:
        with self._req_lock:
            self._req_seq += 1
            # 秒级时间戳拼序号，跨进程重启也基本唯一，且在 uint64 范围内
            return int(time.time()) * 100000 + (self._req_seq % 100000)

    # ---------- 对外同步接口（dispatch 工作线程调用）----------
    def send(self, payload: Dict[str, Any], timeout: float | None = None) -> Dict[str, Any]:
        self.start()
        if not self._loop_up.wait(5.0):
            raise RosbridgeError("微调常驻链路启动超时")
        timeout = timeout or self._timeout
        request_id = self._next_request_id()
        msg = dict(payload)
        msg["message"] = {**payload["message"], "request_id": request_id}
        coro = self._send_and_confirm(msg, request_id, timeout)
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout * 2 + 10.0)

    # ---------- 以下仅在常驻事件循环内运行 ----------
    async def _send_and_confirm(self, payload, request_id, timeout):
        try:
            await asyncio.wait_for(self._ready.wait(), timeout)
        except asyncio.TimeoutError:
            return {"sent": False, "confirmed": False, "request_id": request_id,
                    "confirmation_status": "unconfirmed",
                    "error": "微调常驻链路未连接到 rosbridge"}
        fut = self._loop.create_future()
        self._pending[request_id] = fut
        try:
            publish_json = json.dumps(
                {"op": "publish", "topic": payload["topic"], "msg": payload["message"]},
                ensure_ascii=False)
            ws = self._ws
            if ws is None:
                # _ready 置位后连接仍可能被重连置空：显式判空，避免 NoneType.send
                return {"sent": False, "confirmed": False, "request_id": request_id,
                        "confirmation_status": "unconfirmed", "error": "常驻链路连接已断开，未发送"}
            await ws.send(publish_json)
            ack = await asyncio.wait_for(fut, timeout)
            result = int(ack.get("result", 0))
            return {
                "sent": True, "confirmed": True, "request_id": request_id,
                "ack": ack, "result": result,
                "confirmation_status": "confirmed" if result == 0 else "rejected",
            }
        except asyncio.TimeoutError:
            return {"sent": True, "confirmed": False, "request_id": request_id,
                    "confirmation_status": "unconfirmed",
                    "error": "未收到控制节点 adjust_ack 回执，指令可能未送达；不自动重发，请核实后手动重试"}
        except Exception as exc:
            return {"sent": False, "confirmed": False, "request_id": request_id,
                    "confirmation_status": "unconfirmed", "error": str(exc)}
        finally:
            self._pending.pop(request_id, None)

    async def _connection_manager(self):
        while True:
            try:
                async with websockets.connect(self._url, close_timeout=1, open_timeout=3) as ws:
                    self._ws = ws
                    # 常驻 advertise 三个微调话题 + 订阅回执话题，只建一次
                    for topic, mtype in self._cmd_topics:
                        await ws.send(json.dumps({"op": "advertise", "topic": topic, "type": mtype}))
                    await ws.send(json.dumps(
                        {"op": "subscribe", "topic": self._ack_topic, "type": self._ack_type}))
                    await asyncio.sleep(0.2)  # 等 rosbridge 建好 publisher/subscriber
                    self._ready.set()
                    async for raw in ws:
                        self._on_message(raw)
            except Exception as exc:
                logger.error("[adjust-link] 连接异常：%s", exc)
            finally:
                self._ws = None
                if self._ready is not None:
                    self._ready.clear()
                self._fail_all_pending("微调常驻链路断开，指令未确认")
            await asyncio.sleep(1.0)

    def _on_message(self, raw):
        try:
            event = json.loads(raw)
        except Exception:
            return
        if event.get("op") != "publish" or event.get("topic") != self._ack_topic:
            return
        msg = event.get("msg") or {}
        request_id = msg.get("request_id")
        fut = self._pending.get(request_id)
        if fut is not None and not fut.done():
            fut.set_result(msg)

    def _fail_all_pending(self, error):
        for fut in list(self._pending.values()):
            if not fut.done():
                fut.set_exception(RuntimeError(error))
        self._pending.clear()


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
        # 微调常驻链路：实例在构造时创建（不耗资源），后台线程与长连接在首次 send 时才 start
        self._adjust_link = _AdjustCommandLink(profile, self.url)

    def dispatch(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if action not in {"fine_tuning", "drawing_path", "module_confirm", "axis_zero"}:
            raise RosbridgeError(f"unsupported rosbridge action: {action}")
        if action == "fine_tuning":
            # 微调走常驻链路：长连接 + 常驻 advertise + adjust_ack 回执确认送达
            return self._dispatch_fine_tuning(payload)
        return asyncio.run(self.publish(action, payload))

    def _dispatch_fine_tuning(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        result = self._adjust_link.send(payload)
        return {
            "sent": result.get("sent", False),
            "mode": "rosbridge_persistent",
            "url": self.url,
            "action": "fine_tuning",
            "payload": payload,
            "confirmed": result.get("confirmed"),
            "confirmation_status": result.get("confirmation_status"),
            "request_id": result.get("request_id"),
            "ack": result.get("ack"),
            "error": result.get("error"),
        }

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
            async with websockets.connect(self.url, close_timeout=1, open_timeout=3) as ws:
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

    async def _publish_stop_frames(self, frames: List[Dict[str, Any]], tag: str) -> bool:
        """发送急停类系统指令（IntCmd）：advertise → 等待 → publish → 停留 → 优雅关闭。

        返回 True 仅表示每帧都已写出并经过 rosbridge 的处理窗口，**不代表设备已执行**；
        急停/解除/局部停三个话题在 ROS 端没有应用层回执，因此用重试兜底。
        """
        if websockets is None:
            logger.error("[%s] websockets 库未安装，无法发送指令", tag)
            return False

        message_type = self.profile.message_type("IntCmd")
        topics = list(dict.fromkeys(frame["topic"] for frame in frames))
        last_error: Exception | None = None

        for attempt in range(1, STOP_SEND_RETRIES + 1):
            try:
                async with websockets.connect(
                    self.url, close_timeout=1, open_timeout=3
                ) as ws:
                    for topic in topics:
                        await asyncio.wait_for(
                            ws.send(json.dumps(
                                {"op": "advertise", "topic": topic, "type": message_type},
                                ensure_ascii=False,
                            )),
                            self.timeout,
                        )
                    # Publisher 建立需要时间，过早 publish 会被 rosbridge 当成未注册话题丢弃
                    await asyncio.sleep(STOP_ADVERTISE_WAIT_S)
                    for frame in frames:
                        await asyncio.wait_for(
                            ws.send(json.dumps(
                                {"op": "publish", "topic": frame["topic"], "msg": frame["msg"]},
                                ensure_ascii=False,
                            )),
                            self.timeout,
                        )
                    # 关闭前留出处理窗口：连接一关，未交给 rospy 的帧就会丢
                    await asyncio.sleep(STOP_PUBLISH_DRAIN_S)
                return True
            except asyncio.TimeoutError as exc:
                last_error = exc
            except Exception as exc:
                last_error = exc
            if attempt < STOP_SEND_RETRIES:
                await asyncio.sleep(0.05 * attempt)

        logger.error("[%s] 发送失败（已重试 %s 次）: %s", tag, STOP_SEND_RETRIES, last_error)
        return False

    async def publish_softstop(self) -> bool:
        """全局急停：/control/softstop 的 typeless publish（与 ROS1 现网行为一致）。"""
        softstop_topic = self.profile.topics["softstop"]
        frames = [{
            "topic": softstop_topic,
            "msg": {
                "header": {"stamp": _zero_stamp(self.profile), "frame_id": ""},
                "module_id": SYSTEM_MODULE_ID,
                "device_id": SYSTEM_DEVICE_ID,
                "position": [0x01],
            },
        }]
        if await self._publish_stop_frames(frames, "急停"):
            logger.warning("🔴 急停指令已发送: %s", softstop_topic)
            return True
        logger.error("[紧急故障] 急停指令发送失败（已重试 %s 次）: %s", STOP_SEND_RETRIES, softstop_topic)
        return False

    async def publish_stop_release(self) -> bool:
        """急停解除：/control/softstop_release（softstop_node 转发 /arm/cmd_vel [0x04]）。"""
        release_topic = self.profile.topics["softstop_release"]
        frames = [{
            "topic": release_topic,
            "msg": {
                "header": {"stamp": _zero_stamp(self.profile), "frame_id": ""},
                "module_id": SYSTEM_MODULE_ID,
                "device_id": SYSTEM_DEVICE_ID,
                "position": [0x01],
            },
        }]
        if await self._publish_stop_frames(frames, "急停解除"):
            logger.warning("🟡 急停解除指令已发送: %s", release_topic)
            return True
        logger.error("[紧急故障] 急停解除指令发送失败（已重试 %s 次）: %s", STOP_SEND_RETRIES, release_topic)
        return False

    async def publish_local_stop(self, *, scope: str, module_id: int, device_id: int | None = None) -> bool:
        """局部停：直发 /arm/cmd_vel 系统级指令，经 softstop_node 之外的同一话题进入 hardware_node。

        - module: position=[0x08, module_id]，device_id=0 → CAN 0x00000008 | SEG<<18，只停该组
        - arm:    device_id=臂号，对该臂 3 根轴各发一帧 position=[0x0C, 1]
        - axis:   device_id=轴号，position=[0x0C, 1] → 单轴停止帧
        不经过 softstop_node，是因为它只订阅全局急停话题并固定转发 [0x01]，会把局部停升级成全停。
        """
        if websockets is None:
            logger.error("[局部停] websockets 库未安装，无法发送指令")
            return False

        topic = self.profile.topics["arm_cmd"]
        if scope == "module":
            targets = [{"module_id": int(module_id), "device_id": SYSTEM_DEVICE_ID,
                        "position": [0x08, int(module_id)]}]
        elif scope in ("arm", "axis") and device_id is not None:
            if scope == "arm":
                # 臂停 = 该臂 3 根轴依次发 0x0C；同组其他臂不受影响
                arm = int(device_id)
                axes = list(range((arm - 1) * 3 + 1, arm * 3 + 1))
            else:
                axes = [int(device_id)]
            targets = [{"module_id": int(module_id), "device_id": axis, "position": [0x0C, 1]}
                       for axis in axes]
        else:
            logger.warning("[局部停] 未知 scope 或缺 device_id：%r/%r", scope, device_id)
            return False

        frames = [{
            "topic": topic,
            "msg": {
                "header": {"stamp": _zero_stamp(self.profile), "frame_id": ""},
                **payload,
            },
        } for payload in targets]

        if not await self._publish_stop_frames(frames, "局部停"):
            return False
        for payload in targets:
            logger.warning("🛑 局部停指令已发送: %s scope=%s device_id=%s position=%s",
                           topic, scope, payload["device_id"], payload["position"])
        return True

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

    async def stream_feedback(
        self,
        *,
        ready: asyncio.Event | None = None,
        max_reconnects: int | None = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """持续读取反馈；连接断开后自动重连。

        max_reconnects 默认为 None（无限重连，生产语义）；测试用它把流收敛成有限长度，
        否则一个永远返回空 socket 的测试替身会让重连循环永不结束。
        """
        if websockets is None:
            yield {"data_type": "error", "message": "missing websockets dependency"}
            return

        feedback_topics = [
            self.profile.topics[key]
            for key in ("feedback_rotation", "feedback_swing", "feedback_telescope",
                        "feedback_sensor", "feedback_imu",
                        "feedback_pressure_avg", "feedback_vacuum_loss",
                        "feedback_cmd_ack", "feedback_axis_status", "feedback_arrive",
                        "feedback_stop", "feedback_fault", "feedback_limit",
                        "feedback_can_fault")
        ]

        # 自动重连：ROS/rosbridge 瞬时抖动不再让反馈流终止。
        # 不 yield data_type=="error"——finetuning 批次的 consume 会把 error 当 Halt 杀掉在途批次；
        # 这里静默重连，由批次自身的 preflight/arrive 超时做最终兜底，瞬时断开可恢复。
        #
        # 退避只在「真正收到过数据」后才清零：否则「连上就被对端关掉」会让 attempt 恒为 0，
        # 延迟永远是 1s，变成对 rosbridge 的重连风暴。
        attempt = 0
        rounds = 0
        while True:
            received = False
            try:
                async with websockets.connect(self.url, close_timeout=1, open_timeout=3) as ws:
                    for topic in feedback_topics:
                        await ws.send(json.dumps({"op": "subscribe", "topic": topic}, ensure_ascii=False))
                    if ready is not None:
                        ready.set()

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
                        received = True
                        attempt = 0  # 证明连接可用，退避计数清零
                        yield feedback
                    # async for 正常退出 = 对端关闭连接，落入下方重连。
            except asyncio.CancelledError:
                raise  # 批次结束 reader.cancel()：正常退出，不重连
            except Exception as exc:
                logger.error("[rosbridge] 反馈连接异常：%s", exc)
            rounds += 1
            if not received:
                # 这次连接一条数据都没读到：计入退避，避免「连上即断」变成重连风暴。
                attempt += 1
            if max_reconnects is not None and rounds > max_reconnects:
                logger.warning("[rosbridge] 反馈连接已轮询 %s 次，达到上限，停止重连", rounds)
                return
            delay = min(1.0 * attempt, 5.0)
            logger.warning("[rosbridge] 反馈连接断开，%.1fs 后自动重连（第 %s 次）", delay, attempt)
            await asyncio.sleep(delay)




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
        from app.ros.runtime_settings import runtime_settings
        from app.ros.mock_client import MockRosClient
        self.connection_settings = runtime_settings.snapshot()
        config = self.connection_settings
        self.revision = config["revision"]
        self.emergency_mode = config["emergency_mode"]

        def client(mode, url):
            value = MockRosClient(self.profile) if mode == "mock" else RosbridgeClient(self.profile, url=url)
            value.execution_mode = mode
            value.safety_mode = self.emergency_mode
            value.connection_revision = self.revision
            value.finetuning_preflight_enabled = config["finetuning_preflight_enabled"]
            return value

        self.client = client(config["ros_mode"], config["ros_url"])
        self.drawing_client = client("real" if config["drawing_mode"] == "real" else "mock", config["drawing_ros_url"] or config["ros_url"])
        self.emergency_client = client(self.emergency_mode, config["emergency_ros_url"] or config["ros_url"])
        self._watcher = _RosbridgeStatusWatcher(self.profile, self.client.url)

    def dispatch(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        from app.ros.runtime_settings import runtime_settings
        with runtime_settings.operation(self.revision):
            if action == "drawing_path" and self.connection_settings["drawing_mode"] == "skip":
                raise RosbridgeError("当前选择不使用图纸，不允许下发图纸")
            from app.db import models
            with runtime_settings.sessions() as db:
                safety = db.get(models.ControlSafety, 2 if self.emergency_mode == "mock" else 1)
                if safety and safety.state.startswith("stop"):
                    raise RosbridgeError("当前急停联锁尚未解除，禁止模块确认或任务下发")
            if action == "module_confirm":
                clients = {item.url: item for item in (self.client, self.drawing_client) if item.execution_mode == "real"}
                results = [item.dispatch(action, payload) for item in (list(clients.values()) or [self.client])]
                return {**results[0], "confirmed": all(item.get("confirmed") is True for item in results), "destinations": results}
            return (self.drawing_client if action == "drawing_path" else self.client).dispatch(action, payload)

    def operation(self):
        from app.ros.runtime_settings import runtime_settings
        return runtime_settings.operation(self.revision)

    async def test_serial_connection(self) -> dict:
        if self.client.execution_mode == "mock":
            return {"success": True, "connected": True, "simulated": True,
                    "message": "模拟串口检查成功，未访问真实串口", "bytes_received": 0}
        return await super().test_serial_connection()

    async def get_hardware_status(self) -> dict:
        if self.client.execution_mode == "mock":
            return {"joints": [0.0] * 15, "status": "simulated", "timestamp": time.time(), "simulated": True}
        return await super().get_hardware_status()

    async def stream_robot_data(self):
        if self.client.execution_mode == "mock":
            while True:
                yield json.dumps({"simulated": True, "status": "simulated", "message": "后端模拟，未连接设备"}, ensure_ascii=False)
                await asyncio.sleep(1)
        else:
            async for item in super().stream_robot_data():
                yield item

    async def stream_feedback(self) -> AsyncIterator[Dict[str, Any]]:
        from app.ros.runtime_settings import runtime_settings
        async for feedback in self.client.stream_feedback():
            if runtime_settings.snapshot()["revision"] != self.revision:
                yield {"data_type": "config_changed", "message": "连接配置已变更，请重新确认机械臂"}
                return
            yield {**feedback, "simulated": self.client.execution_mode == "mock", "connection_revision": self.revision}

    async def trigger_emergency_stop(self) -> bool:
        return await self.emergency_client.publish_softstop()

    async def release_emergency_stop(self) -> bool:
        return await self.emergency_client.publish_stop_release()

    async def trigger_local_stop(self, *, scope: str, module_id: int, device_id: int | None = None) -> bool:
        """局部停：只停目标模块或目标轴，不清除全局联锁，也不影响其他模块。"""
        return await self.emergency_client.publish_local_stop(
            scope=scope, module_id=module_id, device_id=device_id)

    def start_native_node(self) -> None:
        """启动 /robot_status 后台订阅（测试页状态来源；子类可叠加各自的后台通道）。"""
        if self.client.execution_mode == "real":
            self._watcher.start()

    def stop(self) -> None:
        self._watcher.stop()

    def publish_web_cmd(self, command: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        # 测试页通道统一走 rosbridge（干净 venv 无 rospy 也能用，ROS1/ROS2 行为一致）
        if self.client.execution_mode == "mock":
            return {"mode": "mock", "simulated": True, "command": command, "payload": payload}
        return asyncio.run(self.client.publish_web_cmd(command, payload))

    @property
    def native_status(self) -> Dict[str, Any]:
        if self.client.execution_mode == "mock":
            return {"robot_status": "simulated", "ros_ready": False, "simulated": True, "message": "后端模拟，未连接设备"}
        return self._watcher.snapshot()
