"""仅在 MES 后端产生明确标记的模拟反馈，绝不连接 rosbridge。"""
from __future__ import annotations

import asyncio
import json
import time
from threading import RLock

from app.core.config import settings
from app.ros.base import RosbridgeError


class MockRobot:
    def __init__(self):
        self.positions, self.running = {}, set()
        self.stopped = False
        self.generation = 0
        self._lock = RLock()

    def telemetry(self, segs):
        with self._lock:
            events = []
            for seg in segs:
                for axis in range(1, 16):
                    busy = (seg, axis) in self.running
                    bits = 257 | (2 if busy else 0) | (128 if self.stopped else 0)
                    events.extend([
                        {"data_type": "axis_status", "module_id": seg, "device_id": axis,
                         "status_bits": bits, "axis_state": 1 if busy else 0, "base_valid": 1},
                        {"data_type": ("rotation_axis_encoder", "swing_axis_encoder", "telescope_axis_encoder")[(axis - 1) % 3],
                         "module_id": seg, "device_id": axis, "position": self.positions.get((seg, axis), 0), "position_valid": True},
                    ])
                for arm in range(1, 6):
                    events.append({"data_type": "pressure_sensor", "module_id": seg, "device_id": 20 + arm,
                                   "position": 0.5, "position_valid": True})
            return events

    async def move(self, payload, publish_event):
        from app.ros.rosbridge import resolve_module_seg
        msg = payload["message"]
        # 下行消息使用业务模块号；反馈和模拟状态必须使用显式映射的 SEG。
        seg, axis = resolve_module_seg(msg["module_id"]), msg["device_id"]
        key = (seg, axis)
        with self._lock:
            if self.stopped or key in self.running:
                raise RosbridgeError("模拟轴急停或忙，未重复发送")
            self.running.add(key)
            generation = self.generation
        publish_event({"data_type": "axis_status", "module_id": seg, "device_id": axis,
                       "status_bits": 259, "axis_state": 1, "base_valid": 1})
        try:
            await asyncio.sleep(0.25)
            with self._lock:
                if generation != self.generation or self.stopped:
                    return
                value = self.positions.get(key, 0) + msg["position"][0]
                self.positions[key] = value
            publish_event({"data_type": "arrive_notification", "module_id": seg, "device_id": axis,
                           "angle": round(value * 100), "pos_error": 0, "status_bits": 5, "flags": 3})
        finally:
            with self._lock:
                self.running.discard(key)

    def stop(self, stopped):
        with self._lock:
            self.stopped = stopped
            self.generation += 1
            self.running.clear()


mock_robot = MockRobot()


class MockRosClient:
    execution_mode = "mock"

    def __init__(self, profile, *, robot=mock_robot):
        self.profile, self.robot = profile, robot
        self.url = "mock://mes"
        self.subscribers = set()

    def _emit(self, event):
        for loop, queue in tuple(self.subscribers):
            loop.call_soon_threadsafe(queue.put_nowait, event)

    async def publish(self, action, payload):
        if action == "fine_tuning":
            # 后台任务本身保持运行，批次仍须消费 RUN/到位/空闲，不能直接返回完成。
            task = asyncio.create_task(self.robot.move(payload, self._emit))
            await asyncio.sleep(0)
            if task.done():
                await task
        return self.dispatch(action, payload)

    def dispatch(self, action, payload):
        return {"sent": True, "confirmed": True if action == "module_confirm" else None,
                "mode": "mock", "simulated": True, "action": action,
                "message": "后端模拟成功，未连接设备"}

    async def stream_feedback(self, *, ready=None):
        queue = asyncio.Queue()
        subscriber = (asyncio.get_running_loop(), queue)
        self.subscribers.add(subscriber)
        if ready is not None:
            ready.set()
        try:
            while True:
                try:
                    segs = set(json.loads(settings.ROS_MODULE_SEG_MAP).values())
                except (TypeError, ValueError):
                    segs = set()
                events = []
                while not queue.empty():
                    events.append(queue.get_nowait())
                for event in events + self.robot.telemetry(segs):
                    yield {**event, "simulated": True, "module_id_space": "seg", "time_id": time.time()}
                await asyncio.sleep(0.05)
        finally:
            self.subscribers.discard(subscriber)

    async def publish_softstop(self):
        self.robot.stop(True)
        return True

    async def publish_stop_release(self):
        self.robot.stop(False)
        return True
