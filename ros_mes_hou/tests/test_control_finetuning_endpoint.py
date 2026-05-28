import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.endpoints import control
from app.db.database import Base
from app.db import models
from app.schemas.finetuning import FineTuningCreate


class DummyDispatcher:
    def __init__(self):
        self.calls = []

    def dispatch(self, action, payload):
        self.calls.append((action, payload))
        return {"sent": True, "mode": "test", "action": action, "payload": payload}


class ControlFineTuningEndpointTest(unittest.TestCase):
    def test_send_fine_tuning_returns_axis_feedback_and_records_new_fields(self):
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        db = SessionLocal()
        try:
            db.add(models.User(User_ID=1, Username="admin", Password="x", Type_ID=1, Creator_ID=1))
            db.add(models.Type(Type_ID=1, Typename="type", creater_id=1))
            db.add(models.Module(Module_ID=17, Type_ID=1, ModuleAddress="17", Moduledescript="test module", creater_id=1))
            db.add(models.Unit(Unit_ID=32, UnitDescript="arm", Module_ID=17, creater_id=1))
            db.commit()

            dispatcher = DummyDispatcher()
            response = control.send_fine_tuning(
                record=FineTuningCreate(
                    module_id=17,
                    device_id=2,
                    unit_id=32,
                    parameter_name="rotation",
                    position=8.5,
                ),
                db=db,
                dispatcher=dispatcher,
            )

            self.assertEqual(response["code"], 200)
            self.assertEqual(response["data"][0]["device_id"], 2)
            self.assertEqual(response["data"][0]["position"], 8.5)
            self.assertEqual(response["dispatch"]["action"], "fine_tuning")
            self.assertEqual(response["dispatch"]["payload"]["topic"], "/control/adjust_rotation_cmd")
            self.assertEqual(response["dispatch"]["payload"]["message"]["module_id"], 17)
            self.assertEqual(response["dispatch"]["payload"]["message"]["device_id"], 33)
            self.assertEqual(response["dispatch"]["payload"]["message"]["position"], [8.5])
            self.assertEqual(response["dispatch"]["payload"]["business"]["device_id"], 2)
            self.assertEqual(response["dispatch"]["payload"]["business"]["unit_id"], 32)
            self.assertEqual(response["dispatch"]["payload"]["parameter_name"], "rotation")
            saved = db.query(models.FineTuning).one()
            self.assertEqual(saved.module_id, 17)
            self.assertEqual(saved.unit_id, 32)
            self.assertEqual(saved.parameter_name, "rotation")
        finally:
            db.close()

    def test_send_fine_tuning_maps_all_axis_parameters_to_ros_topics(self):
        cases = [
            ("rotation", "/control/adjust_rotation_cmd", 33),
            ("swing", "/control/adjust_swing_cmd", 34),
            ("telescopic", "/control/adjust_telescopic_cmd", 35),
        ]

        for parameter_name, expected_topic, expected_device_id in cases:
            with self.subTest(parameter_name=parameter_name):
                engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
                Base.metadata.create_all(bind=engine)
                SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
                db = SessionLocal()
                try:
                    dispatcher = DummyDispatcher()
                    control.send_fine_tuning(
                        record=FineTuningCreate(
                            module_id=17,
                            device_id=5,
                            unit_id=32,
                            parameter_name=parameter_name,
                            position=3.25,
                        ),
                        db=db,
                        dispatcher=dispatcher,
                    )

                    _, payload = dispatcher.calls[0]
                    self.assertEqual(payload["topic"], expected_topic)
                    self.assertEqual(payload["message"]["module_id"], 17)
                    self.assertEqual(payload["message"]["device_id"], expected_device_id)
                    self.assertEqual(payload["message"]["position"], [3.25])
                finally:
                    db.close()


if __name__ == "__main__":
    unittest.main()
