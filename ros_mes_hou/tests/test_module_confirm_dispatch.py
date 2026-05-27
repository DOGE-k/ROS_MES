import unittest
from unittest.mock import Mock, patch

from app.api.endpoints.module import lock_and_dispatch_module
from app.services.rosbridge_gateway import (
    RosbridgeError,
    RosbridgeDispatcher,
    build_module_confirm_publish_payload,
)


class DummyDispatcher:
    def __init__(self):
        self.calls = []

    def dispatch(self, action, payload):
        self.calls.append((action, payload))
        return {"sent": True, "mode": "test", "action": action, "payload": payload}


class ModuleConfirmDispatchTest(unittest.TestCase):
    def test_build_module_confirm_payload_matches_topic_contract(self):
        payload = build_module_confirm_publish_payload(18)

        self.assertEqual(payload["topic"], "/control/module_cmd")
        self.assertEqual(payload["message_type"], "robot_control_backend/IntCmd")
        self.assertEqual(payload["message"]["module_id"], 18)
        self.assertEqual(payload["message"]["device_id"], 0)
        self.assertEqual(payload["message"]["position"], [100])
        self.assertIn("stamp", payload["message"]["header"])

    def test_lock_module_dispatches_module_confirm_topic_before_returning_success(self):
        dispatcher = DummyDispatcher()

        response = lock_and_dispatch_module(
            {"x": 1, "y": 2, "module_id": 18, "device_id": 3, "position": 0},
            dispatcher=dispatcher,
        )

        self.assertEqual(response["code"], 200)
        self.assertEqual(response["data"]["module_id"], 18)
        self.assertEqual(response["dispatch"]["action"], "module_confirm")
        action, payload = dispatcher.calls[0]
        self.assertEqual(action, "module_confirm")
        self.assertEqual(payload["topic"], "/control/module_cmd")
        self.assertEqual(payload["message_type"], "robot_control_backend/IntCmd")
        self.assertEqual(payload["message"]["module_id"], 18)
        self.assertEqual(payload["message"]["device_id"], 0)
        self.assertEqual(payload["message"]["position"], [100])
        self.assertEqual(payload["business"]["x"], 1)
        self.assertEqual(payload["business"]["y"], 2)
        self.assertEqual(payload["business"]["device_id"], 3)

    def test_module_confirm_dispatch_subscribes_success_topic_and_waits_for_matching_ack(self):
        sent_messages = []

        class FakeWebSocket:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def send(self, message):
                sent_messages.append(message)

            async def recv(self):
                return (
                    '{"op":"publish","topic":"/control/module_confirm_success",'
                    '"msg":{"module_id":18,"device_id":0,"position":[100]}}'
                )

        dispatcher = RosbridgeDispatcher(url="ws://test", timeout=0.1)
        payload = build_module_confirm_publish_payload(18)

        with patch("app.services.rosbridge_gateway.websockets") as websockets_mock:
            websockets_mock.connect = Mock(return_value=FakeWebSocket())
            result = dispatcher.dispatch("module_confirm", payload)

        self.assertTrue(result["confirmed"])
        self.assertEqual(result["confirm_topic"], "/control/module_confirm_success")
        self.assertIn('"op": "subscribe"', sent_messages[0])
        self.assertIn('/control/module_confirm_success', sent_messages[0])
        self.assertIn('"op": "subscribe"', sent_messages[1])
        self.assertIn('/hardware/web_module_cmd', sent_messages[1])
        self.assertIn('"op": "advertise"', sent_messages[2])
        self.assertIn('"op": "publish"', sent_messages[3])

    def test_module_confirm_dispatch_subscribes_hardware_web_cmd_and_fails_on_position_one(self):
        sent_messages = []

        class FakeWebSocket:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def send(self, message):
                sent_messages.append(message)

            async def recv(self):
                return (
                    '{"op":"publish","topic":"/hardware/web_module_cmd",'
                    '"msg":{"module_id":18,"device_id":0,"position":[1]}}'
                )

        dispatcher = RosbridgeDispatcher(url="ws://test", timeout=0.1)
        payload = build_module_confirm_publish_payload(18)

        with patch("app.services.rosbridge_gateway.websockets") as websockets_mock:
            websockets_mock.connect = Mock(return_value=FakeWebSocket())
            with self.assertRaises(RosbridgeError) as exc:
                dispatcher.dispatch("module_confirm", payload)

        self.assertIn("module confirm failed", str(exc.exception))
        self.assertIn('/control/module_confirm_success', sent_messages[0])
        self.assertIn('/hardware/web_module_cmd', sent_messages[1])
        self.assertIn('"op": "advertise"', sent_messages[2])
        self.assertIn('"op": "publish"', sent_messages[3])


if __name__ == "__main__":
    unittest.main()
