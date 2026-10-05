import json
import unittest
from unittest.mock import Mock, patch

from app.services import ros_control


class EmergencyStopPayloadTest(unittest.IsolatedAsyncioTestCase):
    async def test_emergency_stop_publishes_system_level_softstop(self):
        # V2 IntCmd 寻址：module_id=0 / device_id=0 表示系统级指令，position=[0x01] 为急停命令
        sent_messages = []

        class FakeWebSocket:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def send(self, message):
                sent_messages.append(message)

        with patch.object(ros_control, "websockets") as websockets_mock:
            websockets_mock.connect = Mock(return_value=FakeWebSocket())

            success = await ros_control.trigger_emergency_stop()

        self.assertTrue(success)
        payload = json.loads(sent_messages[0])
        self.assertEqual(payload["topic"], "/control/softstop")
        self.assertEqual(payload["msg"]["module_id"], 0)
        self.assertEqual(payload["msg"]["device_id"], 0)
        self.assertEqual(payload["msg"]["position"], [0x01])


if __name__ == "__main__":
    unittest.main()
