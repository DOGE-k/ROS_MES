"""MES 三轴顺序执行。只使用既有 ROS 消息，不向固件虚构请求编号。"""
from __future__ import annotations

import asyncio
import contextlib
import json
import math
import time
import uuid

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.db import models
from app.db.database import SessionLocal
from app.ros.base import RosbridgeError
from app.ros.rosbridge import build_fine_tuning_publish_payload, resolve_arm_from_unit_id, resolve_module_seg

ACTIVE = {"queued", "checking", "executing"}
ORDER = ("rotation", "swing", "telescopic")
ENCODERS = ("rotation_axis_encoder", "swing_axis_encoder", "telescope_axis_encoder")


class Halt(Exception):
    pass


def snapshot(row):
    context = json.loads(row.request_json).get("_execution", {})
    simulated = context.get("mode", "real") == "mock"
    return {
        "id": row.id, "request_id": row.request_id, "module_id": row.module_id,
        "unit_id": row.unit_id, "seg": row.seg, "status": row.status,
        "message": ("【后端模拟】" if simulated else "") + row.message, "steps": json.loads(row.progress_json),
        "target_locked": row.target_key is not None,
        "simulated": simulated, "execution_mode": context.get("mode", "real"),
        "safety_mode": context.get("safety_mode", "real"), "connection": context,
    }


