import ast
from pathlib import Path
import unittest

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from starlette.routing import Match

from app.api.endpoints import device_api, sensors_api, unit_api
from app.db.database import Base
from app.db import models
from app.schemas.sensors import SensorCreate, SensorUpdate
from app.schemas.unit import UnitCreate


class DeviceConfigTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.db.add(models.User(User_ID=1, Username="admin", Password="x", Type_ID=1, Creator_ID=1))
        self.db.flush()
        self.db.add(models.Type(Type_ID=1, Typename="type", creater_id=1))
        self.db.flush()
        for module_id in (17, 18):
            self.db.add(models.Module(Module_ID=module_id, Type_ID=1, ModuleAddress=str(module_id), creater_id=1))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def add_unit(self, unit_id=128, module_id=17):
        return unit_api.create_unit(UnitCreate(Unit_ID=unit_id, Module_ID=module_id), self.db)["data"]

    def add_sensor(self, label="压力传感器", unit_id=128, module_id=17, **kwargs):
        return sensors_api.create_sensor(SensorCreate(
            Unit_ID=unit_id, Module_ID=module_id, sensordescript=label, **kwargs,
        ), self.db)["data"]

    def test_config_route_is_not_shadowed_by_device_id_and_does_not_write_data(self):
        scope = {"type": "http", "path": "/config", "method": "GET"}
        route = next(r for r in device_api.router.routes if r.matches(scope)[0] == Match.FULL)
        self.assertIs(route.endpoint, device_api.device_config)
        config = route.endpoint()["data"]
        self.assertEqual([32, 64, 96, 128, 160], [arm["value"] for arm in config["arms"]])
        self.assertEqual(0, self.db.query(models.Unit).count())
        self.assertEqual(0, self.db.query(models.Sensor).count())

    def test_catalog_and_generated_records_match_all_five_arms_in_seed_script(self):
        seed_path = Path(__file__).resolve().parents[3] / "sqlite_create.py"
        tree = ast.parse(seed_path.read_text(encoding="utf-8-sig"))
        seed_node = next(n for n in ast.walk(tree) if isinstance(n, ast.Assign)
                         and any(isinstance(t, ast.Name) and t.id == "unit_sensor_data" for t in n.targets))
        config = device_api.device_config()["data"]
        for unit_id, _, sensors in ast.literal_eval(seed_node.value):
            self.add_unit(unit_id)
            for sensor_id, label, is_read, _, address in sensors:
                with self.subTest(unit_id=unit_id, label=label):
                    option = next(s for s in config["sensor_types"] if s["label"] == label)
                    self.assertEqual(sensor_id, option["sensor_ids"][str(unit_id)])
                    item = self.add_sensor(label, unit_id)
                    self.assertEqual((sensor_id, address, is_read), (item.sensor_ID, item.Unit_address, item.IsRead))

    def test_unknown_arm_rejected(self):
        with self.assertRaises(ValidationError):
            UnitCreate(Unit_ID=192, Module_ID=17)

    def test_missing_module_rejected(self):
        with self.assertRaises(HTTPException) as caught:
            self.add_unit(module_id=999)
        self.assertEqual(422, caught.exception.status_code)

    def test_wrong_sensor_id_address_or_type_rejected_without_writes(self):
        self.add_unit()
        for fields in ({"sensor_ID": 21}, {"Unit_address": 4}, {"sensordescript": "unknown"}):
            with self.subTest(fields=fields), self.assertRaises(HTTPException) as caught:
                payload = {"Unit_ID": 128, "Module_ID": 17, "sensordescript": "压力传感器", **fields}
                sensors_api.create_sensor(SensorCreate(**payload), self.db)
            self.assertEqual(422, caught.exception.status_code)
        self.assertEqual(0, self.db.query(models.Sensor).count())

    def test_legacy_explicit_sensor_number_is_accepted_if_consistent(self):
        self.add_unit()
        item = self.add_sensor(sensor_ID=145, Unit_address=0)
        self.assertEqual(145, item.sensor_ID)

    def test_unit_row_id_must_match_business_unit_and_module(self):
        source = self.add_unit()
        self.add_unit(160)
        with self.assertRaises(HTTPException) as caught:
            self.add_sensor(unit_id=160, unit_row_id=source.id)
        self.assertEqual(422, caught.exception.status_code)

    def test_edit_type_and_move_arm_regenerates_number_and_address(self):
        self.add_unit()
        target = self.add_unit(160, 18)
        item = self.add_sensor()
        result = sensors_api.update_sensor(item.id, SensorUpdate(
            unit_row_id=target.id, sensordescript="陀螺仪传感器",
        ), self.db)["data"]
        self.assertEqual((18, 160, 178, 4), (result.Module_ID, result.Unit_ID, result.sensor_ID, result.Unit_address))

    def test_duplicate_create_and_move_return_conflict(self):
        self.add_unit()
        self.add_unit(160)
        original = self.add_sensor()
        self.add_sensor(unit_id=160)
        with self.assertRaises(HTTPException) as caught:
            self.add_sensor()
        self.assertEqual(409, caught.exception.status_code)
        with self.assertRaises(HTTPException) as caught:
            sensors_api.update_sensor(original.id, SensorUpdate(Unit_ID=160), self.db)
        self.assertEqual(409, caught.exception.status_code)
        self.assertEqual(128, original.Unit_ID)

    def test_readding_deleted_records_reuses_unique_business_number(self):
        unit = self.add_unit()
        unit_api.delete_unit(unit.id, self.db)
        self.assertEqual(unit.id, self.add_unit().id)
        sensor = self.add_sensor()
        sensors_api.delete_sensor(sensor.id, self.db)
        self.assertEqual(sensor.id, self.add_sensor().id)
        self.assertEqual(1, self.db.query(models.Unit).count())
        self.assertEqual(1, self.db.query(models.Sensor).count())

    def test_edit_into_deleted_sensor_number_is_conflict_instead_of_integrity_error(self):
        self.add_unit()
        original = self.add_sensor()
        deleted = self.add_sensor("陀螺仪传感器")
        sensors_api.delete_sensor(deleted.id, self.db)
        with self.assertRaises(HTTPException) as caught:
            sensors_api.update_sensor(original.id, SensorUpdate(sensordescript="陀螺仪传感器"), self.db)
        self.assertEqual(409, caught.exception.status_code)

    def test_notes_only_edit_preserves_legacy_number(self):
        self.add_unit()
        self.db.add(models.Sensor(sensor_ID=999, sensordescript="legacy custom", IsRead=1, Module_ID=17,
                                  Unit_ID=128, Unit_address=9, creater_id=1))
        self.db.commit()
        item = self.db.query(models.Sensor).one()
        sensors_api.update_sensor(item.id, SensorUpdate(Notes="reviewed"), self.db)
        self.assertEqual((999, 9, "reviewed"), (item.sensor_ID, item.Unit_address, item.Notes))


if __name__ == "__main__":
    unittest.main()
