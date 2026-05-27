import unittest
from unittest.mock import Mock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.endpoints.coordination import proxy_pointcloud_view, send_coordination
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
            wait_for_views=lambda: True,
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
                wait_for_views=lambda: True,
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

    def test_send_coordination_returns_pointcloud_view_urls(self):
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        try:
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
                dispatcher=DummyDispatcher(),
                wait_for_views=lambda: True,
            )

            self.assertEqual(response["views"]["top"], "/api/coordination/views/top")
            self.assertEqual(response["views"]["front"], "/api/coordination/views/front")
            self.assertEqual(response["views"]["side"], "/api/coordination/views/side")
        finally:
            db.close()

    def test_proxy_pointcloud_view_returns_png_response_from_ros_view_server(self):
        response_mock = Mock()
        response_mock.read.return_value = b"png-bytes"
        response_mock.headers = {"Content-Type": "image/png"}
        response_mock.__enter__ = Mock(return_value=response_mock)
        response_mock.__exit__ = Mock(return_value=False)

        with patch("app.api.endpoints.coordination.urlopen", return_value=response_mock) as urlopen_mock:
            response = proxy_pointcloud_view("top")

        self.assertEqual(response.media_type, "image/png")
        self.assertEqual(response.body, b"png-bytes")
        urlopen_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
