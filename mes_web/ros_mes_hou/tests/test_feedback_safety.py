import asyncio
import json
import unittest
from unittest.mock import Mock, patch

from app.ros.normalizer import normalize_feedback_message, resolve_ack_module
from app.ros.profile import ROS1_PROFILE, ROS2_PROFILE
from app.ros.rosbridge import RosbridgeClient, build_fine_tuning_publish_payload


class FeedbackSafetyTest(unittest.TestCase):
    def test_missing_empty_invalid_and_nonfinite_positions_never_become_zero(self):
        for fields in ({}, {"position": []}, {"position": None}, {"position": "invalid"},
                       {"position": float("nan")}, {"position": float("inf")}, {"position": True}):
            with self.subTest(fields=fields):
                feedback = normalize_feedback_message("/hardware/rotation_feedback", {
                    "module_id": 0, "device_id": 1, **fields,
                })
                self.assertIsNone(feedback["position"])
                self.assertFalse(feedback["position_valid"])
                self.assertEqual(feedback["valid_fields"], [])
                json.dumps(feedback, allow_nan=False)

    def test_real_zero_is_valid_and_keeps_can_seg_namespace(self):
        feedback = normalize_feedback_message("/hardware/rotation_feedback", {
            "module_id": 0, "device_id": 1, "position": [0],
        })
        self.assertEqual(feedback["position"], 0)
        self.assertTrue(feedback["position_valid"])
        self.assertEqual(feedback["module_id"], 0)
        self.assertEqual(feedback["module_id_space"], "seg")

    def test_nonfinite_diagnostic_header_and_id_are_json_safe(self):
        feedback = normalize_feedback_message("/hardware/rotation_feedback", {
            "module_id": 0, "device_id": 1, "position": [0],
            "header": {"stamp": {"secs": float("nan"), "nsecs": float("inf")}},
            "id": {"value": float("-inf")},
        })
        self.assertEqual(feedback["header"], {"secs": "nan", "nsecs": "inf"})
        self.assertEqual(feedback["id"], {"value": "-inf"})
        self.assertTrue(feedback["position_valid"])
        json.dumps(feedback, allow_nan=False)

    def test_partial_imu_retains_only_valid_fields(self):
        feedback = normalize_feedback_message("/hardware/imu_angles", {
            "module_id": 0, "device_id": 21, "x": 0, "y": "invalid", "z": float("inf"),
            "rotation_angle": 1.5,
        })
        self.assertEqual(feedback["valid_fields"], ["rotation_angle", "x"])
        self.assertEqual(feedback["x"], 0)
        self.assertIsNone(feedback["y"])
        self.assertIsNone(feedback["z"])
        self.assertIsNone(feedback["swing_angle"])
        self.assertEqual(feedback["module_id_space"], "seg")
        json.dumps(feedback, allow_nan=False)

    def test_wrong_topic_axis_and_invalid_identifiers_are_not_measurements(self):
        cases = [("/hardware/rotation_feedback", 2), ("/hardware/sensor_feedback", 1),
                 ("/hardware/imu_angles", 9), ("/hardware/rotation_feedback", "invalid"),
                 ("/hardware/swing_feedback", 2.5)]
        for topic, device_id in cases:
            with self.subTest(topic=topic, device_id=device_id):
                feedback = normalize_feedback_message(topic, {"module_id": 0, "device_id": device_id, "position": 5})
                self.assertEqual(feedback["data_type"], "unknown")
                self.assertFalse(feedback["position_valid"])
                self.assertIsNone(feedback["position"])

    def test_other_topic_namespaces_are_not_all_assumed_to_be_seg(self):
        pressure = normalize_feedback_message("/hardware/sensor_feedback", {"module_id": 0, "device_id": 21, "position": 1})
        average = normalize_feedback_message("/hardware/pressure_avg", {"module_id": 17, "device_id": 21, "position": 1})
        vacuum = normalize_feedback_message("/hardware/vacuum_loss", {"module_id": 0, "device_id": 21, "position": 1})
        self.assertEqual(pressure["module_id_space"], "seg")
        self.assertEqual(average["module_id_space"], "business")
        # 本次已核查 hardware_node：失压与轴遥测同样取自 CAN SEG；均值仍用业务号。
        self.assertEqual(vacuum["module_id_space"], "seg")

    def test_ack_raw_and_fields_are_preserved_without_a_request_id(self):
        message = {"module_id": 0, "device_id": 1, "ack_msg": 1, "result": 0, "detail": 0}
        with patch("app.ros.normalizer.settings.ROS_MODULE_SEG_MAP", '{"17":0}'):
            feedback = normalize_feedback_message("/hardware/cmd_ack", message)
        self.assertEqual(feedback["data_type"], "cmd_ack")
        self.assertEqual(feedback["raw"], message)
        self.assertEqual(feedback["result"], 0)
        self.assertEqual(feedback["module_id_space"], "mixed")
        self.assertEqual(feedback["business_module_id"], 17)
        self.assertEqual(feedback["module_resolution"], "resolved")
        self.assertNotIn("request_id", feedback)

    def test_ack_seg_zero_can_be_resolved_only_with_a_unique_mapping(self):
        resolved = resolve_ack_module(0, '{"17":0}')
        self.assertEqual(resolved["module_candidates"], [17])
        self.assertEqual(resolved["business_module_id"], 17)
        self.assertEqual(resolved["module_resolution"], "resolved")
        ambiguous = resolve_ack_module(0, '{"17":0,"18":0}')
        self.assertEqual(ambiguous["module_candidates"], [17, 18])
        self.assertEqual(ambiguous["module_resolution"], "ambiguous")
        self.assertIsNone(ambiguous["business_module_id"])

    def test_ack_business_and_seg_overlap_is_ambiguous(self):
        feedback = resolve_ack_module(3, '{"17":3}')
        self.assertEqual(feedback["module_candidates"], [3, 17])
        self.assertEqual(feedback["module_resolution"], "ambiguous")
        self.assertIsNone(feedback["business_module_id"])

    def test_ack_unmapped_seg_remains_unknown_even_when_business_id_is_possible(self):
        feedback = resolve_ack_module(3, '{"17":0}')
        self.assertEqual(feedback["module_candidates"], [3])
        self.assertEqual(feedback["module_resolution"], "unknown")
        self.assertIsNone(feedback["business_module_id"])

    def test_ack_above_seg_range_has_only_a_business_candidate(self):
        feedback = resolve_ack_module(17, '{"17":0}')
        self.assertEqual(feedback["module_candidates"], [17])
        self.assertEqual(feedback["module_resolution"], "resolved")

    def test_bad_mapping_or_module_id_never_guesses_a_business_module(self):
        for mapping in ('invalid', '[]', '{"17":15}', '{"bad":0}', '{"17":true}'):
            with self.subTest(mapping=mapping):
                feedback = resolve_ack_module(17, mapping)
                self.assertEqual(feedback["module_resolution"], "unknown")
                self.assertIsNone(feedback["business_module_id"])
        for module_id in (None, -1, "invalid", True, 1.5):
            self.assertEqual(resolve_ack_module(module_id, '{"17":0}')["module_resolution"], "unknown")


