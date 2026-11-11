import asyncio
import json
import unittest
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

    def __init__(self, *, initial=True, complete=False, arrive_offset=0.0):
        self.queue = asyncio.Queue()
        self.sent = []
        self.complete = complete
        self.arrive_offset = arrive_offset
        self.positions = {1: 0, 2: 0, 3: 0}
        if initial:
            for axis in self.positions:
                self.queue.put_nowait(status(axis))
                self.queue.put_nowait(position(axis))

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