class BatchManager:
    def __init__(self, sessions=SessionLocal, *, state_timeout=10.0, motion_timeout=60.0, freshness=3.0):
        self.sessions = sessions
        self.state_timeout = state_timeout
        self.motion_timeout = motion_timeout
        self.freshness = freshness
        self.tasks = {}

    def recover(self):
        """单工作进程启动：记录未知结果并保留锁，不恢复动作。"""
        with self.sessions() as db:
            for row in db.query(models.FineTuningBatch).filter(models.FineTuningBatch.status.in_(ACTIVE)):
                row.status = "uncertain"
                row.message = "后端重启，执行结果待现场核实；未恢复或重发指令"
                row.cancel_requested = True
            db.commit()

    def safety(self, mode="real"):
        with self.sessions() as db:
            row = db.get(models.ControlSafety, 2 if mode == "mock" else 1)
            return {"state": row.state if row else "clear", "generation": row.generation if row else 0, "simulated": mode == "mock"}

    def set_safety(self, state, mode="real"):
        with self.sessions() as db:
            safety_id = 2 if mode == "mock" else 1
            row = db.get(models.ControlSafety, safety_id)
            if row is None:
                row = models.ControlSafety(id=safety_id, state=state, generation=1)
                db.add(row)
            else:
                row.state = state
                row.generation += 1
            if state.startswith("stop"):
                for batch in db.query(models.FineTuningBatch).filter(models.FineTuningBatch.status.in_(ACTIVE)):
                    if snapshot(batch)["safety_mode"] != mode:
                        continue
                    batch.cancel_requested = True
                    batch.status = "uncertain"
                    batch.message = "已请求急停，停止后续下发；设备实际状态待确认"
            db.commit()
        return self.safety(mode)

    def clear_safety(self, expected_generation, mode="real"):
        """人工确认清除当前版本的 MES 急停记录，保留批次核实流程。"""
        with self.sessions() as db:
            # 版本条件在同一条更新中核验，迟到请求不能清除后来触发的急停。
            db.query(models.ControlSafety).filter(
                models.ControlSafety.id == (2 if mode == "mock" else 1),
                models.ControlSafety.generation == expected_generation,
                models.ControlSafety.state != "clear",
            ).update({
                models.ControlSafety.state: "clear",
                models.ControlSafety.generation: models.ControlSafety.generation + 1,
            }, synchronize_session=False)
            db.commit()
        state = self.safety(mode)
        if state["state"] != "clear":
            raise HTTPException(409, "急停记录已更新，请查看最新状态后重新确认")
        return state

    def assert_available(self, db, module_id, unit_id, *, mode="real", safety_mode=None):
        safety = db.get(models.ControlSafety, 2 if (safety_mode or mode) == "mock" else 1)
        if safety and safety.state.startswith("stop"):
            raise HTTPException(409, "急停联锁尚未解除，禁止运动下发")
        mode_filter = models.FineTuningBatch.target_key.like("mock:%") if mode == "mock" else ~models.FineTuningBatch.target_key.like("mock:%")
        if db.query(models.FineTuningBatch).filter(mode_filter,
            models.FineTuningBatch.module_id == module_id, models.FineTuningBatch.unit_id == unit_id,
            models.FineTuningBatch.target_key.is_not(None),
        ).first():
            raise HTTPException(409, "该机械臂存在执行中或待核实批次，禁止重复下发")
        try:
            key = ("mock:" if mode == "mock" else "") + f"{resolve_module_seg(module_id)}:{resolve_arm_from_unit_id(unit_id)}"
        except RosbridgeError:
            # 旧单轴客户端可保留原配置兼容；存在在途动作时，未知映射不能绕过物理目标锁。
            if db.query(models.FineTuningBatch).filter(models.FineTuningBatch.target_key.is_not(None)).first():
                raise HTTPException(409, "目标映射不明且存在执行批次，禁止运动下发")
            return
        if db.query(models.FineTuningBatch).filter(models.FineTuningBatch.target_key == key).first():
            raise HTTPException(409, "该机械臂存在执行中或待核实批次，禁止重复下发")

    def get(self, batch_id):
        with self.sessions() as db:
            row = db.get(models.FineTuningBatch, batch_id)
            if row is None:
                raise HTTPException(404, "执行批次不存在；请核实设备，勿自动重新提交")
            return snapshot(row)

    def latest(self, module_id, unit_id, mode="real"):
        with self.sessions() as db:
            row = db.query(models.FineTuningBatch).filter(
                models.FineTuningBatch.module_id == module_id,
                models.FineTuningBatch.unit_id == unit_id,
                models.FineTuningBatch.target_key.is_not(None),
                models.FineTuningBatch.target_key.like("mock:%") if mode == "mock" else ~models.FineTuningBatch.target_key.like("mock:%"),
            ).first()
            return snapshot(row) if row else None

    def by_request(self, request_id):
        with self.sessions() as db:
            row = db.query(models.FineTuningBatch).filter_by(request_id=request_id).first()
            return snapshot(row) if row else None

    async def start(self, request, client, creator_id):
        mode = getattr(client, "execution_mode", "real")
        safety_mode = getattr(client, "safety_mode", mode)
        canonical = json.dumps({
            "module_id": request.module_id, "unit_id": request.unit_id,
            "adjustments": sorted([item.model_dump() for item in request.adjustments], key=lambda x: ORDER.index(x["parameter_name"])),
        }, sort_keys=True)
        with self.sessions() as db:
            old = db.query(models.FineTuningBatch).filter_by(request_id=request.request_id).first()
            if old:
                old_request = json.loads(old.request_json)
                old_request.pop("_execution", None)
                if json.dumps(old_request, sort_keys=True) != canonical:
                    raise HTTPException(409, "请求编号已用于另一组调整，禁止复用")
                return snapshot(old)
            self.assert_available(db, request.module_id, request.unit_id, mode=mode, safety_mode=safety_mode)
            unit = db.query(models.Unit).filter_by(Module_ID=request.module_id, Unit_ID=request.unit_id, del_flag=False).first()
            if unit is None:
                raise HTTPException(422, "机械臂未登记在该模块中")
            try:
                seg = resolve_module_seg(request.module_id)
                arm = resolve_arm_from_unit_id(request.unit_id)
            except (ValueError, RosbridgeError) as exc:
                raise HTTPException(422, str(exc)) from exc
            steps = [{**item, "device_id": (arm - 1) * 3 + ORDER.index(item["parameter_name"]) + 1,
                      "status": "pending"} for item in json.loads(canonical)["adjustments"]]
            row = models.FineTuningBatch(
                id=str(uuid.uuid4()), request_id=request.request_id, target_key=("mock:" if mode == "mock" else "") + f"{seg}:{arm}",
                module_id=request.module_id, unit_id=request.unit_id, seg=seg, creator_id=creator_id,
                request_json=json.dumps({**json.loads(canonical), "_execution": {
                    "mode": mode, "safety_mode": safety_mode, "url": getattr(client, "url", None),
                    "revision": getattr(client, "connection_revision", None),
                }}, sort_keys=True),
                progress_json=json.dumps(steps), status="queued", message="等待新鲜轴状态，尚未发送运动指令",
            )
            db.add(row)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                old = db.query(models.FineTuningBatch).filter_by(request_id=request.request_id).first()
                if old:
                    old_request = json.loads(old.request_json)
                    old_request.pop("_execution", None)
                    if json.dumps(old_request, sort_keys=True) == canonical:
                        return snapshot(old)
                raise HTTPException(409, "机械臂已被另一批次占用")
            result = snapshot(row)
        task = asyncio.create_task(self._execute(result["id"], client))
        self.tasks[result["id"]] = task
        task.add_done_callback(lambda _: self.tasks.pop(result["id"], None))
        return result

    def _save(self, batch_id, status, message, steps, *, unlock=False):
        with self.sessions() as db:
            row = db.get(models.FineTuningBatch, batch_id)
            row.progress_json = json.dumps(steps, ensure_ascii=False)
            if row.cancel_requested and status in ACTIVE | {"completed"}:
                raise Halt("批次已被中止，禁止继续下发")
            row.status, row.message = status, message
            if unlock:
                row.target_key = None
            db.commit()

    def interrupt(self, batch_id):
        with self.sessions() as db:
            row = db.get(models.FineTuningBatch, batch_id)
            if row is None:
                raise HTTPException(404, "批次不存在")
            if row.status in ACTIVE:
                row.cancel_requested = True
                row.status, row.message = "uncertain", "已停止后续下发；已发送动作的结果仍需核实"
                db.commit()
            return snapshot(row)

    def acknowledge(self, batch_id):
        with self.sessions() as db:
            row = db.get(models.FineTuningBatch, batch_id)
            if row is None:
                raise HTTPException(404, "批次不存在")
            if row.status != "uncertain" or batch_id in self.tasks:
                raise HTTPException(409, "请先停止后续下发并等待处理结束，再现场核实")
            row.status, row.message, row.target_key = "closed", "操作者已现场核实并关闭 MES 批次；未重发任何指令", None
            db.commit()
            return snapshot(row)

    def _check(self, batch_id, generation):
        with self.sessions() as db:
            row = db.get(models.FineTuningBatch, batch_id)
            safety = db.get(models.ControlSafety, 2 if snapshot(row)["safety_mode"] == "mock" else 1)
            if row.cancel_requested or (safety and safety.generation != generation):
                raise Halt("控制联锁或急停状态已变化，结果待核实")

    async def _execute(self, batch_id, client):
        job = self.get(batch_id)
        steps = job["steps"]
        generation = self.safety(job["safety_mode"])["generation"]
        arm = resolve_arm_from_unit_id(job["unit_id"])
        axes = tuple(range((arm - 1) * 3 + 1, arm * 3 + 1))
        queue, ready = asyncio.Queue(maxsize=512), asyncio.Event()
        attempted = False
        samples, states = {}, {}

        async def pump():
            try:
                async for item in client.stream_feedback(ready=ready):
                    await queue.put((time.monotonic(), item))
                await queue.put((time.monotonic(), {"data_type": "error", "message": "反馈连接已结束"}))
            except Exception:
                await queue.put((time.monotonic(), {"data_type": "error", "message": "反馈连接失败"}))

        def number(value):
            return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

        def consume(at, item):
            if item.get("simulated") is True and not job["simulated"]:
                return False
            if item.get("data_type") == "error":
                raise Halt("反馈断开，执行结果待核实")
            did, kind = item.get("device_id"), item.get("data_type")
            if kind == "cmd_ack":
                if did in axes and item.get("result") not in (None, 0):
                    candidates = item.get("module_candidates", [])
                    if job["module_id"] in candidates or item.get("module_resolution") != "resolved":
                        raise Halt(f"收到可能属于当前臂的拒绝回执（result={item.get('result')}），停止后续下发")
                return False
            if item.get("module_id_space") != "seg" or item.get("module_id") != job["seg"]:
                return False
            if kind == "vacuum_loss_event" and did == 20 + arm:
                raise Halt("当前机械臂出现失压事件，停止后续下发")
            if did not in axes:
                return False
            if kind in {"axis_fault", "limit_event"}:
                raise Halt("当前机械臂出现故障/限位事件，停止后续下发")
            if kind == "stop_notification" and item.get("stop_reason") != 1:
                raise Halt("收到非正常到位的停止事件，执行结果待核实")
            if kind == "axis_status":
                bits = item.get("status_bits")
                if not isinstance(bits, int) or item.get("axis_state") not in (0, 1, 2, 3) or item.get("base_valid") != 1:
                    raise Halt("轴状态缺少有效基准/状态字段，禁止继续下发")
                if bits & ((1 << 3) | (1 << 4) | (1 << 5) | (1 << 7)) or item.get("axis_state") == 3:
                    raise Halt("轴处于限位、故障或急停状态")
                states[did] = (at, item)
            elif kind in ENCODERS and kind == ENCODERS[(did - 1) % 3] and item.get("position_valid") is True and number(item.get("position")):
                samples[did] = (at, item["position"])
            return True

        def idle(did):
            if did not in states:
                return False
            at, state = states[did]
            return time.monotonic() - at <= self.freshness and state["axis_state"] in (0, 2) and not state["status_bits"] & ((1 << 1) | (1 << 6))

        async def next_event(deadline):
            while True:
                self._check(batch_id, generation)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise Halt("等待有效状态或运动完成超时；未自动重发")
                try:
                    return await asyncio.wait_for(queue.get(), min(0.2, remaining))
                except asyncio.TimeoutError:
                    continue

        reader = asyncio.create_task(pump())
        try:
            self._save(batch_id, "checking", "等待当前臂三轴有效空闲状态和实测位置", steps)
            await asyncio.wait_for(ready.wait(), self.state_timeout)
            for step in steps:
                deadline = time.monotonic() + self.state_timeout
                # 每一轴下发前重新获得当前臂的有效空闲及位置；不能凭 HTTP 成功推进。
                while not all(idle(did) and did in samples and time.monotonic() - samples[did][0] <= self.freshness for did in axes):
                    at, item = await next_event(deadline)
                    consume(at, item)
                # 清空已收到的旧事件，避免前一动作的到位事件在发送后被消费。
                while not queue.empty():
                    at, item = queue.get_nowait()
                    consume(at, item)
                if not all(idle(did) for did in axes):
                    raise Halt("发送前检测到机械臂忙，尚未发送本轴")
                self._check(batch_id, generation)
                axis = step["device_id"]
                expected = samples[axis][1] + step["position"]
                if not math.isfinite(expected):
                    raise Halt("目标位置无效，尚未发送本轴")
                step.update(status="sent_unconfirmed", expected_position=expected)
                self._save(batch_id, "executing", f"轴 {axis}：发送并等待运行、到位及空闲反馈", steps)
                payload = build_fine_tuning_publish_payload(step["parameter_name"], step["position"], job["module_id"], axis, profile=client.profile)
                with self.sessions() as db:
                    db.add(models.FineTuning(module_id=job["module_id"], unit_id=job["unit_id"],
                        parameter_name=step["parameter_name"], old_value=samples[axis][1], new_value=step["position"],
                        creater_id=job_creator(self.sessions, batch_id), notes=f"batch={batch_id}; mode={job['execution_mode']}; 增量发送记录，不证明设备执行"))
                    db.commit()
                attempted = True
                sent_at = time.monotonic()
                await client.publish("fine_tuning", payload)
                deadline = time.monotonic() + self.motion_timeout
                ran_at, arrived, idle_after_run = None, False, False
                while not (ran_at is not None and arrived and idle_after_run):
                    at, item = await next_event(deadline)
                    if not consume(at, item) or at < sent_at:
                        continue
                    did, kind = item.get("device_id"), item.get("data_type")
                    if kind == "axis_status" and did != axis and (item["axis_state"] == 1 or item["status_bits"] & ((1 << 1) | (1 << 6))):
                        raise Halt("其他轴出现并行运动，停止后续下发")
                    if did != axis:
                        continue
                    if kind == "axis_status":
                        if item["axis_state"] == 1 or item["status_bits"] & (1 << 1):
                            ran_at = at
                            idle_after_run = False
                        elif ran_at is not None and at >= ran_at and idle(axis):
                            idle_after_run = True
                    elif kind == "arrive_notification" and ran_at is not None and at >= ran_at:
                        bits, flags, angle, error = (item.get(key) for key in ("status_bits", "flags", "angle", "pos_error"))
                        tolerance = 0.1 if step["parameter_name"] == "telescopic" else 0.2
                        arrived = (isinstance(bits, int) and isinstance(flags, int) and bool(bits & 4) and bool(flags & 1)
                            and not bits & ((1 << 5) | (1 << 7)) and number(angle) and number(error)
                            and abs(angle / 100.0 - expected) <= tolerance and abs(error / 100.0) <= tolerance)
                step["status"] = "completed"
                self._save(batch_id, "executing", f"轴 {axis} 已观测到运行、目标到位及空闲", steps)
            self._check(batch_id, generation)
            self._save(batch_id, "completed", "本批次各轴已观测到运行、目标到位和空闲反馈", steps, unlock=True)
        except (Exception, asyncio.CancelledError) as exc:
            for step in steps:
                if step["status"] == "sent_unconfirmed":
                    step["status"] = "uncertain"
            status = "uncertain" if attempted or self.get(batch_id)["status"] == "uncertain" else "blocked"
            self._save(batch_id, status, str(exc) or "执行中断，结果待核实", steps, unlock=status == "blocked")
        finally:
            reader.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await reader


def job_creator(sessions, batch_id):
    with sessions() as db:
        return db.get(models.FineTuningBatch, batch_id).creator_id


batch_manager = BatchManager()