class FakeSocket:
    def __init__(self, messages=()):
        self.sent = []
        self.messages = iter(messages)
        self.recv_count = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def send(self, value):
        self.sent.append(json.loads(value))

    async def recv(self):
        self.recv_count += 1
        raise AssertionError("No device acknowledgement is provided")

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self.messages)
        except StopIteration:
            raise StopAsyncIteration


class RosbridgeDeliverySafetyTest(unittest.TestCase):
    def test_plain_publish_does_not_claim_device_confirmation_in_either_ros_version(self):
        for profile in (ROS1_PROFILE, ROS2_PROFILE):
            with self.subTest(profile=profile.name):
                socket = FakeSocket()
                with patch("app.ros.rosbridge.websockets") as websocket:
                    websocket.connect = Mock(return_value=socket)
                    client = RosbridgeClient(profile, url="ws://test-only")
                    result = client.dispatch("fine_tuning", build_fine_tuning_publish_payload("rotation", 2, 17, 1, profile))
                self.assertEqual([item["op"] for item in socket.sent], ["advertise", "publish"])
                self.assertEqual(socket.recv_count, 0)
                self.assertTrue(result["sent"])
                self.assertIsNone(result["confirmed"])
                self.assertEqual(result["confirmation_status"], "not_requested")

    def test_drawing_publish_also_remains_unconfirmed(self):
        socket = FakeSocket()
        with patch("app.ros.rosbridge.websockets") as websocket:
            websocket.connect = Mock(return_value=socket)
            client = RosbridgeClient(ROS1_PROFILE, url="ws://test-only")
            result = client.dispatch("drawing_path", {"topic": "/test", "message_type": "std_msgs/String", "message": {"data": "test"}})
        self.assertIsNone(result["confirmed"])
        self.assertEqual(result["confirmation_status"], "not_requested")

    def test_malformed_feedback_frames_do_not_end_the_stream(self):
        socket = FakeSocket([
            "not JSON", b"\xff", "[]",
            json.dumps({"op": "publish", "topic": "/hardware/rotation_feedback", "msg": "invalid"}),
            json.dumps({"op": "publish", "topic": "/hardware/rotation_feedback", "msg": {"module_id": {}, "device_id": [], "position": "bad"}}),
            json.dumps({"op": "publish", "topic": "/hardware/rotation_feedback", "msg": {"module_id": 0, "device_id": 1, "position": [0]}}),
        ])

        async def collect():
            return [item async for item in RosbridgeClient(ROS1_PROFILE, url="ws://test-only").stream_feedback()]

        with patch("app.ros.rosbridge.websockets") as websocket:
            websocket.connect = Mock(return_value=socket)
            feedback = asyncio.run(collect())
        self.assertTrue(feedback[-1]["position_valid"])
        self.assertEqual(feedback[-1]["position"], 0)
        self.assertFalse(any(item["data_type"] == "error" for item in feedback))


if __name__ == "__main__":
    unittest.main()
