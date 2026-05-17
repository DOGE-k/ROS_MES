import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.endpoints import control
from app.db import models
from app.db.database import Base
from app.schemas.finetuning import FineTuningCreate


class DummyDispatcher:
    def __init__(self):
        self.calls = []

    def dispatch(self, action, payload):
        self.calls.append((action, payload))
        return {"sent": True, "mode": "test", "action": action, "payload": payload}


class ControlFineTuningEndpointTest(unittest.TestCase):
    def test_send_fine_tuning_returns_axis_feedback_and_records_device_field(self):
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        db = SessionLocal()
        try:
            db.add(
                models.Device(
                    Device_ID=2,
                    Model_ID=17,
                    DeviceAddress=18,
                    Devicedescript="test module",
                    creater_id=1,
                    del_flag=False,
                )
            )
            db.commit()

            dispatcher = DummyDispatcher()
            response = control.send_fine_tuning(
                record=FineTuningCreate(
                    module_id=18,
                    device_id=2,
                    unit_id=32,
                    unit_row_id=7,
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
            self.assertEqual(response["dispatch"]["payload"]["business"]["unit_row_id"], 7)
            self.assertEqual(response["dispatch"]["payload"]["parameter_name"], "rotation")
            saved = db.query(models.FineTuning).one()
            self.assertEqual(saved.Device_ID, 2)
            self.assertEqual(saved.DeviceAddress, 18)
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
                            module_id=99,
                            device_id=5,
                            unit_id=32,
                            unit_row_id=7,
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
