import asyncio
import json
import unittest
from types import SimpleNamespace

from fastapi import FastAPI
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.endpoints import finetuning
from app.db import models
from app.db.database import Base, get_db


class LocalASGIClient:
    """直接请求 FastAPI 应用，覆盖 HTTP 校验且无需可选 httpx 依赖。"""

    def __init__(self, app):
        self.app = app

    def post(self, path, **kwargs):
        body = json.dumps(kwargs["json"]).encode()
        messages = []

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        async def send(message):
            messages.append(message)

        asyncio.run(self.app({
            "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
            "method": "POST", "scheme": "http", "path": path, "raw_path": path.encode(),
            "query_string": b"", "headers": [(b"content-type", b"application/json")],
            "client": ("test", 1), "server": ("test", 80), "root_path": "",
        }, receive, send))
        status = next(message["status"] for message in messages if message["type"] == "http.response.start")
        content = b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body")
        return SimpleNamespace(status_code=status, text=content.decode(), json=lambda: json.loads(content))


class FineTuningConfigDebugTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
        )

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        with self.session_factory() as db:
            db.add(models.User(User_ID=1, Username="test", Password="x", Type_ID=1, Creator_ID=1))
            db.commit()
            db.add(models.Type(Type_ID=1, Typename="test", creater_id=1))
            db.commit()
            db.add(models.Module(Module_ID=17, Type_ID=1, ModuleAddress=17, creater_id=1))
            db.commit()
            for unit_id in (32, 64):
                db.add(models.Unit(Module_ID=17, Unit_ID=unit_id, creater_id=1))
            db.commit()
            for unit_id in (32, 64):
                db.add(models.Sensor(
                    Module_ID=17, Unit_ID=unit_id, sensor_ID=unit_id + 17,
                    sensordescript="压力传感器", Unit_address=0, IsRead=True, creater_id=1,
                ))
            db.commit()

        app = FastAPI()
        app.include_router(finetuning.router, prefix="/api/finetuning")

        def isolated_db():
            with self.session_factory() as db:
                yield db

        app.dependency_overrides[get_db] = isolated_db
        self.client = LocalASGIClient(app)

    def tearDown(self):
        self.engine.dispose()

    def payload(self, **overrides):
        return {
            "module_id": 17, "unit_id": 32, "device_id": 17, "sensor_id": 49,
            "devices": [{"device_id": 1, "parameter_name": "rotation", "initial": 3, "adjust": 2, "current": 5}],
            **overrides,
        }

    def test_debug_save_persists_without_any_drawing_and_keeps_arm_sensor_identity(self):
        for unit_id, axis in ((32, 1), (64, 4)):
            response = self.client.post("/api/finetuning/config", json=self.payload(
                unit_id=unit_id, sensor_id=unit_id + 17, is_debug=True, drawing_id=None,
                x=1.5, devices=[{"device_id": axis, "current": 6.25}],
            ))
            self.assertEqual(response.status_code, 200, response.text)
            saved = response.json()["data"]
            self.assertEqual(saved["sensor_id"], unit_id + 17)
            self.assertIs(saved["config"]["is_debug"], True)
            self.assertIsNone(saved["config"]["drawing_id"])
            with self.session_factory() as db:
                record = db.get(models.FineTuningConfig, saved["id"])
                config = json.loads(record.config_json)
                self.assertEqual(config, saved["config"])
                self.assertEqual(config["devices"][0]["device_id"], axis)
                self.assertEqual(config["devices"][0]["current"], 6.25)
                self.assertEqual(config["x"], 1.5)

    def test_normal_save_retains_the_drawing_id_in_config_json(self):
        response = self.client.post("/api/finetuning/config", json=self.payload(is_debug=False, drawing_id=12))
        self.assertEqual(response.status_code, 200, response.text)
        config = response.json()["data"]["config"]
        self.assertIs(config["is_debug"], False)
        self.assertEqual(config["drawing_id"], 12)
        with self.session_factory() as db:
            self.assertEqual(json.loads(db.query(models.FineTuningConfig).one().config_json), config)

    def test_legacy_request_without_debug_or_drawing_fields_still_saves(self):
        response = self.client.post("/api/finetuning/config", json=self.payload())
        self.assertEqual(response.status_code, 200, response.text)
        config = response.json()["data"]["config"]
        self.assertIs(config["is_debug"], False)
        self.assertIsNone(config["drawing_id"])
        self.assertEqual("raw", config["devices"][0]["position_mode"])
        self.assertEqual("command_start", config["devices"][0]["reference_source"])
        self.assertNotIn("adjust", config["devices"][0])
        self.assertIsNone(config["devices"][0]["requested_delta"])
        self.assertIsNone(config["devices"][0]["reference_position"])
        self.assertIsNone(config["devices"][0]["raw_current"])

    def test_relative_snapshot_keeps_command_and_measured_values(self):
        response = self.client.post("/api/finetuning/config", json=self.payload(
            is_debug=True,
            devices=[{
                "device_id": 1, "parameter_name": "rotation", "initial": 0,
                "requested_delta": 10, "current": 9.5, "position_mode": "relative",
                "reference_position": 37.25, "raw_current": 46.75,
            }, {
                "device_id": 21, "sensor_id": 49, "parameter_name": "pressure", "current": 1.5,
            }],
        ))
        self.assertEqual(response.status_code, 200, response.text)
        config = response.json()["data"]["config"]
        axis = config["devices"][0]
        self.assertEqual("relative", axis["position_mode"])
        self.assertEqual("command_start", axis["reference_source"])
        self.assertNotIn("adjust", axis)
        self.assertEqual(10, axis["requested_delta"])
        self.assertEqual(9.5, axis["current"])
        self.assertEqual(37.25, axis["reference_position"])
        self.assertEqual(46.75, axis["raw_current"])
        self.assertEqual("raw", config["devices"][1]["position_mode"])
        with self.session_factory() as db:
            self.assertEqual(json.loads(db.query(models.FineTuningConfig).one().config_json), config)

    def test_relative_snapshot_preserves_unavailable_measurements(self):
        response = self.client.post("/api/finetuning/config", json=self.payload(
            is_debug=True,
            devices=[{
                "device_id": 1, "position_mode": "relative", "current": None,
                "reference_position": None, "raw_current": None,
            }],
        ))
        self.assertEqual(response.status_code, 200, response.text)
        axis = response.json()["data"]["config"]["devices"][0]
        self.assertEqual("relative", axis["position_mode"])
        self.assertIsNone(axis["current"])
        self.assertIsNone(axis["reference_position"])
        self.assertIsNone(axis["raw_current"])

    def test_drawing_settled_snapshot_keeps_a_nonzero_fixed_reference_across_adjustments(self):
        for measured_delta, raw_current in ((9.5, 46.75), (20, 57.25)):
            response = self.client.post("/api/finetuning/config", json=self.payload(
                is_debug=False, drawing_id=12,
                devices=[{
                    "device_id": 1, "parameter_name": "rotation", "initial": 37.25,
                    "position_mode": "relative", "reference_source": "drawing_settled",
                    "reference_position": 37.25, "raw_current": raw_current,
                    "current": measured_delta, "requested_delta": 10,
                }],
            ))
            self.assertEqual(response.status_code, 200, response.text)
            saved = response.json()["data"]
            axis = saved["config"]["devices"][0]
            self.assertEqual("drawing_settled", axis["reference_source"])
            self.assertEqual(37.25, axis["initial"])
            self.assertEqual(37.25, axis["reference_position"])
            self.assertEqual(raw_current, axis["raw_current"])
            self.assertEqual(measured_delta, axis["current"])
            self.assertAlmostEqual(raw_current - axis["reference_position"], axis["current"])
            self.assertEqual(10, axis["requested_delta"])
            self.assertNotIn("adjust", axis)
            with self.session_factory() as db:
                record = db.get(models.FineTuningConfig, saved["id"])
                self.assertEqual(saved["config"], json.loads(record.config_json))
        with self.session_factory() as db:
            self.assertEqual(2, db.query(models.FineTuningConfig).count())

    def test_drawing_snapshot_before_reference_lock_preserves_null_reference_values(self):
        response = self.client.post("/api/finetuning/config", json=self.payload(
            is_debug=False, drawing_id=12,
            devices=[{
                "device_id": 1, "parameter_name": "rotation", "initial": None,
                "position_mode": "relative", "reference_source": "drawing_settled",
                "reference_position": None, "raw_current": 37.25,
                "current": None, "requested_delta": 10,
            }],
        ))
        self.assertEqual(response.status_code, 200, response.text)
        saved = response.json()["data"]
        axis = saved["config"]["devices"][0]
        self.assertEqual("drawing_settled", axis["reference_source"])
        self.assertIsNone(axis["initial"])
        self.assertIsNone(axis["reference_position"])
        self.assertIsNone(axis["current"])
        self.assertEqual(37.25, axis["raw_current"])
        self.assertEqual(10, axis["requested_delta"])
        with self.session_factory() as db:
            self.assertEqual(saved["config"], json.loads(db.get(models.FineTuningConfig, saved["id"]).config_json))

    def test_unknown_reference_sources_are_rejected_without_saving(self):
        response = self.client.post("/api/finetuning/config", json=self.payload(
            devices=[{"device_id": 1, "reference_source": "unknown"}],
        ))
        self.assertEqual(response.status_code, 422)
        with self.session_factory() as db:
            self.assertEqual(0, db.query(models.FineTuningConfig).count())

    def test_snapshot_preserves_unknown_values_and_historical_feedback_state(self):
        feedback_state = {"rotation": {"status": "waiting", "age_ms": None},
                          "pressure": {"status": "stale", "age_ms": 9000}}
        response = self.client.post("/api/finetuning/config", json=self.payload(
            is_debug=True, drawing_id=None, x=None, y=None, z=None,
            feedback_state=feedback_state,
            devices=[{"device_id": 1, "initial": None, "current": None},
                     {"device_id": 21, "sensor_id": 49, "initial": 1.25, "current": 1.5}],
        ))
        self.assertEqual(response.status_code, 200, response.text)
        config = response.json()["data"]["config"]
        self.assertIsNone(config["devices"][0]["initial"])
        self.assertIsNone(config["devices"][0]["current"])
        self.assertIsNone(config["x"])
        self.assertEqual(config["feedback_state"], feedback_state)
        with self.session_factory() as db:
            self.assertEqual(json.loads(db.query(models.FineTuningConfig).one().config_json), config)

    def test_debug_request_cannot_bind_a_drawing(self):
        response = self.client.post("/api/finetuning/config", json=self.payload(is_debug=True, drawing_id=12))
        self.assertEqual(response.status_code, 422)
        with self.session_factory() as db:
            self.assertEqual(db.query(models.FineTuningConfig).count(), 0)

    def test_invalid_drawing_numbers_do_not_create_records(self):
        for drawing_id in (0, -1, "invalid"):
            with self.subTest(drawing_id=drawing_id):
                response = self.client.post("/api/finetuning/config", json=self.payload(drawing_id=drawing_id))
                self.assertEqual(response.status_code, 422)
        with self.session_factory() as db:
            self.assertEqual(db.query(models.FineTuningConfig).count(), 0)

    def test_calibration_save_writes_the_zeroing_remark_into_notes(self):
        note = "校零：机械臂 1，三轴基准初始值 0.00/0.00/0.00（人工下发归位后保存）2026-11-11 20:20"
        response = self.client.post("/api/finetuning/config", json=self.payload(calibrated=True, notes=note))
        self.assertEqual(response.status_code, 200, response.text)
        saved = response.json()["data"]
        self.assertEqual(saved["notes"], note)
        self.assertIs(saved["config"]["calibrated"], True)
        with self.session_factory() as db:
            record = db.query(models.FineTuningConfig).one()
            # 备注列落库：翻数据库能直接看出这条是校零值，不是微调值
            self.assertEqual(record.notes, note)
            self.assertIs(json.loads(record.config_json)["calibrated"], True)

    def test_calibration_without_explicit_note_still_gets_a_zeroing_remark(self):
        response = self.client.post("/api/finetuning/config", json=self.payload(calibrated=True))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("校零", response.json()["data"]["notes"])

    def test_drawing_calibration_without_note_uses_actual_fixed_references_and_pending_values(self):
        response = self.client.post("/api/finetuning/config", json=self.payload(
            calibrated=True, is_debug=False, drawing_id=12,
            devices=[{
                "device_id": 1, "parameter_name": "rotation", "initial": 0,
                "reference_source": "drawing_settled", "reference_position": 37.25,
            }, {
                "device_id": 2, "parameter_name": "swing", "initial": None,
                "reference_source": "drawing_settled", "reference_position": None,
            }, {
                "device_id": 3, "parameter_name": "telescopic", "initial": 0,
                "reference_source": "drawing_settled", "reference_position": 7.5,
            }],
        ))
        self.assertEqual(response.status_code, 200, response.text)
        saved = response.json()["data"]
        note = saved["notes"]
        self.assertIn("校零", note)
        self.assertIn("图纸固定基准", note)
        self.assertIn("旋转 37.25°", note)
        self.assertIn("摆动 待采集", note)
        self.assertIn("伸缩 7.50mm", note)
        self.assertNotIn("按 0 记录", note)
        with self.session_factory() as db:
            self.assertEqual(note, db.get(models.FineTuningConfig, saved["id"]).notes)

    def test_plain_save_leaves_the_notes_column_empty(self):
        response = self.client.post("/api/finetuning/config", json=self.payload())
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIsNone(response.json()["data"]["notes"])


if __name__ == "__main__":
    unittest.main()
