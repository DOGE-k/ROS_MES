import asyncio
import json
import types
import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.endpoints import control
from app.db import models
from app.db.database import Base
from app.ros.base import RosbridgeError
from app.ros.finetuning_batch import BatchManager
from app.ros.profile import ROS1_PROFILE
from app.ros.rosbridge import RosbridgeClient
from app.ros.stop_holds import StopHoldManager, axes_for
from app.schemas.local_stop import LocalStopRequest


class DummyDispatcher:
    revision = 0
    emergency_mode = "real"

    def __init__(self, sent=True):
        self.sent = sent
        self.calls = []
        self.client = types.SimpleNamespace(execution_mode="real")

    async def trigger_local_stop(self, *, scope, module_id, device_id=None):
        self.calls.append((scope, module_id, device_id))
        return self.sent


class LocalStopTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.manager = StopHoldManager()
        self.dispatcher = DummyDispatcher()

    def tearDown(self):
        self.engine.dispose()

    def _stop(self, *, scope="module", module_id=17, device_id=None):
        with patch("app.api.endpoints.control.get_ros_dispatcher", return_value=self.dispatcher):
            with self.Session() as db:
                return asyncio.run(control.request_local_stop(
                    LocalStopRequest(scope=scope, module_id=module_id, device_id=device_id),
                    db=db, current_user=types.SimpleNamespace(Username="test"),
                ))

    def test_module_stop_records_hold_and_sends_module_command(self):
        response = self._stop(scope="module", module_id=17)

        self.assertEqual(response["code"], 200)
        self.assertEqual(response["data"]["scope"], "module")
        self.assertEqual(response["data"]["state"], "sent")
        self.assertEqual(self.dispatcher.calls, [("module", 17, None)])
        with self.Session() as db:
            self.assertEqual(len(self.manager.active(db, "real")), 1)

    def test_axis_stop_sends_axis_number_and_records_device(self):
        response = self._stop(scope="axis", module_id=17, device_id=5)

        self.assertEqual(response["data"]["scope"], "axis")
        self.assertEqual(response["data"]["device_id"], 5)
        self.assertEqual(self.dispatcher.calls, [("axis", 17, 5)])

    def test_failed_send_keeps_hold_locked(self):
        self.dispatcher.sent = False
        response = self._stop(scope="module", module_id=17)

        self.assertEqual(response["data"]["state"], "unknown")
        with self.Session() as db:
            self.assertEqual(len(self.manager.active(db, "real")), 1)

    def test_invalid_axis_number_is_rejected_before_sending(self):
        with self.assertRaises(HTTPException) as ctx:
            self._stop(scope="axis", module_id=17, device_id=16)

        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(self.dispatcher.calls, [])

    def test_unmapped_module_is_rejected(self):
        with self.assertRaises(HTTPException) as ctx:
            self._stop(scope="module", module_id=18)

        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(self.dispatcher.calls, [])

    def test_connection_revision_mismatch_is_rejected(self):
        with patch("app.api.endpoints.control.get_ros_dispatcher", return_value=self.dispatcher):
            with self.Session() as db:
                with self.assertRaises(HTTPException) as ctx:
                    asyncio.run(control.request_local_stop(
                        LocalStopRequest(scope="module", module_id=17, connection_revision=9),
                        db=db, current_user=types.SimpleNamespace(Username="test"),
                    ))

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(self.dispatcher.calls, [])

    def test_module_hold_blocks_same_module_only(self):
        self._stop(scope="module", module_id=17)

        with self.Session() as db:
            self.assertIsNotNone(self.manager.blocked(db, 17, axes={1}))
            self.assertIsNone(self.manager.blocked(db, 18, axes={1}))
            with self.assertRaises(RosbridgeError):
                self.manager.assert_available(db, 17, axes={1})

    def test_axis_hold_blocks_only_that_axis(self):
        self._stop(scope="axis", module_id=17, device_id=5)

        with self.Session() as db:
            self.assertIsNotNone(self.manager.blocked(db, 17, axes={5}))
            self.assertIsNone(self.manager.blocked(db, 17, axes={4, 6}))
            # 轴号无法判定时按整模块拦截，宁可多拦
            self.assertIsNotNone(self.manager.blocked(db, 17, axes=None))

    def test_axes_for_maps_unit_and_parameter_to_axis_number(self):
        self.assertEqual(axes_for(32, ["rotation"]), {1})
        self.assertEqual(axes_for(32, ["swing", "telescopic"]), {2, 3})
        self.assertEqual(axes_for(64, ["rotation"]), {4})

    def test_clear_module_restores_dispatch(self):
        self._stop(scope="module", module_id=17)
        with patch("app.api.endpoints.control.get_ros_dispatcher", return_value=self.dispatcher):
            with self.Session() as db:
                response = control.clear_local_stop_holds(
                    module_id=17, current_user=types.SimpleNamespace(Username="test"), db=db)

        self.assertEqual(response["data"]["cleared"], 1)
        with self.Session() as db:
            self.assertIsNone(self.manager.blocked(db, 17, axes={1}))

    def test_active_holds_are_reported_for_current_mode(self):
        self._stop(scope="module", module_id=17)
        with patch("app.api.endpoints.control.get_ros_dispatcher", return_value=self.dispatcher):
            with self.Session() as db:
                response = control.list_local_stop_holds(
                    current_user=types.SimpleNamespace(Username="test"), db=db)

        self.assertEqual(response["data"]["mode"], "real")
        self.assertEqual(len(response["data"]["holds"]), 1)
        self.assertTrue(response["data"]["holds"][0]["active"])

    def test_hold_target_marks_matching_batch_uncertain(self):
        manager = BatchManager(sessions=self.Session)
        with self.Session() as db:
            db.add(models.FineTuningBatch(
                id="batch-1", request_id="request-1", target_key="0:1", module_id=17, unit_id=32, seg=0,
                creator_id=1, status="executing", message="running",
                request_json=json.dumps({"_execution": {"mode": "real", "safety_mode": "real"}}),
                progress_json=json.dumps([{"parameter_name": "rotation", "device_id": 1, "position": 2, "status": "sent_unconfirmed"}]),
            ))
            db.commit()

        manager.hold_target(17, device_id=None, mode="real")
        with self.Session() as db:
            row = db.get(models.FineTuningBatch, "batch-1")
            self.assertEqual(row.status, "uncertain")
            self.assertTrue(row.cancel_requested)
            self.assertIn("局部停", row.message)

    def test_axis_hold_target_skips_batch_without_that_axis(self):
        manager = BatchManager(sessions=self.Session)
        with self.Session() as db:
            db.add(models.FineTuningBatch(
                id="batch-2", request_id="request-2", target_key="0:1", module_id=17, unit_id=32, seg=0,
                creator_id=1, status="executing", message="running",
                request_json=json.dumps({"_execution": {"mode": "real", "safety_mode": "real"}}),
                progress_json=json.dumps([{"parameter_name": "rotation", "device_id": 1, "position": 2, "status": "pending"}]),
            ))
            db.commit()

        manager.hold_target(17, device_id=3, mode="real")
        with self.Session() as db:
            self.assertEqual(db.get(models.FineTuningBatch, "batch-2").status, "executing")

    def test_publish_local_stop_message_matches_contract(self):
        sent = []

        class FakeWebSocket:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def send(self, message):
                sent.append(json.loads(message))

        client = RosbridgeClient(ROS1_PROFILE, url="ws://test", timeout=0.1)
        with patch("app.ros.rosbridge.websockets") as websockets_mock:
            websockets_mock.connect = Mock(return_value=FakeWebSocket())
            self.assertTrue(asyncio.run(client.publish_local_stop(scope="module", module_id=17)))
            self.assertTrue(asyncio.run(client.publish_local_stop(scope="axis", module_id=17, device_id=5)))

        self.assertEqual(sent[0]["topic"], "/arm/cmd_vel")
        self.assertEqual(sent[0]["msg"]["device_id"], 0)
        self.assertEqual(sent[0]["msg"]["position"], [0x08, 17])
        self.assertEqual(sent[1]["msg"]["device_id"], 5)
        self.assertEqual(sent[1]["msg"]["position"], [0x0C, 1])

    def test_unknown_scope_is_not_published(self):
        client = RosbridgeClient(ROS1_PROFILE, url="ws://test", timeout=0.1)
        with patch("app.ros.rosbridge.websockets") as websockets_mock:
            self.assertFalse(asyncio.run(client.publish_local_stop(scope="all", module_id=17)))
            websockets_mock.connect.assert_not_called()

    def test_arm_stop_sends_arm_scope_and_records_arm_number(self):
        response = self._stop(scope="arm", module_id=17, device_id=2)

        self.assertEqual(response["data"]["scope"], "arm")
        self.assertEqual(response["data"]["device_id"], 2)
        self.assertEqual(self.dispatcher.calls, [("arm", 17, 2)])

    def test_invalid_arm_number_is_rejected_before_sending(self):
        for arm in (0, 6, 15):
            with self.subTest(arm=arm):
                with self.assertRaises(HTTPException) as ctx:
                    self._stop(scope="arm", module_id=17, device_id=arm)
                self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(self.dispatcher.calls, [])

    def test_arm_hold_blocks_only_that_arms_three_axes(self):
        self._stop(scope="arm", module_id=17, device_id=2)

        with self.Session() as db:
            self.assertIsNotNone(self.manager.blocked(db, 17, axes={4}))
            self.assertIsNotNone(self.manager.blocked(db, 17, axes={6}))
            self.assertIsNone(self.manager.blocked(db, 17, axes={1, 2, 3}))
            # 轴号无法判定时按整模块拦截
            self.assertIsNotNone(self.manager.blocked(db, 17, axes=None))

    def test_arm_stop_publishes_three_axis_frames(self):
        sent = []

        class FakeWebSocket:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def send(self, message):
                sent.append(json.loads(message))

        client = RosbridgeClient(ROS1_PROFILE, url="ws://test", timeout=0.1)
        with patch("app.ros.rosbridge.websockets") as websockets_mock:
            websockets_mock.connect = Mock(return_value=FakeWebSocket())
            self.assertTrue(asyncio.run(client.publish_local_stop(scope="arm", module_id=17, device_id=2)))

        self.assertEqual([item["msg"]["device_id"] for item in sent], [4, 5, 6])
        self.assertTrue(all(item["msg"]["position"] == [0x0C, 1] for item in sent))
        self.assertTrue(all(item["topic"] == "/arm/cmd_vel" for item in sent))

    def test_arm_hold_target_skips_batches_of_other_arms(self):
        manager = BatchManager(sessions=self.Session)
        with self.Session() as db:
            db.add(models.FineTuningBatch(
                id="batch-arm", request_id="request-arm", target_key="0:1", module_id=17, unit_id=32, seg=0,
                creator_id=1, status="executing", message="running",
                request_json=json.dumps({"_execution": {"mode": "real", "safety_mode": "real"}}),
                progress_json=json.dumps([{"parameter_name": "rotation", "device_id": 1, "position": 2, "status": "pending"}]),
            ))
            db.commit()

        # 一号臂的批次不应被“停二号臂”波及
        manager.hold_target(17, axes={4, 5, 6}, mode="real")
        with self.Session() as db:
            self.assertEqual(db.get(models.FineTuningBatch, "batch-arm").status, "executing")

        manager.hold_target(17, axes={1, 2, 3}, mode="real")
        with self.Session() as db:
            row = db.get(models.FineTuningBatch, "batch-arm")
            self.assertEqual(row.status, "uncertain")
            self.assertTrue(row.cancel_requested)


if __name__ == "__main__":
    unittest.main()
