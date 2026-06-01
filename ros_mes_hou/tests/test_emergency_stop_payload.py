import json
import unittest
from unittest.mock import Mock, patch

from app.services import ros_control


class EmergencyStopPayloadTest(unittest.IsolatedAsyncioTestCase):
    async def test_emergency_stop_publishes_softstop_device_one_with_empty_position(self):
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
        self.assertEqual(payload["msg"]["module_id"], 17)
        self.assertEqual(payload["msg"]["device_id"], 1)
        self.assertEqual(payload["msg"]["position"], [])


if __name__ == "__main__":
    unittest.main()
