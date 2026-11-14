"""MES 三轴顺序执行。只使用既有 ROS 消息，不向固件虚构请求编号。"""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import math
import time
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.db import models
from app.db.database import SessionLocal
from app.ros.base import RosbridgeError
from app.ros.rosbridge import build_fine_tuning_publish_payload, resolve_arm_from_unit_id, resolve_module_seg
from app.ros.stop_holds import BLOCK_MESSAGE, axes_for, stop_holds

ACTIVE = {"queued", "checking", "executing"}
# 批次已终结、允许人工标记运动结论的状态
TERMINAL = {"completed", "uncertain", "blocked", "closed"}
ORDER = ("rotation", "swing", "telescopic")
ENCODERS = ("rotation_axis_encoder", "swing_axis_encoder", "telescope_axis_encoder")


class Halt(Exception):
    pass


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def axis_unit(parameter_name):
    return "mm" if parameter_name == "telescopic" else "°"


def format_axis_value(value, unit):
    return f"{value:.2f}{unit}" if number(value) else "—"

logger = logging.getLogger(__name__)
# 控制台中文标注：与 ROS 节点日志同一风格（表情 + 中文 + 关键值），测试时不用翻数据库就能看懂
AXIS_LABELS = {"rotation": "旋转", "swing": "摆动", "telescopic": "伸缩"}
STATUS_LABELS = {"queued": "📋 已登记", "checking": "⏳ 发送前检查", "executing": "🔄 执行中",
                 "completed": "✅ 完成", "uncertain": "⚠️ 待核实", "blocked": "🚫 受阻", "closed": "🧾 已关闭"}


def axis_label(parameter_name):
    return AXIS_LABELS.get(parameter_name, parameter_name)


def signed_axis_value(value, parameter_name):
    """带符号的微调量/偏差显示，缺值时不编造。"""
    return "—" if not number(value) else f"{value:+.2f}{axis_unit(parameter_name)}"


def relative_motion_warning(step):
    """按固定顺序说明一次相对运动的五个值，每个数只出现一次。

    初始值 → 微调量 → 应到 → 到位实测 → 偏差；缺少起点或到位反馈的项显示为 —。
    """
    unit = axis_unit(step["parameter_name"])
    tolerance = 0.1 if step["parameter_name"] == "telescopic" else 0.2
    start, requested = step.get("start_position"), step.get("position")
    expected = step.get("expected_position")
    if not number(expected) and number(start) and number(requested):
        expected = start + requested
    observed_delta = step.get("observed_delta")
    deviation = observed_delta - requested if number(observed_delta) and number(requested) else None
    error_value = step.get("position_error")
    firmware_error = f"{error_value:+.2f}{unit}" if number(error_value) else "待核实"
    parts = [
        f"初始 {format_axis_value(start, unit)}",
        f"微调 {requested:+.2f}{unit}" if number(requested) else "微调 —",
        f"应到 {format_axis_value(expected, unit)}",
        f"到位实测 {format_axis_value(step.get('observed_angle'), unit)}",
        f"偏差 {deviation:+.2f}{unit}" if number(deviation) else "偏差 —",
    ]
    return " → ".join(parts) + f"（仅提示，不阻止后续轴；固件自报误差 {firmware_error}，容差 ±{tolerance}{unit}）"


def snapshot(row):
    context = json.loads(row.request_json).get("_execution", {})
    simulated = context.get("mode", "real") == "mock"
    steps = json.loads(row.progress_json)
    message = row.message
    for step in steps:
        expected, requested = step.get("expected_position"), step.get("position")
        if "start_position" not in step and number(expected) and number(requested) and number(expected - requested):
            step["start_position"] = expected - requested
        start, observed = step.get("start_position"), step.get("observed_angle")
        if "observed_delta" not in step and number(start) and number(observed) and number(observed - start):
            step["observed_delta"] = round(observed - start, 3)
        old_warning = step.get("warning")
        if isinstance(old_warning, str) and old_warning:
            step["warning"] = relative_motion_warning(step)
            if not message.startswith("轴 ") or message.startswith(f"轴 {step.get('device_id')} "):
                message = message.replace(old_warning, step["warning"])
    return {
        "id": row.id, "request_id": row.request_id, "module_id": row.module_id,
        "unit_id": row.unit_id, "seg": row.seg, "status": row.status,
        "message": ("【后端模拟】" if simulated else "") + message, "steps": steps,
        "target_locked": row.target_key is not None,
        "simulated": simulated, "execution_mode": context.get("mode", "real"),
        "safety_mode": context.get("safety_mode", "real"), "connection": context,
        "finetuning_preflight_enabled": context.get("finetuning_preflight_enabled", True),
    }


