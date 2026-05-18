import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.endpoints.coordination import send_coordination
from app.db import models
from app.db.database import Base


class DummyDispatcher:
    def __init__(self):
        self.calls = []

    def dispatch(self, action, payload):
        self.calls.append((action, payload))
        return {"sent": True, "mode": "test", "action": action, "payload": payload}


class CoordinationPayloadTest(unittest.TestCase):
    def test_send_coordination_accepts_unit_and_drawing_without_xyz(self):
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        dispatcher = DummyDispatcher()
        db.add(
            models.User(
                User_ID=1,
                Username="tester",
                Password="pwd",
                Type_ID=2,
                Creator_ID=1,
                del_flag=False,
            )
        )
        db.add(
            models.Drawing(
                Drawing_ID=5,
                Drawingname="drawing",
                Drawingdescripte="",
                Drawingfile=r"D:\drawings\part.json",
                Creator_ID=1,
                NewVersion_ID=1,
                del_flag=False,
            )
        )
        db.commit()
        response = send_coordination(
            {
                "module_id": 18,
                "device_id": 1,
                "unit_id": 32,
                "unit_row_id": 7,
                "drawing_id": 5,
            },
            db=db,
            dispatcher=dispatcher,
        )

        self.assertEqual(response["code"], 200)
        self.assertEqual(response["data"]["module_id"], 18)
        self.assertEqual(response["data"]["device_id"], 1)
        self.assertEqual(response["data"]["unit_id"], 32)
        self.assertEqual(response["data"]["unit_row_id"], 7)
        self.assertEqual(response["data"]["drawing_id"], 5)
        db.close()

    def test_send_coordination_dispatches_drawing_file_path_to_ros_topic(self):
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        try:
            db.add(
                models.User(
                    User_ID=1,
                    Username="tester",
                    Password="pwd",
                    Type_ID=2,
                    Creator_ID=1,
                    del_flag=False,
                )
            )
            db.add(
                models.Drawing(
                    Drawing_ID=5,
                    Drawingname="drawing",
                    Drawingdescripte="",
                    Drawingfile=r"D:\drawings\part.json",
                    Creator_ID=1,
                    NewVersion_ID=1,
                    del_flag=False,
                )
            )
            db.commit()
            dispatcher = DummyDispatcher()

            response = send_coordination(
                {
                    "module_id": 18,
                    "device_id": 1,
                    "unit_id": 32,
                    "unit_row_id": 7,
                    "drawing_id": 5,
                },
                db=db,
                dispatcher=dispatcher,
            )

            self.assertEqual(response["code"], 200)
            self.assertEqual(response["dispatch"]["action"], "drawing_path")
            _, payload = dispatcher.calls[0]
            self.assertEqual(payload["topic"], "/frontend_pointcloud_topic")
            self.assertEqual(payload["message_type"], "std_msgs/String")
            self.assertEqual(payload["message"]["data"], '{"file_path":"D:\\\\drawings\\\\part.json"}')
            self.assertEqual(payload["business"]["drawing_id"], 5)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
