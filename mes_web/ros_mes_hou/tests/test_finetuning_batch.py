import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db import models
from app.db.database import Base
from app.ros.finetuning_batch import BatchManager
from app.ros.normalizer import normalize_feedback_message
from app.ros.profile import ROS1_PROFILE
from app.ros.rosbridge import RosbridgeClient
from app.schemas.finetuning import FineTuningBatchCreate


def status(axis, state=0, bits=257, seg=0):
    return {"data_type": "axis_status", "module_id_space": "seg", "module_id": seg,
            "device_id": axis, "axis_state": state, "status_bits": bits, "base_valid": 1}


def position(axis, value=0, seg=0):
    return {"data_type": ("rotation_axis_encoder", "swing_axis_encoder", "telescope_axis_encoder")[(axis - 1) % 3],
            "module_id_space": "seg", "module_id": seg, "device_id": axis, "position": value, "position_valid": True}


def arrive(axis, value, seg=0, pos_error=0):
    return {"data_type": "arrive_notification", "module_id_space": "seg", "module_id": seg, "device_id": axis,
            "angle": round(value * 100), "pos_error": pos_error, "status_bits": 5, "flags": 3}


class FakeClient:
    profile = ROS1_PROFILE

    def __init__(self, *, initial=True, complete=False, arrive_offset=0.0, positions=None):
        self.queue = asyncio.Queue()
        self.sent = []
        self.complete = complete
        self.arrive_offset = arrive_offset
        self.positions = {1: 0, 2: 0, 3: 0, **(positions or {})}
        if initial:
            for axis in self.positions:
                self.queue.put_nowait(status(axis))
                self.queue.put_nowait(position(axis, self.positions[axis]))

    async def stream_feedback(self, *, ready=None):
        ready.set()
        while True:
            yield await self.queue.get()

    async def publish(self, action, payload):
        self.sent.append(payload)
        axis = payload["message"]["device_id"]
        if self.complete:
            self.finish(axis, payload["message"]["position"][0], arrive_offset=self.arrive_offset)
        return {"sent": True}

    def finish(self, axis, increment, *, run=True, arrive_offset=0.0, pos_error=0):
        self.positions[axis] += increment
        if run:
            self.queue.put_nowait(status(axis, 1, 259))
        self.queue.put_nowait(arrive(axis, self.positions[axis] + arrive_offset, pos_error=pos_error))
        for did, value in self.positions.items():
            self.queue.put_nowait(position(did, value))
            self.queue.put_nowait(status(did, 2 if did == axis else 0))


class FineTuningBatchTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        with self.sessions() as db:
            db.add(models.User(User_ID=1, Username="test", Password="x", Type_ID=1, Creator_ID=1))
            db.add(models.Type(Type_ID=1, Typename="type", creater_id=1))
            db.add(models.Module(Module_ID=17, Type_ID=1, ModuleAddress="17", creater_id=1))
            db.add(models.Unit(Module_ID=17, Unit_ID=32, creater_id=1))
            db.commit()
        self.mapping = patch.object(settings, "ROS_MODULE_SEG_MAP", '{"17":0}')
        self.mapping.start()
        self.manager = BatchManager(self.sessions, state_timeout=0.08, motion_timeout=0.12)

    async def asyncTearDown(self):
        for task in list(self.manager.tasks.values()):
            task.cancel()
            await task
        self.mapping.stop()
        self.engine.dispose()

    def request(self, key="request_001", adjustments=None):
        return FineTuningBatchCreate(request_id=key, module_id=17, unit_id=32,
            adjustments=adjustments or [{"parameter_name": "rotation", "position": 2}, {"parameter_name": "swing", "position": 1}, {"parameter_name": "telescopic", "position": 0.5}])

    async def start(self, client, **kwargs):
        job = await self.manager.start(self.request(**kwargs), client, 1)
        return job, self.manager.tasks[job["id"]]

    async def wait_sent(self, client, count=1):
        for _ in range(100):
            if len(client.sent) >= count:
                return
            await asyncio.sleep(0.001)
        self.fail("expected command was not sent")

    def test_default_preparation_and_motion_timeouts_are_one_minute(self):
        manager = BatchManager(self.sessions)
        self.assertEqual(60, manager.state_timeout)
        self.assertEqual(60, manager.motion_timeout)
        self.assertEqual(3, manager.freshness)

    async def test_initial_feedback_after_eleven_seconds_can_still_start_motion(self):
        self.manager.state_timeout = 60
        clock = SimpleNamespace(now=0)
        client = FakeClient(complete=True)
        original_stream = client.stream_feedback

        async def delayed_feedback(*, ready=None):
            clock.now = 11
            async for item in original_stream(ready=ready):
                yield item

        client.stream_feedback = delayed_feedback
        with patch("app.ros.finetuning_batch.time", SimpleNamespace(monotonic=lambda: clock.now)):
            job, task = await self.start(client)
            await asyncio.wait_for(task, 0.5)
        self.assertEqual("completed", self.manager.get(job["id"])["status"])
        self.assertEqual(3, len(client.sent))

    async def test_feedback_readiness_and_initial_state_share_one_minute(self):
        self.manager.state_timeout = 60
        clock = SimpleNamespace(now=0)
        client = FakeClient(initial=False)
        original_stream = client.stream_feedback

        async def delayed_readiness(*, ready=None):
            clock.now = 61
            async for item in original_stream(ready=ready):
                yield item

        client.stream_feedback = delayed_readiness
        with patch("app.ros.finetuning_batch.time", SimpleNamespace(monotonic=lambda: clock.now)):
            job, task = await self.start(client)
            await asyncio.wait_for(task, 0.5)
        result = self.manager.get(job["id"])
        self.assertEqual("blocked", result["status"])
        self.assertIn("超时", result["message"])
        self.assertEqual([], client.sent)
        self.assertFalse(result["target_locked"])

    async def test_feedback_readiness_timeout_has_a_specific_message_and_sends_nothing(self):
        client = FakeClient(initial=False)

        async def unopened_feedback(*, ready=None):
            yield await client.queue.get()

        client.stream_feedback = unopened_feedback
        job, task = await self.start(client)
        await task
        result = self.manager.get(job["id"])
        self.assertEqual("blocked", result["status"])
        self.assertIn("等待反馈通道就绪超时", result["message"])
        self.assertEqual([], client.sent)

    async def test_disabled_preflight_sends_without_readiness_and_keeps_unknown_start_null(self):
        client = FakeClient(initial=False)
        client.finetuning_preflight_enabled = False

        async def unopened_feedback(*, ready=None):
            yield await client.queue.get()

        client.stream_feedback = unopened_feedback
        job, task = await self.start(client)
        client.finetuning_preflight_enabled = True
        await self.wait_sent(client)
        await task

        result = self.manager.get(job["id"])
        self.assertIs(result["finetuning_preflight_enabled"], False)
        self.assertIs(result["connection"]["finetuning_preflight_enabled"], False)
        self.assertEqual("uncertain", result["status"])
        self.assertTrue(result["target_locked"])
        self.assertEqual(1, len(client.sent))
        self.assertEqual([2], client.sent[0]["message"]["position"])
        for key in ("start_position", "expected_position", "observed_delta", "deviation"):
            self.assertIsNone(result["steps"][0][key])
        with self.sessions() as db:
            self.assertIsNone(db.query(models.FineTuning).one().old_value)

    async def test_disabled_preflight_ignores_incomplete_status_and_still_completes_in_order(self):
        client = FakeClient(initial=False, complete=True, positions={1: 50})
        client.finetuning_preflight_enabled = False
        for axis in (1, 2, 3):
            client.queue.put_nowait({"data_type": "axis_status", "module_id_space": "seg",
                                     "module_id": 0, "device_id": axis})
        job, task = await self.start(client)
        await task

        result = self.manager.get(job["id"])
        self.assertEqual("completed", result["status"])
        self.assertEqual([1, 2, 3], [sent["message"]["device_id"] for sent in client.sent])
        self.assertFalse(result["target_locked"])
        first_step = result["steps"][0]
        self.assertEqual(52, first_step["observed_angle"])
        for key in ("start_position", "expected_position", "observed_delta", "deviation"):
            self.assertIsNone(first_step[key])
        self.assertNotIn("warning", first_step)
        self.assertEqual(0, result["steps"][1]["start_position"])

    async def test_disabled_preflight_uses_available_nonzero_start_for_relative_results(self):
        client = FakeClient(complete=True, positions={1: 37.25})
        client.finetuning_preflight_enabled = False
        job, task = await self.start(client, adjustments=[{"parameter_name": "rotation", "position": 10}])
        await task

        step = self.manager.get(job["id"])["steps"][0]
        self.assertEqual("completed", step["status"])
        self.assertEqual(37.25, step["start_position"])
        self.assertEqual(47.25, step["expected_position"])
        self.assertEqual(10, step["observed_delta"])
        self.assertEqual(0, step["deviation"])
        self.assertEqual([10], client.sent[0]["message"]["position"])

    async def test_disabled_preflight_does_not_use_stale_start_positions(self):
        clock = SimpleNamespace(now=0)
        client = FakeClient(initial=False, complete=True, positions={1: 37.25})
        client.finetuning_preflight_enabled = False
        original_stream = client.stream_feedback

        async def stale_feedback(*, ready=None):
            yield position(1, 37.25)
            clock.now = 4
            async for item in original_stream(ready=ready):
                yield item

        client.stream_feedback = stale_feedback
        with patch("app.ros.finetuning_batch.time", SimpleNamespace(monotonic=lambda: clock.now)):
            job, task = await self.start(client, adjustments=[{"parameter_name": "rotation", "position": 10}])
            await asyncio.wait_for(task, 0.5)
        step = self.manager.get(job["id"])["steps"][0]
        self.assertEqual("completed", step["status"])
        self.assertIsNone(step["start_position"])
        self.assertIsNone(step["observed_delta"])
        self.assertEqual(47.25, step["observed_angle"])

    async def test_disabled_preflight_reports_only_firmware_error_when_start_is_unknown(self):
        client = FakeClient(initial=False, positions={1: 50})
        client.finetuning_preflight_enabled = False
        job, task = await self.start(client, adjustments=[{"parameter_name": "rotation", "position": 2}])
        await self.wait_sent(client)
        client.finish(1, 2, pos_error=45)
        await task

        result = self.manager.get(job["id"])
        step = result["steps"][0]
        self.assertEqual("completed", result["status"])
        self.assertEqual(52, step["observed_angle"])
        self.assertIsNone(step["observed_delta"])
        self.assertIsNone(step["deviation"])
        self.assertIn("本次相对运动结果待核实", step["warning"])
        self.assertIn("固件误差 +0.45°", step["warning"])
        self.assertNotIn("本次实际转动", step["warning"])
        self.assertNotIn("历史记录", step["warning"])
        self.assertNotIn("相差", step["warning"])

    async def test_disabled_preflight_still_requires_run_before_arrival_advances_the_batch(self):
        client = FakeClient(initial=False)
        client.finetuning_preflight_enabled = False
        job, task = await self.start(client)
        await self.wait_sent(client)
        client.finish(1, 2, run=False)
        await task
        result = self.manager.get(job["id"])
        self.assertEqual("uncertain", result["status"])
        self.assertTrue(result["target_locked"])
        self.assertEqual(1, len(client.sent))

    async def test_disabled_preflight_preserves_explicit_fault_limit_stop_and_rejection_guards(self):
        events = [
            *[{"data_type": "axis_status", "status_bits": 1 << bit} for bit in (3, 4, 5, 7)],
            {"data_type": "axis_status", "axis_state": 3},
            {"data_type": "axis_fault", "fault_bits": 1},
            {"data_type": "limit_event", "limit_type": 1},
            {"data_type": "stop_notification", "stop_reason": 2},
            {"data_type": "cmd_ack", "result": 1, "ack_msg": 1},
        ]
        for index, event in enumerate(events):
            with self.subTest(event=event):
                client = FakeClient(initial=False)
                client.finetuning_preflight_enabled = False
                client.queue.put_nowait({"module_id_space": "seg", "module_id": 0, "device_id": 1, **event})
                job, task = await self.start(client, key=f"bypass_guard_{index}")
                await task
                self.assertEqual("blocked", self.manager.get(job["id"])["status"])
                self.assertEqual([], client.sent)

    async def test_disabled_preflight_preserves_safety_and_target_locks(self):
        client = FakeClient(initial=False)
        client.finetuning_preflight_enabled = False
        self.manager.set_safety("stop_sent")
        with self.assertRaises(HTTPException):
            await self.start(client)
        self.manager.set_safety("clear")
        job, task = await self.start(client)
        await self.wait_sent(client)
        with self.assertRaises(HTTPException):
            await self.start(client, key="bypass_duplicate")
        await task
        self.assertEqual("uncertain", self.manager.get(job["id"])["status"])
        self.assertEqual(1, len(client.sent))

    def persist_history(self, steps, message, batch_id="legacy_batch"):
        with self.sessions() as db:
            db.add(models.FineTuningBatch(
                id=batch_id, request_id=batch_id, module_id=17, unit_id=32, seg=0,
                creator_id=1, target_key=None, request_json="{}",
                progress_json=json.dumps(steps, ensure_ascii=False), status="completed", message=message,
            ))
            db.commit()

    def test_legacy_snapshot_derives_relative_results_without_rewriting_persisted_json(self):
        for name, axis, unit, motion in (("rotation", 1, "°", "转动"), ("telescopic", 3, "mm", "移动")):
            with self.subTest(parameter=name):
                old_warning = "到位角 13.60 与期望 14.05 相差 -0.45（容差 0.2），仅提示，不阻止后续轴"
                legacy_step = {
                    "parameter_name": name, "device_id": axis, "position": 5,
                    "expected_position": 14.05, "observed_angle": 13.6,
                    "position_error": 0.45, "deviation": -0.45,
                    "status": "completed", "warning": old_warning,
                }
                batch_id = f"legacy_{name}"
                old_message = f"轴 {axis} 已观测到运行、目标到位及空闲；{old_warning}"
                self.persist_history([legacy_step], old_message, batch_id)

                result = self.manager.get(batch_id)
                step = result["steps"][0]
                self.assertAlmostEqual(9.05, step["start_position"])
                self.assertAlmostEqual(4.55, step["observed_delta"])
                self.assertEqual(14.05, step["expected_position"])
                self.assertEqual(13.6, step["observed_angle"])
                self.assertIn(f"本次实际{motion} 4.55{unit}", step["warning"])
                self.assertIn(step["warning"], result["message"])
                self.assertNotIn("到位角", result["message"])
                with self.sessions() as db:
                    row = db.get(models.FineTuningBatch, batch_id)
                    self.assertEqual([legacy_step], json.loads(row.progress_json))
                    self.assertEqual(old_message, row.message)

    def test_legacy_snapshot_preserves_existing_relative_fields(self):
        step = {
            "parameter_name": "rotation", "device_id": 1, "position": 5,
            "expected_position": 14.05, "observed_angle": 13.6,
            "start_position": 8.25, "observed_delta": 5.35, "status": "completed",
        }
        self.persist_history([step], "本批次已完成")
        result = self.manager.get("legacy_batch")
        self.assertEqual(step, result["steps"][0])

    def test_legacy_snapshot_without_finite_start_reports_relative_result_unknown(self):
        for index, expected in enumerate((None, float("inf"), True, "14.05")):
            with self.subTest(expected=expected):
                old_warning = "到位角 13.60 与期望 5.00 相差 +8.60（容差 0.2），仅提示，不阻止后续轴"
                step = {
                    "parameter_name": "rotation", "device_id": 1, "position": 5,
                    "expected_position": expected, "observed_angle": 13.6,
                    "status": "completed", "warning": old_warning,
                }
                batch_id = f"legacy_unknown_{index}"
                self.persist_history([step], f"轴 1 已完成；{old_warning}", batch_id)
                result = self.manager.get(batch_id)
                restored = result["steps"][0]
                self.assertNotIn("start_position", restored)
                self.assertNotIn("observed_delta", restored)
                self.assertIn("本次相对运动结果待核实", restored["warning"])
                self.assertNotIn("到位角", result["message"])

    def test_legacy_message_with_identical_axis_warnings_keeps_the_current_axis_units(self):
        old_warning = "到位角 13.60 与期望 14.05 相差 -0.45（容差 0.2），仅提示，不阻止后续轴"
        steps = [{
            "parameter_name": name, "device_id": axis, "position": 5,
            "expected_position": 14.05, "observed_angle": 13.6,
            "position_error": 0.45, "status": "completed", "warning": old_warning,
        } for name, axis in (("rotation", 1), ("telescopic", 3))]
        self.persist_history(steps, f"轴 3 已观测到运行、目标到位及空闲；{old_warning}")
        result = self.manager.get("legacy_batch")
        self.assertIn("本次实际移动 4.55mm", result["message"])
        self.assertIn("本次实际转动 4.55°", result["steps"][0]["warning"])

    async def test_three_axes_complete_in_order_with_real_completion_pattern(self):
        client = FakeClient(complete=True)
        job, task = await self.start(client)
        await task
        result = self.manager.get(job["id"])
        self.assertEqual([1, 2, 3], [x["message"]["device_id"] for x in client.sent])
        self.assertEqual("completed", result["status"])
        self.assertFalse(result["target_locked"])
        with self.sessions() as db:
            self.assertEqual(3, db.query(models.FineTuning).count())

    async def test_nonzero_start_reports_positive_motion_as_relative_increment(self):
        initial_positions = {1: 37.2, 2: 4.05, 3: 7.5}
        client = FakeClient(complete=True, positions=initial_positions)
        job, task = await self.start(client)
        await task

        result = self.manager.get(job["id"])
        self.assertEqual("completed", result["status"])
        for step, sent in zip(result["steps"], client.sent):
            start = initial_positions[step["device_id"]]
            self.assertAlmostEqual(start, step["start_position"])
            self.assertAlmostEqual(start + step["position"], step["expected_position"])
            self.assertAlmostEqual(start + step["position"], step["observed_angle"])
            self.assertAlmostEqual(step["position"], step["observed_delta"])
            self.assertEqual(0, step["deviation"])
            self.assertNotIn("warning", step)
            self.assertEqual([step["position"]], sent["message"]["position"])

    async def test_nonzero_start_reports_negative_motion_as_relative_increment(self):
        initial_positions = {1: -43.5, 2: 9.05, 3: 20.0}
        adjustments = [
            {"parameter_name": "rotation", "position": -10},
            {"parameter_name": "swing", "position": -5},
            {"parameter_name": "telescopic", "position": -2.5},
        ]
        client = FakeClient(complete=True, positions=initial_positions)
        job, task = await self.start(client, adjustments=adjustments)
        await task

        result = self.manager.get(job["id"])
        self.assertEqual("completed", result["status"])
        for step, sent in zip(result["steps"], client.sent):
            self.assertAlmostEqual(initial_positions[step["device_id"]], step["start_position"])
            self.assertAlmostEqual(step["position"], step["observed_delta"])
            self.assertEqual(0, step["deviation"])
            self.assertNotIn("warning", step)
            self.assertEqual([step["position"]], sent["message"]["position"])

    async def test_repeated_increment_starts_from_each_batch_current_position(self):
        client = FakeClient(complete=True, positions={1: 37.25})
        adjustment = [{"parameter_name": "rotation", "position": 10}]
        first_job, first_task = await self.start(client, adjustments=adjustment)
        await first_task
        for axis, value in client.positions.items():
            client.queue.put_nowait(status(axis))
            client.queue.put_nowait(position(axis, value))
        second_job, second_task = await self.start(client, key="request_002", adjustments=adjustment)
        await second_task

        first = self.manager.get(first_job["id"])["steps"][0]
        second = self.manager.get(second_job["id"])["steps"][0]
        self.assertEqual("completed", second["status"])
        self.assertEqual([10, 10], [sent["message"]["position"][0] for sent in client.sent])
        self.assertAlmostEqual(37.25, first["start_position"])
        self.assertAlmostEqual(47.25, second["start_position"])
        self.assertAlmostEqual(10, first["observed_delta"])
        self.assertAlmostEqual(10, second["observed_delta"])
        self.assertAlmostEqual(57.25, second["observed_angle"])

    async def test_relative_motion_warning_reports_degrees_and_millimeters(self):
        for name, axis, unit, motion in (("rotation", 1, "°", "转动"), ("telescopic", 3, "mm", "移动")):
            with self.subTest(parameter=name):
                client = FakeClient(positions={axis: 9.05})
                job, task = await self.start(client, key=f"warning_{name}", adjustments=[
                    {"parameter_name": name, "position": 5},
                ])
                await self.wait_sent(client)
                client.finish(axis, 5, arrive_offset=-0.45, pos_error=45)
                await task

                step = self.manager.get(job["id"])["steps"][0]
                self.assertEqual("completed", step["status"])
                self.assertAlmostEqual(9.05, step["start_position"])
                self.assertAlmostEqual(4.55, step["observed_delta"])
                self.assertAlmostEqual(-0.45, step["deviation"])
                self.assertIn(f"本次实际{motion} 4.55{unit}", step["warning"])
                self.assertIn(f"指令增量 5.00{unit}", step["warning"])
                self.assertIn(f"相差 -0.45{unit}", step["warning"])
                self.assertIn(f"固件误差 +0.45{unit}", step["warning"])
                self.assertNotIn("到位角", step["warning"])

    async def test_accept_ack_does_not_advance_next_axis(self):
        client = FakeClient()
        job, task = await self.start(client)
        await self.wait_sent(client)
        client.queue.put_nowait({"data_type": "cmd_ack", "device_id": 1, "result": 0, "ack_msg": 1})
        await asyncio.sleep(0.01)
        self.assertEqual(1, len(client.sent))
        client.finish(1, 2)
        await self.wait_sent(client, 2)
        self.manager.interrupt(job["id"])
        await task
        self.assertEqual(2, len(client.sent))

    async def test_arrival_without_observed_run_does_not_prove_this_motion(self):
        client = FakeClient()
        job, task = await self.start(client)
        await self.wait_sent(client)
        client.finish(1, 2, run=False)
        await task
        self.assertEqual("uncertain", self.manager.get(job["id"])["status"])
        self.assertEqual(1, len(client.sent))

    async def test_arrival_outside_tolerance_completes_with_warning_instead_of_locking(self):
        client = FakeClient()
        job, task = await self.start(client)
        await self.wait_sent(client)
        # 实际到位比期望多 0.45°，超出 0.2° 容差：只记提示，仍算这一轴完成并继续下一轴
        client.finish(1, 2, arrive_offset=0.45)
        await self.wait_sent(client, 2)
        self.manager.interrupt(job["id"])
        await task

        step = self.manager.get(job["id"])["steps"][0]
        self.assertEqual("completed", step["status"])
        self.assertAlmostEqual(0.45, step["deviation"], places=2)
        self.assertIn("相差 +0.45", step["warning"])
        self.assertIn("不阻止", step["warning"])

    async def test_out_of_tolerance_arrival_keeps_dispatch_available(self):
        client = FakeClient(complete=True, arrive_offset=0.45)
        job, task = await self.start(client)
        await task

        result = self.manager.get(job["id"])
        self.assertEqual("completed", result["status"])
        self.assertFalse(result["target_locked"])
        self.assertTrue(all(step.get("warning") for step in result["steps"]))
        self.assertIn("未阻止下发", result["message"])
        # 容差不再锁批次：同一机械臂可以立刻开下一批
        await self.manager.start(self.request("request_002"), client, 1)

    async def test_missing_initial_feedback_blocks_without_sending(self):
        client = FakeClient(initial=False)
        job, task = await self.start(client)
        await task
        self.assertEqual([], client.sent)
        self.assertIs(self.manager.get(job["id"])["finetuning_preflight_enabled"], True)
        self.assertEqual("blocked", self.manager.get(job["id"])["status"])
        self.assertFalse(self.manager.get(job["id"])["target_locked"])

    async def test_wrong_segment_or_arm_feedback_cannot_open_preflight(self):
        client = FakeClient(initial=False)
        for axis in (1, 2, 3, 4):
            client.queue.put_nowait(status(axis, seg=7))
            client.queue.put_nowait(position(axis, seg=7))
        job, task = await self.start(client)
        await task
        self.assertEqual([], client.sent)

    async def test_timeout_keeps_target_locked_and_never_retries(self):
        client = FakeClient()
        job, task = await self.start(client)
        await task
        self.assertEqual(1, len(client.sent))
        result = self.manager.get(job["id"])
        self.assertEqual("uncertain", result["status"])
        self.assertTrue(result["target_locked"])
        with self.assertRaises(HTTPException):
            await self.manager.start(self.request("request_002"), client, 1)

    async def test_duplicate_request_and_conflicting_payload(self):
        client = FakeClient(complete=True)
        job, task = await self.start(client)
        duplicate = await self.manager.start(self.request(), client, 1)
        self.assertEqual(job["id"], duplicate["id"])
        await task
        await self.manager.start(self.request(), client, 1)
        self.assertEqual(3, len(client.sent))
        with self.assertRaises(HTTPException):
            await self.manager.start(self.request(adjustments=[{"parameter_name": "rotation", "position": 3}]), client, 1)

    async def test_busy_ack_fault_limit_and_abnormal_stop_halt_remaining_axes(self):
        events = [
            {"data_type": "cmd_ack", "device_id": 1, "result": 1, "module_resolution": "resolved", "module_candidates": [17]},
            {"data_type": "axis_fault", "fault_bits": 1},
            {"data_type": "limit_event", "limit_type": 1},
            {"data_type": "stop_notification", "stop_reason": 2},
        ]
        for index, event in enumerate(events):
            client = FakeClient()
            job, task = await self.start(client, key=f"fault_request_{index}")
            await self.wait_sent(client)
            client.queue.put_nowait({"module_id_space": "seg", "module_id": 0, "device_id": 1, **event})
            await task
            self.assertEqual(1, len(client.sent))
            self.assertEqual("uncertain", self.manager.get(job["id"])["status"])
            await asyncio.sleep(0)
            self.manager.acknowledge(job["id"])

    async def test_emergency_stops_remaining_dispatch_and_release_does_not_resume(self):
        client = FakeClient()
        job, task = await self.start(client)
        await self.wait_sent(client)
        self.manager.set_safety("stop_requested")
        await task
        self.manager.set_safety("release_sent")
        self.assertEqual(1, len(client.sent))
        self.assertEqual("uncertain", self.manager.get(job["id"])["status"])

    async def test_restart_preserves_unknown_lock_and_does_not_resume(self):
        client = FakeClient()
        job, task = await self.start(client)
        await self.wait_sent(client)
        task.cancel()
        await task
        with self.sessions() as db:
            row = db.get(models.FineTuningBatch, job["id"])
            row.status = "executing"
            db.commit()
        restarted = BatchManager(self.sessions)
        restarted.recover()
        self.assertEqual("uncertain", restarted.get(job["id"])["status"])
        self.assertTrue(restarted.get(job["id"])["target_locked"])
        self.assertEqual(1, len(client.sent))

    async def test_normalizer_preserves_event_fields_and_never_fabricates_missing_status(self):
        result = normalize_feedback_message('/hardware/arrive_notification', {
            "module_id": 0, "device_id": 3, "angle": 125, "pos_error": 0, "flags": 3, "status_bits": 5,
        })
        self.assertEqual("arrive_notification", result["data_type"])
        self.assertEqual("seg", result["module_id_space"])
        self.assertEqual(125, result["angle"])
        self.assertIsNone(result["position"])
        bad = normalize_feedback_message('/hardware/axis_status', {"module_id": 0, "device_id": 1})
        self.assertIsNone(bad["axis_state"])
        self.assertIsNone(bad["status_bits"])

    async def test_legacy_single_axis_cannot_bypass_target_lock_or_mislabel_an_axis(self):
        from app.api.endpoints.control import send_fine_tuning
        from app.schemas.finetuning import FineTuningCreate
        client = FakeClient(initial=False)
        job, task = await self.start(client)
        with self.sessions() as db:
            for unit_id, axis, expected in ((32, 1, 409), (64, 1, 422), (32, 2, 422)):
                with self.assertRaises(HTTPException) as caught:
                    send_fine_tuning(FineTuningCreate(module_id=17, unit_id=unit_id, device_id=axis, parameter_name='rotation', position=1), db=db, dispatcher=object())
                self.assertEqual(expected, caught.exception.status_code)
            self.assertEqual(0, db.query(models.FineTuning).count())
        await task

    async def test_two_business_modules_cannot_control_the_same_physical_seg_arm(self):
        with self.sessions() as db:
            db.add(models.Module(Module_ID=18, Type_ID=1, ModuleAddress='18', creater_id=1))
            db.add(models.Unit(Module_ID=18, Unit_ID=32, creater_id=1))
            db.commit()
        client = FakeClient(initial=False)
        with patch.object(settings, 'ROS_MODULE_SEG_MAP', '{"17":0,"18":0}'):
            job, task = await self.start(client)
            other = self.request('aliased_request').model_copy(update={'module_id': 18})
            with self.assertRaises(HTTPException) as caught:
                await self.manager.start(other, client, 1)
            self.assertEqual(409, caught.exception.status_code)
            await task
        self.assertEqual([], client.sent)

    async def test_actual_transport_subscribes_new_events_and_signals_readiness(self):
        messages = []
        class Socket:
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
            async def send(self, value): messages.append(json.loads(value))
            def __aiter__(self):
                async def events():
                    yield json.dumps({"op": "publish", "topic": "/hardware/axis_status", "msg": {
                        "module_id": 0, "device_id": 1, "axis_state": 0, "status_bits": 257, "base_valid": 1,
                    }})
                return events()
        ready = asyncio.Event()
        with patch('app.ros.rosbridge.websockets.connect', return_value=Socket()):
            data = [item async for item in RosbridgeClient(ROS1_PROFILE).stream_feedback(ready=ready)]
        topics = {item['topic'] for item in messages if item['op'] == 'subscribe'}
        self.assertTrue(ready.is_set())
        self.assertTrue({'/hardware/axis_status', '/hardware/arrive_notification', '/hardware/stop_notification', '/hardware/axis_fault', '/hardware/limit_event'} <= topics)
        self.assertEqual('axis_status', data[0]['data_type'])
        self.assertEqual(257, data[0]['status_bits'])


if __name__ == '__main__':
    unittest.main()