class BatchManager:
    def __init__(self, sessions=SessionLocal, *, state_timeout=60.0, motion_timeout=60.0, freshness=3.0,
                 status_grace=5.0):
        self.sessions = sessions
        self.state_timeout = state_timeout
        self.motion_timeout = motion_timeout
        self.freshness = freshness
        # 轴状态帧缺失时的快速失败窗口：现场固件可能根本不上报 /hardware/axis_status，
        # 与其等满 state_timeout 再报"超时"，不如短时间内给出可执行的诊断信息。
        self.status_grace = status_grace
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

    def hold_target(self, module_id, *, device_id=None, axes=None, mode="real",
                    message="已执行局部停，停止后续下发；设备实际状态待确认"):
        """局部停命中当前环境的活动批次：只停止后续下发并转待核实，不重发任何指令。

        `axes` 为命中范围（臂停传该臂的 3 个轴号）；`device_id` 保留给单轴调用方。
        """
        wanted = None
        if axes is not None:
            wanted = {int(item) for item in axes}
        elif device_id is not None:
            wanted = {int(device_id)}
        with self.sessions() as db:
            for batch in db.query(models.FineTuningBatch).filter(models.FineTuningBatch.status.in_(ACTIVE)):
                item = snapshot(batch)
                if item["safety_mode"] != mode or int(batch.module_id) != int(module_id):
                    continue
                if wanted is not None:
                    try:
                        hit = axes_for(item["unit_id"], [step["parameter_name"] for step in item["steps"]])
                    except (ValueError, RosbridgeError):
                        hit = set()
                    if not (wanted & hit):
                        continue
                batch.cancel_requested = True
                batch.status = "uncertain"
                batch.message = message
            db.commit()

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

    def assert_available(self, db, module_id, unit_id, *, mode="real", safety_mode=None, axes=None):
        safety = db.get(models.ControlSafety, 2 if (safety_mode or mode) == "mock" else 1)
        if safety and safety.state.startswith("stop"):
            raise HTTPException(409, "急停联锁尚未解除，禁止运动下发")
        # 局部停只锁本模块/本轴；axes 未知时按整模块拦截，宁可多拦也不放过
        if stop_holds.blocked(db, module_id, axes=axes, mode=mode) is not None:
            raise HTTPException(409, BLOCK_MESSAGE)
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
            try:
                axes = axes_for(request.unit_id, [item.parameter_name for item in request.adjustments])
            except (ValueError, RosbridgeError):
                axes = None  # 轴号换算失败时按整模块拦截
            self.assert_available(db, request.module_id, request.unit_id, mode=mode,
                                  safety_mode=safety_mode, axes=axes)
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
                    "finetuning_preflight_enabled": getattr(client, "finetuning_preflight_enabled", True),
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
        detail = "；".join(f"轴{item['device_id']} {axis_label(item['parameter_name'])} {signed_axis_value(item['position'], item['parameter_name'])}"
                           for item in steps)
        logger.info("📋 批次 %s 登记 | 模块%s 臂%s | %s | 模式 %s | 请求编号 %s",
                    row.id[:8], request.module_id, arm, detail, mode, request.request_id)
        task = asyncio.create_task(self._execute(result["id"], client))
        self.tasks[result["id"]] = task
        task.add_done_callback(lambda _: self.tasks.pop(result["id"], None))
        return result

    def _save(self, batch_id, status, message, steps, *, unlock=False):
        # 每个状态变化都打一行中文标注，测试时控制台就是完整时间线
        logger.info("%s 批次 %s | %s", STATUS_LABELS.get(status, status), batch_id[:8], message)
        with self.sessions() as db:
            row = db.get(models.FineTuningBatch, batch_id)
            row.progress_json = json.dumps(steps, ensure_ascii=False)
            if row.cancel_requested and status in ACTIVE | {"completed"}:
                raise Halt("批次已被中止，禁止继续下发")
            row.status, row.message = status, message
            if unlock:
                row.target_key = None
            db.commit()

    def _record_outcome(self, batch_id, steps):
        """把每轴的运动结论与实测值回填到 fine_tuning 记录。

        只有收到完整到位证据的轴写 moved；超时、中断、未发送的轴写 unknown，
        留待操作者现场判断后用「标记未动」改成 no_motion。
        """
        rows = [step for step in steps if step.get("record_id") is not None]
        if not rows:
            return
        with self.sessions() as db:
            for step in rows:
                record = db.get(models.FineTuning, step["record_id"])
                if record is None:
                    continue
                record.observed_position = step.get("observed_angle")
                record.observed_delta = step.get("observed_delta")
                record.deviation = step.get("deviation")
                record.position_error = step.get("position_error")
                record.outcome = "moved" if step.get("status") == "completed" else "unknown"
                step["outcome"] = record.outcome
                logger.info("📝 批次 %s 轴 %s（%s）结论 %s%s", batch_id[:8], step["device_id"],
                            axis_label(step["parameter_name"]),
                            {"moved": "已动（收到到位证据）", "unknown": "待核实（无到位证据，可人工标记未动）"}[record.outcome],
                            "" if record.outcome == "moved" else "，等操作员现场判断")
            # 结论要一起落进批次快照：只写 fine_tuning 的话，查询接口拿到的 steps 里没有 outcome，
            # 前端只能猜默认“已动”，会把“待核实”的轴显示成已动。
            batch = db.get(models.FineTuningBatch, batch_id)
            if batch is not None:
                batch.progress_json = json.dumps(steps, ensure_ascii=False)
            db.commit()

    def set_outcome(self, batch_id, parameter_name, no_motion, operator_id):
        """人工标记某轴本次是否运动。只改数据库记录，不发送任何运动指令。"""
        if parameter_name not in ORDER:
            raise HTTPException(422, "parameter_name 必须是 rotation、swing、telescopic 之一")
        with self.sessions() as db:
            row = db.get(models.FineTuningBatch, batch_id)
            if row is None:
                raise HTTPException(404, "批次不存在")
            if row.status not in TERMINAL:
                raise HTTPException(409, "批次尚未结束，请等执行结束后再标记")
            outcome = "no_motion" if no_motion else "moved"
            # notes 形如 "batch=<uuid>; mode=real"，逐条精确比对，避免 LIKE 把 _ 当通配符
            candidates = db.query(models.FineTuning).filter(
                models.FineTuning.parameter_name == parameter_name,
            ).all()
            records = [item for item in candidates
                       if (item.notes or "").split(";")[0].strip() == f"batch={batch_id}"]
            if not records:
                raise HTTPException(404, "该批次没有这条轴的微调记录")
            marked_at = datetime.now(timezone.utc)
            logger.info("🖊️ 批次 %s 轴（%s）人工判定 %s | 操作员 id=%s | 只改数据库，未发送运动指令",
                        batch_id[:8], axis_label(parameter_name),
                        "本次未动" if no_motion else "撤销未动，恢复已动", operator_id)
            for record in records:
                record.outcome = outcome
                record.outcome_by = operator_id
                record.outcome_at = marked_at
            steps = json.loads(row.progress_json)
            for step in steps:
                if step.get("parameter_name") == parameter_name:
                    step["outcome"] = outcome
            row.progress_json = json.dumps(steps, ensure_ascii=False)
            db.commit()
            return snapshot(row)

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
            # 两种原因要分开说：操作者主动停和急停/联锁真的变了是两回事，
            # 混成一句话会让人去找一个根本没发生的急停。
            if row.cancel_requested:
                raise Halt("操作者已停止后续下发；已发送动作的结果仍需核实")
            if safety and safety.generation != generation:
                raise Halt("控制联锁或急停状态已变化，结果待核实")

    async def _execute(self, batch_id, client):
        job = self.get(batch_id)
        steps = job["steps"]
        preflight_enabled = job["finetuning_preflight_enabled"]
        generation = self.safety(job["safety_mode"])["generation"]
        arm = resolve_arm_from_unit_id(job["unit_id"])
        axes = tuple(range((arm - 1) * 3 + 1, arm * 3 + 1))
        queue, ready = asyncio.Queue(maxsize=512), asyncio.Event()
        attempted = False
        samples, states = {}, {}
        # 诊断用：本批次实际收到了哪些反馈帧；只在消息里说明，不参与任何放行判定。
        seen = {}
        axis_status_topic = client.profile.topics.get("feedback_axis_status", "/hardware/axis_status")

        async def pump():
            try:
                async for item in client.stream_feedback(ready=ready):
                    await queue.put((time.monotonic(), item))
                await queue.put((time.monotonic(), {"data_type": "error", "message": "反馈连接已结束"}))
            except Exception:
                await queue.put((time.monotonic(), {"data_type": "error", "message": "反馈连接失败"}))

        def consume(at, item):
            if item.get("simulated") is True and not job["simulated"]:
                return False
            if item.get("data_type") == "error":
                raise Halt("反馈断开，执行结果待核实")
            did, kind = item.get("device_id"), item.get("data_type")
            seen[kind] = seen.get(kind, 0) + 1
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
                if (isinstance(bits, int) and bits & ((1 << 3) | (1 << 4) | (1 << 5) | (1 << 7))) or item.get("axis_state") == 3:
                    raise Halt("轴处于限位、故障或急停状态")
                if not isinstance(bits, int) or item.get("axis_state") not in (0, 1, 2, 3) or item.get("base_valid") != 1:
                    if preflight_enabled:
                        raise Halt("轴状态缺少有效基准/状态字段，禁止继续下发")
                    return False
                states[did] = (at, item)
            elif kind in ENCODERS and kind == ENCODERS[(did - 1) % 3] and item.get("position_valid") is True and number(item.get("position")):
                samples[did] = (at, item["position"])
            return True

        def idle(did):
            if did not in states:
                return False
            at, state = states[did]
            return time.monotonic() - at <= self.freshness and state["axis_state"] in (0, 2) and not state["status_bits"] & ((1 << 1) | (1 << 6))

        def diagnose():
            """把"到底缺什么帧"写进提示，避免只报一句超时。"""
            labels = {
                "axis_status": "轴状态", "arrive_notification": "到位事件", "stop_notification": "停止事件",
                "cmd_ack": "命令回执", "axis_fault": "故障事件", "limit_event": "限位事件",
                "rotation_axis_encoder": "位置", "swing_axis_encoder": "位置", "telescope_axis_encoder": "位置",
                "pressure_sensor": "压力", "imu_pose": "陀螺仪",
            }
            counts = {}
            for kind, value in seen.items():
                name = labels.get(kind, str(kind))
                counts[name] = counts.get(name, 0) + value
            received = "、".join(f"{name} {value} 帧" for name, value in sorted(counts.items())) or "无任何反馈帧"
            parts = [f"本批次已收到：{received}"]
            if seen.get("axis_status", 0) == 0:
                parts.append(f"未收到任何轴状态帧（{axis_status_topic}）")
            stale_state = [str(did) for did in axes if did not in states or time.monotonic() - states[did][0] > self.freshness]
            stale_sample = [str(did) for did in axes if did not in samples or time.monotonic() - samples[did][0] > self.freshness]
            if stale_state:
                parts.append(f"缺少 {self.freshness:g} 秒内轴状态的轴：{','.join(stale_state)}")
            if stale_sample:
                parts.append(f"缺少 {self.freshness:g} 秒内位置反馈的轴：{','.join(stale_sample)}")
            return "；".join(parts)

        async def next_event(deadline, on_tick=None):
            while True:
                self._check(batch_id, generation)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise Halt(f"等待有效状态或运动完成超时；未自动重发（{diagnose()}）")
                try:
                    return await asyncio.wait_for(queue.get(), min(0.2, remaining))
                except asyncio.TimeoutError:
                    if on_tick is not None:
                        on_tick()
                    continue

        def guard_status_frames():
            """下发前若迟迟收不到任何轴状态帧，直接说明原因，不让操作者干等满等待上限。"""
            if seen.get("axis_status", 0) == 0 and time.monotonic() - preflight_started >= self.status_grace:
                raise Halt(
                    f"{self.status_grace:g} 秒内未收到任何轴状态帧（{axis_status_topic}），无法确认轴是否空闲，"
                    "未发送运动指令。请确认固件是否周期上报轴状态帧；"
                    f"如现场已确认固件不上报，可在个人中心关闭“发送前检查”后重试。（{diagnose()}）")

        reader = asyncio.create_task(pump())
        try:
            state_deadline = time.monotonic() + self.state_timeout
            if preflight_enabled:
                self._save(batch_id, "checking", "等待当前臂三轴有效空闲状态和实测位置", steps)
                try:
                    await asyncio.wait_for(ready.wait(), self.state_timeout)
                except asyncio.TimeoutError:
                    raise Halt("等待反馈通道就绪超时；未发送运动指令") from None
            else:
                self._save(batch_id, "checking", "已跳过下发前状态和位置检查，准备发送相对增量", steps)
                await asyncio.sleep(0)
            preflight_started = time.monotonic()
            for step in steps:
                # 每一轴下发前重新获得当前臂的有效空闲及位置；不能凭 HTTP 成功推进。
                while preflight_enabled and not all(idle(did) and did in samples and time.monotonic() - samples[did][0] <= self.freshness for did in axes):
                    at, item = await next_event(state_deadline, guard_status_frames)
                    consume(at, item)
                # 清空已收到的旧事件，避免前一动作的到位事件在发送后被消费。
                while not queue.empty():
                    at, item = queue.get_nowait()
                    consume(at, item)
                if preflight_enabled and not all(idle(did) for did in axes):
                    raise Halt("发送前检测到机械臂忙，尚未发送本轴")
                self._check(batch_id, generation)
                axis = step["device_id"]
                sample = samples.get(axis)
                start_position = sample[1] if sample is not None and time.monotonic() - sample[0] <= self.freshness else None
                expected = start_position + step["position"] if start_position is not None else None
                if expected is not None and not math.isfinite(expected):
                    raise Halt("目标位置无效，尚未发送本轴")
                step.update(status="sent_unconfirmed", start_position=start_position, expected_position=expected,
                            observed_delta=None, deviation=None)
                self._save(batch_id, "executing", f"轴 {axis}：发送并等待运行、到位及空闲反馈", steps)
                payload = build_fine_tuning_publish_payload(step["parameter_name"], step["position"], job["module_id"], axis, profile=client.profile)
                with self.sessions() as db:
                    record = models.FineTuning(
                        module_id=job["module_id"], unit_id=job["unit_id"],
                        parameter_name=step["parameter_name"],
                        # 初始值：本次发令前实测位置；缺少起点反馈时为空
                        old_value=start_position,
                        # 微调量：本次请求的增量
                        requested_delta=step["position"],
                        # 应到值：初始值 + 微调量；缺少初始值时为为空
                        new_value=expected,
                        creater_id=job_creator(self.sessions, batch_id),
                        notes=f"batch={batch_id}; mode={job['execution_mode']}",
                    )
                    db.add(record)
                    db.commit()
                    # 记住本条记录，批次结束时按 id 回填实测值与运动结论
                    step["record_id"] = record.id
                attempted = True
                sent_at = time.monotonic()
                unit = axis_unit(step["parameter_name"])
                logger.info("📤 轴 %s（%s）发送 %s | 起点 %s → 应到 %s | 记录 id=%s",
                            axis, axis_label(step["parameter_name"]),
                            signed_axis_value(step["position"], step["parameter_name"]),
                            format_axis_value(start_position, unit), format_axis_value(expected, unit),
                            step.get("record_id"))
                await client.publish("fine_tuning", payload)
                deadline = time.monotonic() + self.motion_timeout
                # 两条证据路径：优先"运行→到位→空闲"三件套；固件不发轴状态帧时退化为"到位+正常停止"设备事件。
                ran_at, arrived, idle_after_run, stopped = None, False, False, False
                while not (arrived and ((ran_at is not None and idle_after_run) or stopped)):
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
                    elif kind == "stop_notification" and at >= sent_at:
                        # consume() 已拦截 stop_reason != 1；到这里即为正常到位的停止事件。
                        stopped = True
                    elif kind == "arrive_notification" and at >= sent_at:
                        bits, flags, angle, error = (item.get(key) for key in ("status_bits", "flags", "angle", "pos_error"))
                        tolerance = 0.1 if step["parameter_name"] == "telescopic" else 0.2
                        # 硬条件：收到到位事件、基准有效、无超位/故障、带角度与误差字段
                        arrived = (isinstance(bits, int) and isinstance(flags, int) and bool(bits & 4) and bool(flags & 1)
                            and not bits & ((1 << 5) | (1 << 7)) and number(angle) and number(error))
                        if arrived:
                            # 容差只做提示：现场确认过"误差过大也要能继续下发"，因此不参与判定、不锁批次
                            observed_delta = angle / 100.0 - start_position if start_position is not None else None
                            deviation = round(observed_delta - step["position"], 3) if observed_delta is not None else None
                            error_value = round(error / 100.0, 3)
                            step["observed_angle"] = round(angle / 100.0, 3)
                            logger.info("🎯 轴 %s（%s）到位实测 %s | 偏差 %s | 固件自报误差 %s%s",
                                        axis, axis_label(step["parameter_name"]),
                                        format_axis_value(step["observed_angle"], unit),
                                        "—" if deviation is None else f"{deviation:+.2f}{unit}",
                                        "—" if error_value is None else f"{error_value:+.2f}{unit}",
                                        "，超出容差" if (deviation is not None and abs(deviation) > tolerance) or abs(error_value) > tolerance else "")
                            step["observed_delta"] = round(observed_delta, 3) if observed_delta is not None else None
                            step["deviation"] = deviation
                            step["position_error"] = error_value
                            if (deviation is not None and abs(deviation) > tolerance) or abs(error_value) > tolerance:
                                step["warning"] = relative_motion_warning(step)
                step["status"] = "completed"
                step["run_observed"] = ran_at is not None
                step["idle_observed"] = idle_after_run
                step["stop_observed"] = stopped
                step["completion_evidence"] = "run_arrive_idle" if (ran_at is not None and idle_after_run) else "arrive_stop"
                warning_note = f"；{step['warning']}" if step.get("warning") else ""
                evidence_note = ("已观测到运行、目标到位及空闲" if step["completion_evidence"] == "run_arrive_idle"
                                 else "已收到目标到位和正常停止事件（未观测到运行/空闲轴状态帧，按设备事件判定）")
                self._save(batch_id, "executing", f"轴 {axis} {evidence_note}{warning_note}", steps)
                state_deadline = time.monotonic() + self.state_timeout
            self._check(batch_id, generation)
            deviations = [step for step in steps if step.get("warning")]
            message = "本批次各轴已到位"
            if deviations:
                message += f"；{len(deviations)} 个轴偏差超出容差"
            self._save(batch_id, "completed", message, steps, unlock=True)
            self._record_outcome(batch_id, steps)
        except (Exception, asyncio.CancelledError) as exc:
            for step in steps:
                if step["status"] == "sent_unconfirmed":
                    step["status"] = "uncertain"
            status = "uncertain" if attempted or self.get(batch_id)["status"] == "uncertain" else "blocked"
            logger.warning("⚠️ 批次 %s 未正常完成：%s", batch_id[:8], str(exc) or "执行中断，结果待核实")
            self._save(batch_id, status, str(exc) or "执行中断，结果待核实", steps, unlock=status == "blocked")
            # 中断/受阻的轴没有到位证据，结论留待现场判断
            self._record_outcome(batch_id, steps)
        finally:
            reader.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await reader


def job_creator(sessions, batch_id):
    with sessions() as db:
        return db.get(models.FineTuningBatch, batch_id).creator_id


batch_manager = BatchManager()
