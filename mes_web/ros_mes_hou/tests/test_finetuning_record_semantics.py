import asyncio
import json
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db import models
from app.db.database import Base
from app.db.schema import ensure_schema
from app.ros.finetuning_batch import BatchManager
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


class RecordingClient:
    """按到位事件驱动的最小替身：只回传状态帧和到位事件，用于验证写库字段。"""

    profile = None

    def __init__(self, *, complete=True, positions=None):
        from app.ros.profile import ROS1_PROFILE
        self.profile = ROS1_PROFILE
        self.queue = asyncio.Queue()
        self.sent = []
        self.complete = complete
        self.positions = {1: 0, 2: 0, 3: 0, **(positions or {})}
        for axis in self.positions:
            self.queue.put_nowait(status(axis))
            self.queue.put_nowait(position(axis, self.positions[axis]))

    async def stream_feedback(self, *, ready=None):
        ready.set()
        while True:
            yield await self.queue.get()

    async def publish(self, action, payload):
        self.sent.append(payload)
        if self.complete:
            self.finish(payload["message"]["device_id"], payload["message"]["position"][0])
        return {"sent": True}

    def finish(self, axis, increment, *, run=True, arrive_offset=0.0, pos_error=0):
        self.positions[axis] += increment
        if run:
            self.queue.put_nowait(status(axis, 1, 259))
        self.queue.put_nowait(arrive(axis, self.positions[axis] + arrive_offset, pos_error=pos_error))
        for did, value in self.positions.items():
            self.queue.put_nowait(position(did, value))
            self.queue.put_nowait(status(did, 2 if did == axis else 0))


class FineTuningRecordSemanticsTest(unittest.IsolatedAsyncioTestCase):
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
            adjustments=adjustments or [{"parameter_name": "rotation", "position": 2}])

    def records(self, batch_id):
        with self.sessions() as db:
            return db.query(models.FineTuning).filter(
                models.FineTuning.notes.like(f"batch={batch_id}%")).all()

    async def test_record_separates_initial_delta_and_expected(self):
        client = RecordingClient(positions={1: 47.25})
        job = await self.manager.start(self.request(), client, 1)
        await asyncio.wait_for(self.manager.tasks[job["id"]], 2)

        record = self.records(job["id"])[0]
        self.assertAlmostEqual(47.25, record.old_value)          # 初始值
        self.assertAlmostEqual(2.0, record.requested_delta)      # 微调量
        self.assertAlmostEqual(49.25, record.new_value)          # 应到值
        # 免责声明不再写入 notes
        self.assertEqual(f"batch={job['id']}; mode=real", record.notes)
        self.assertNotIn("不证明设备执行", record.notes)

    async def test_completed_axis_backfills_measurements_and_moved(self):
        client = RecordingClient(positions={1: 47.25})
        job = await self.manager.start(self.request(), client, 1)
        await asyncio.wait_for(self.manager.tasks[job["id"]], 2)

        record = self.records(job["id"])[0]
        self.assertAlmostEqual(49.25, record.observed_position)
        self.assertAlmostEqual(2.0, record.observed_delta)
        self.assertAlmostEqual(0.0, record.deviation)
        self.assertAlmostEqual(0.0, record.position_error)
        self.assertEqual("moved", record.outcome)
        self.assertIsNone(record.outcome_by)
        self.assertIsNone(record.outcome_at)

    async def test_snapshot_carries_outcome_so_ui_never_guesses_moved(self):
        """查询接口读 progress_json；结论没落进去，前端只能默认“已动”。"""
        client = RecordingClient(positions={1: 47.25})
        job = await self.manager.start(self.request(), client, 1)
        await asyncio.wait_for(self.manager.tasks[job["id"]], 2)

        self.assertEqual("moved", self.manager.get(job["id"])["steps"][0]["outcome"])

    async def test_snapshot_marks_uncertain_axis_as_unknown(self):
        client = RecordingClient(complete=False)
        job = await self.manager.start(self.request(), client, 1)
        await asyncio.wait_for(self.manager.tasks[job["id"]], 2)

        self.assertEqual("unknown", self.manager.get(job["id"])["steps"][0]["outcome"])

    async def test_uncertain_axis_backfills_unknown_and_leaves_measurements_null(self):
        client = RecordingClient(complete=False)
        job = await self.manager.start(self.request(), client, 1)
        await asyncio.wait_for(self.manager.tasks[job["id"]], 2)

        self.assertEqual("uncertain", self.manager.get(job["id"])["status"])
        record = self.records(job["id"])[0]
        self.assertAlmostEqual(0.0, record.old_value)
        self.assertAlmostEqual(2.0, record.requested_delta)
        self.assertAlmostEqual(2.0, record.new_value)
        self.assertIsNone(record.observed_position)
        self.assertIsNone(record.observed_delta)
        self.assertIsNone(record.deviation)
        self.assertEqual("unknown", record.outcome)

    async def test_mark_no_motion_records_operator_and_timestamp(self):
        client = RecordingClient(positions={1: 47.25})
        job = await self.manager.start(self.request(), client, 1)
        await asyncio.wait_for(self.manager.tasks[job["id"]], 2)

        data = self.manager.set_outcome(job["id"], "rotation", True, operator_id=1)
        record = self.records(job["id"])[0]
        self.assertEqual("no_motion", record.outcome)
        self.assertEqual(1, record.outcome_by)
        self.assertIsNotNone(record.outcome_at)
        self.assertEqual("no_motion", data["steps"][0]["outcome"])
        # 只改记录，不追加任何运动指令
        self.assertEqual(1, len(client.sent))

    async def test_mark_no_motion_can_be_reverted_to_moved(self):
        client = RecordingClient(positions={1: 47.25})
        job = await self.manager.start(self.request(), client, 1)
        await asyncio.wait_for(self.manager.tasks[job["id"]], 2)

        self.manager.set_outcome(job["id"], "rotation", True, operator_id=1)
        data = self.manager.set_outcome(job["id"], "rotation", False, operator_id=1)
        self.assertEqual("moved", self.records(job["id"])[0].outcome)
        self.assertEqual("moved", data["steps"][0]["outcome"])

    async def test_mark_rejected_while_batch_still_running(self):
        client = RecordingClient(complete=False)
        job = await self.manager.start(self.request(), client, 1)
        try:
            with self.assertRaises(HTTPException) as caught:
                self.manager.set_outcome(job["id"], "rotation", True, operator_id=1)
            self.assertEqual(409, caught.exception.status_code)
        finally:
            self.manager.interrupt(job["id"])
            await asyncio.wait_for(self.manager.tasks[job["id"]], 2)

    def test_mark_rejects_unknown_axis_name(self):
        with self.assertRaises(HTTPException) as caught:
            self.manager.set_outcome("missing_batch", "wrist", True, operator_id=1)
        self.assertEqual(422, caught.exception.status_code)

    def test_mark_rejects_missing_batch(self):
        with self.assertRaises(HTTPException) as caught:
            self.manager.set_outcome("missing_batch", "rotation", True, operator_id=1)
        self.assertEqual(404, caught.exception.status_code)


