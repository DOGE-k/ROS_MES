import json
import os
import unittest
from unittest.mock import Mock, patch

from app.services import ros_control


class FakeWebSocket:
    def __init__(self, sent_messages=None):
        self.sent_messages = sent_messages if sent_messages is not None else []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def send(self, message):
        self.sent_messages.append(message)


class EmergencyStopPayloadTest(unittest.IsolatedAsyncioTestCase):
    async def test_emergency_stop_publishes_system_level_softstop(self):
        # V2 IntCmd 寻址：module_id=0 / device_id=0 表示系统级指令，position=[0x01] 为急停命令
        sent_messages = []
        fake_ws = FakeWebSocket(sent_messages)

        with patch.object(ros_control, "websockets") as websockets_mock:
            websockets_mock.connect = Mock(return_value=fake_ws)

            success = await ros_control.trigger_emergency_stop()

        self.assertTrue(success)
        payload = json.loads(sent_messages[0])
        self.assertEqual(payload["topic"], "/control/softstop")
        self.assertEqual(payload["msg"]["module_id"], 0)
        self.assertEqual(payload["msg"]["device_id"], 0)
        self.assertEqual(payload["msg"]["position"], [0x01])

    async def test_emergency_stop_uses_rosbridge_url_from_environment(self):
        # 急停必须跟随 ROSBRIDGE_URL，不能再把地址写死在函数里
        fake_ws = FakeWebSocket()

        with patch.dict(os.environ, {"ROSBRIDGE_URL": "ws://127.0.0.1:9099"}):
            with patch.object(ros_control, "websockets") as websockets_mock:
                websockets_mock.connect = Mock(return_value=fake_ws)

                success = await ros_control.trigger_emergency_stop()

        self.assertTrue(success)
        websockets_mock.connect.assert_called_once()
        called_url = websockets_mock.connect.call_args.args[0]
        self.assertEqual(called_url, "ws://127.0.0.1:9099")

    async def test_emergency_stop_falls_back_to_default_url_without_env(self):
        fake_ws = FakeWebSocket()

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ROSBRIDGE_URL", None)
            with patch.object(ros_control, "websockets") as websockets_mock:
                websockets_mock.connect = Mock(return_value=fake_ws)

                success = await ros_control.trigger_emergency_stop()

        self.assertTrue(success)
        self.assertEqual(
            websockets_mock.connect.call_args.args[0],
            ros_control.DEFAULT_ROSBRIDGE_URL,
        )

    async def test_emergency_stop_returns_false_when_connection_fails(self):
        # 连不上 rosbridge 时必须返回 False，接口层据此报 500，不能报发送成功
        with patch.object(ros_control, "websockets") as websockets_mock:
            websockets_mock.connect = Mock(side_effect=OSError("connection refused"))

            success = await ros_control.trigger_emergency_stop()

        self.assertFalse(success)


if __name__ == "__main__":
    unittest.main()
