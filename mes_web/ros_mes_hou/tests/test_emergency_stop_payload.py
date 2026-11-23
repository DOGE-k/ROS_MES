import json
import unittest
from unittest.mock import Mock, patch

from app.core.config import settings
from app.ros.profile import ROS1_PROFILE
from app.ros.rosbridge import RosbridgeClient


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

        client = RosbridgeClient(ROS1_PROFILE, url="ws://test")
        with patch("app.ros.rosbridge.websockets") as websockets_mock:
            websockets_mock.connect = Mock(return_value=fake_ws)

            success = await client.publish_softstop()

        self.assertTrue(success)
        self.assertEqual(json.loads(sent_messages[0])["op"], "advertise")
        payload = json.loads(sent_messages[-1])
        self.assertEqual(payload["op"], "publish")
        self.assertEqual(payload["topic"], "/control/softstop")
        self.assertEqual(payload["msg"]["module_id"], 0)
        self.assertEqual(payload["msg"]["device_id"], 0)
        self.assertEqual(payload["msg"]["position"], [0x01])

    async def test_emergency_stop_uses_rosbridge_url_from_config(self):
        # 急停地址必须跟随统一配置（ROSBRIDGE_URL），不能再把地址写死在传输层里
        fake_ws = FakeWebSocket()

        with patch.object(settings, "ROSBRIDGE_URL", "ws://127.0.0.1:9099"):
            client = RosbridgeClient(ROS1_PROFILE)
            with patch("app.ros.rosbridge.websockets") as websockets_mock:
                websockets_mock.connect = Mock(return_value=fake_ws)

                success = await client.publish_softstop()

        self.assertTrue(success)
        websockets_mock.connect.assert_called_once()
        called_url = websockets_mock.connect.call_args.args[0]
        self.assertEqual(called_url, "ws://127.0.0.1:9099")

    async def test_emergency_stop_url_defaults_to_central_config(self):
        # 不传 url 时跟随 core/config 的 ROSBRIDGE_URL（env 可覆盖），传输层无硬编码地址
        self.assertEqual(RosbridgeClient(ROS1_PROFILE).url, settings.ROSBRIDGE_URL)

    async def test_emergency_stop_returns_false_when_connection_fails(self):
        # 连不上 rosbridge 时必须返回 False，接口层据此报 500，不能报发送成功
        client = RosbridgeClient(ROS1_PROFILE, url="ws://test")
        with patch("app.ros.rosbridge.websockets") as websockets_mock:
            websockets_mock.connect = Mock(side_effect=OSError("connection refused"))

            success = await client.publish_softstop()

        self.assertFalse(success)


    async def test_emergency_stop_release_publishes_to_release_topic(self):
        # 急停解除：/control/softstop_release → softstop_node 转发 /arm/cmd_vel [0x04]
        sent_messages = []
        fake_ws = FakeWebSocket(sent_messages)

        client = RosbridgeClient(ROS1_PROFILE, url="ws://test")
        with patch("app.ros.rosbridge.websockets") as websockets_mock:
            websockets_mock.connect = Mock(return_value=fake_ws)

            success = await client.publish_stop_release()

        self.assertTrue(success)
        payload = json.loads(sent_messages[-1])
        self.assertEqual(payload["op"], "publish")
        self.assertEqual(payload["topic"], "/control/softstop_release")
        self.assertEqual(payload["msg"]["module_id"], 0)
        self.assertEqual(payload["msg"]["device_id"], 0)
        self.assertEqual(payload["msg"]["position"], [0x01])


if __name__ == "__main__":
    unittest.main()