class MarkOutcomeEndpointTest(unittest.IsolatedAsyncioTestCase):
    """走一遍 HTTP 端点函数，确认响应结构与文案，且不触发任何运动。"""

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
            adjustments=adjustments or [{"parameter_name": "rotation", "position": 2}])

    async def test_endpoint_returns_batch_snapshot_and_sends_no_motion(self):
        from app.api.endpoints import control
        from app.schemas.finetuning import BatchMotionOutcome

        client = RecordingClient(positions={1: 47.25})
        job = await self.manager.start(self.request(), client, 1)
        await asyncio.wait_for(self.manager.tasks[job["id"]], 2)
        operator = models.User(User_ID=1, Username="test", Password="x", Type_ID=1, Creator_ID=1)

        with patch.object(control, "batch_manager", self.manager):
            response = control.mark_finetuning_axis_outcome(
                job["id"], "rotation",
                BatchMotionOutcome(no_motion=True, operator_confirmed=True),
                operator,
            )

        self.assertEqual(200, response["code"])
        self.assertIn("未发送运动指令", response["message"])
        self.assertEqual("no_motion", response["data"]["steps"][0]["outcome"])
        self.assertEqual(1, len(client.sent))


class EnsureSchemaTest(unittest.TestCase):
    def legacy_database(self):
        path = os.path.join(tempfile.mkdtemp(), "legacy.db")
        connection = sqlite3.connect(path)
        connection.executescript("""
            CREATE TABLE "Users" (User_ID INTEGER NOT NULL, PRIMARY KEY (User_ID));
            CREATE TABLE "Unit" (Module_ID INTEGER NOT NULL, Unit_ID INTEGER NOT NULL, PRIMARY KEY (Module_ID, Unit_ID));
            CREATE TABLE fine_tuning (
                id INTEGER NOT NULL, module_id INTEGER NOT NULL, unit_id INTEGER NOT NULL,
                module_address INTEGER, module_descript TEXT, parameter_name VARCHAR(100) NOT NULL,
                old_value FLOAT, new_value FLOAT NOT NULL, creater_id INTEGER NOT NULL,
                create_time DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, notes TEXT, del_flag BOOLEAN,
                PRIMARY KEY (id),
                CONSTRAINT fk_fine_tuning_unit FOREIGN KEY (module_id, unit_id) REFERENCES "Unit" (Module_ID, Unit_ID)
            );
            INSERT INTO fine_tuning (id, module_id, unit_id, parameter_name, old_value, new_value, creater_id, notes)
            VALUES (7, 17, 32, 'rotation', 47.25, 2.0, 1, 'batch=old; mode=real');
        """)
        connection.commit()
        connection.close()
        return path

    def test_rebuild_relaxes_new_value_and_keeps_rows(self):
        path = self.legacy_database()
        engine = create_engine("sqlite:///" + path)
        try:
            ensure_schema(engine)
            columns = {column["name"]: column for column in inspect(engine).get_columns("fine_tuning")}
            self.assertTrue(columns["new_value"]["nullable"])
            for name in ("requested_delta", "observed_position", "observed_delta", "deviation",
                         "position_error", "outcome", "outcome_by", "outcome_at"):
                self.assertIn(name, columns)
            connection = sqlite3.connect(path)
            try:
                rows = list(connection.execute("SELECT id, old_value, new_value, notes FROM fine_tuning"))
            finally:
                connection.close()
            self.assertEqual([(7, 47.25, 2.0, "batch=old; mode=real")], rows)
        finally:
            engine.dispose()

    def test_second_run_is_idempotent(self):
        path = self.legacy_database()
        engine = create_engine("sqlite:///" + path)
        try:
            ensure_schema(engine)
            ensure_schema(engine)
            connection = sqlite3.connect(path)
            try:
                self.assertEqual(1, list(connection.execute("SELECT COUNT(*) FROM fine_tuning"))[0][0])
            finally:
                connection.close()
        finally:
            engine.dispose()

    def test_missing_table_is_skipped(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        try:
            ensure_schema(engine)  # 建表交给 create_all，这里不应抛错
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
