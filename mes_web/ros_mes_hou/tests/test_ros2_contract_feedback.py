"""Fixed proposed-contract samples; no ROS, sockets, application or database."""
from copy import deepcopy
import unittest

from app.ros2_contract.feedback import parse_feedback
from app.ros2_contract.validation import ContractError


HEADER = {"stamp": {"sec": 1795057200, "nanosec": 123456789}, "frame_id": "module_0"}


def payload(device_id, module_id=0, **fields):
    return {
        "header": deepcopy(HEADER),
        "module_id": module_id,
        "device_id": device_id,
        **fields,
    }


SAMPLES = {
    "SensorCmd": payload(31, id=0, position=[0.0]),
    "VacuumLoss": payload(32, pressure_raw=-1234, loss_threshold=250),
    "TuoLuoYi": payload(36, swing_angle=0, rotation_angle=-1.5, x=2, y=3, z=4),
    "GyroFeedback": payload(
        40, accel_x=0, accel_y=1, accel_z=-9.81, gyro_x=-2, gyro_y=0, gyro_z=3
    ),
    "Feedback": payload(4, position=[12.5]),
    "AxisStatus": payload(2, status_bits=257, axis_state=0, base_valid=1),
    "ArriveNotification": payload(1, angle=12345, pos_error=-5, status_bits=4, flags=3),
    "StopNotification": payload(6, stop_reason=1, output_level=0),
    "CmdAck": payload(7, ack_msg=0, result=0, detail=0),
    "AxisFault": payload(11, fault_bits=65, local_action=1, detail=2, duration_ms=300),
    "LimitEvent": payload(15, limit_type=2, output_level=0),
    "ModuleStatus": payload(
        0,
        seg=0,
        status=1,
        arm_slot=2,
        axis_base=4,
        exist_mask=7,
        ready_mask=7,
        module_state=0,
        token=1234,
    ),
}


class Ros2FeedbackSamplesTest(unittest.TestCase):
    def test_pressure_segment_and_zero_measurement_are_preserved(self):
        result = parse_feedback("SensorCmd", SAMPLES["SensorCmd"])
        self.assertTrue(result.is_known)
        self.assertEqual((result.address.module_id, result.address.device_id), (0, 31))
        self.assertEqual(result.values, {"id": 0, "position": [0.0]})
        self.assertEqual(result.units, {"position": "N"})
        self.assertEqual(result.pending, ())

    def test_pressure_top_id_and_counter_boundary(self):
        result = parse_feedback("SensorCmd", payload(35, module_id=14, id=255, position=[12]))
        self.assertEqual(result.values, {"id": 255, "position": [12.0]})
        self.assertEqual(result.address.module_id, 14)

    def test_imu_pose_keeps_coordinate_and_angle_units_distinct(self):
        result = parse_feedback("TuoLuoYi", SAMPLES["TuoLuoYi"])
        self.assertEqual(
            result.values,
            {"swing_angle": 0.0, "rotation_angle": -1.5, "x": 2.0, "y": 3.0, "z": 4.0},
        )
        self.assertEqual(
            result.units,
            {"swing_angle": "degree", "rotation_angle": "degree", "x": "cm", "y": "cm", "z": "cm"},
        )
        self.assertEqual(result.address.device_id, 36)

    def test_raw_gyro_has_six_distinct_measurements(self):
        result = parse_feedback("GyroFeedback", SAMPLES["GyroFeedback"])
        self.assertEqual(
            result.values,
            {"accel_x": 0.0, "accel_y": 1.0, "accel_z": -9.81, "gyro_x": -2.0, "gyro_y": 0.0, "gyro_z": 3.0},
        )
        self.assertEqual(result.units["accel_z"], "m/s²")
        self.assertEqual(result.units["gyro_z"], "degree/s")
        self.assertEqual(result.address.device_id, 40)

    def test_rotation_and_swing_feedback_are_degrees_without_rescaling(self):
        for device_id in (1, 2, 4, 14):
            with self.subTest(device_id=device_id):
                result = parse_feedback("Feedback", payload(device_id, position=[12.5]))
                self.assertEqual(result.values, {"position": [12.5]})
                self.assertEqual(result.units, {"position": "degree"})
                self.assertEqual(result.pending, ())

    def test_telescopic_feedback_keeps_unconfirmed_unit(self):
        result = parse_feedback("Feedback", payload(3, position=[123]))
        self.assertEqual(result.values, {"position": [123.0]})
        self.assertEqual(result.units, {"position": None})
        self.assertIn("telescopic_feedback_unit_unconfirmed", result.pending)

    def test_arrive_keeps_integer_raw_scale(self):
        result = parse_feedback("ArriveNotification", SAMPLES["ArriveNotification"])
        self.assertEqual(result.values, {"angle": 12345, "pos_error": -5, "status_bits": 4, "flags": 3})
        self.assertIs(type(result.values["angle"]), int)
        self.assertEqual(result.units, {"angle": "0.01degree", "pos_error": "0.01degree"})

    def test_telescopic_arrive_does_not_guess_scale(self):
        result = parse_feedback(
            "ArriveNotification", payload(15, angle=100, pos_error=-1, status_bits=4, flags=3)
        )
        self.assertEqual(result.values["angle"], 100)
        self.assertEqual(result.units, {"angle": None, "pos_error": None})
        self.assertIn("telescopic_arrive_units_unconfirmed", result.pending)

    def test_vacuum_loss_keeps_pressure_identity_and_unconfirmed_units(self):
        result = parse_feedback("VacuumLoss", SAMPLES["VacuumLoss"])
        self.assertEqual(result.address.device_id, 32)
        self.assertEqual(result.values, {"pressure_raw": -1234, "loss_threshold": 250})
        self.assertEqual(result.units, {"pressure_raw": None, "loss_threshold": None})
        self.assertIn("vacuum_loss_units_unconfirmed", result.pending)

    def test_axis_events_do_not_manufacture_position_or_completion(self):
        expected = {
            "AxisStatus": {"status_bits": 257, "axis_state": 0, "base_valid": 1},
            "StopNotification": {"stop_reason": 1, "output_level": 0},
            "CmdAck": {"ack_msg": 0, "result": 0, "detail": 0},
            "AxisFault": {"fault_bits": 65, "local_action": 1, "detail": 2, "duration_ms": 300},
            "LimitEvent": {"limit_type": 2, "output_level": 0},
        }
        for name, values in expected.items():
            with self.subTest(name=name):
                result = parse_feedback(name, SAMPLES[name])
                self.assertEqual(result.values, values)
                self.assertNotIn("position", result.values)
                self.assertNotIn("completed", result.values)
                self.assertNotIn("request_id", result.values)
        self.assertIn("uncorrelated_ack", parse_feedback("CmdAck", SAMPLES["CmdAck"]).pending)

    def test_module_status_uses_explicit_status_and_retains_token(self):
        result = parse_feedback("ModuleStatus", SAMPLES["ModuleStatus"])
        self.assertEqual(result.values["module_state"], 0)
        self.assertEqual(result.binding.status, 1)
        self.assertEqual(result.binding.route_seg, 0)
        self.assertEqual(result.binding.bound_seg, 0)
        self.assertEqual(result.values["token"], 1234)
        self.assertIn("binding_freshness_unverified", result.pending)
        self.assertIn("binding_query_correlation_unverified", result.pending)

    def test_unbound_module_does_not_use_firmware_bits_as_binding_status(self):
        source = deepcopy(SAMPLES["ModuleStatus"])
        source.update(module_id=5, seg=0, status=0, module_state=255)
        result = parse_feedback("ModuleStatus", source)
        self.assertEqual(result.binding.status, 0)
        self.assertEqual((result.binding.route_seg, result.binding.bound_seg), (5, 0))

    def test_module_routing_seg_and_bound_seg_are_not_merged(self):
        source = deepcopy(SAMPLES["ModuleStatus"])
        source["seg"] = 4
        result = parse_feedback("ModuleStatus", source)
        self.assertEqual(result.address.module_id, 0)
        self.assertEqual(result.values["seg"], 4)
        self.assertEqual((result.binding.route_seg, result.binding.bound_seg), (0, 4))
        self.assertIn("binding_route_mismatch", result.pending)

    def test_raw_payload_is_an_independent_snapshot(self):
        source = deepcopy(SAMPLES["SensorCmd"])
        source["future_field"] = {"values": [123]}
        result = parse_feedback("SensorCmd", source)
        source["position"][0] = 99
        source["header"]["stamp"]["sec"] = 0
        source["future_field"]["values"].append(456)
        self.assertEqual(result.raw["position"], [0.0])
        self.assertEqual(result.header, HEADER)
        self.assertEqual(result.raw["future_field"], {"values": [123]})
        self.assertNotIn("future_field", result.values)
        result.raw["position"][0] = 10
        self.assertEqual(result.values["position"], [0.0])


class Ros2FeedbackValidationTest(unittest.TestCase):
    def test_every_documented_field_is_required(self):
        for name, original in SAMPLES.items():
            for field in original:
                with self.subTest(message=name, missing=field):
                    source = deepcopy(original)
                    del source[field]
                    with self.assertRaises(ContractError):
                        parse_feedback(name, source)

    def test_old_sensor_ids_and_cross_segment_payloads_are_rejected(self):
        cases = (("SensorCmd", 21), ("SensorCmd", 36), ("VacuumLoss", 22), ("TuoLuoYi", 21), ("TuoLuoYi", 31), ("GyroFeedback", 35), ("Feedback", 31), ("CmdAck", 0), ("ModuleStatus", 1))
        for name, device_id in cases:
            with self.subTest(message=name, device_id=device_id):
                source = deepcopy(SAMPLES[name])
                source["device_id"] = device_id
                with self.assertRaises(ContractError):
                    parse_feedback(name, source)

    def test_module_and_device_ids_are_strict_integers(self):
        for field in ("module_id", "device_id"):
            for value in (True, False, 0.0, "0", None):
                with self.subTest(field=field, value=value):
                    source = deepcopy(SAMPLES["SensorCmd"])
                    source[field] = value
                    with self.assertRaises(ContractError):
                        parse_feedback("SensorCmd", source)

    def test_invalid_seg_never_falls_back_to_zero(self):
        for value in (-1, 15, 17, 255):
            with self.subTest(value=value):
                with self.assertRaises(ContractError):
                    parse_feedback("SensorCmd", payload(31, module_id=value, id=0, position=[0]))

    def test_position_requires_exactly_one_finite_number(self):
        for value in ([], [1, 2], 0, (0,), [None], [True], ["0"], [float("nan")], [float("inf")]):
            with self.subTest(value=value):
                with self.assertRaises(ContractError):
                    parse_feedback("SensorCmd", payload(31, id=0, position=value))

    def test_integer_fields_reject_coercion_and_out_of_range_values(self):
        cases = (
            ("SensorCmd", "id", 256),
            ("AxisStatus", "status_bits", 512),
            ("AxisStatus", "axis_state", 4),
            ("AxisStatus", "base_valid", True),
            ("ArriveNotification", "angle", 2**31),
            ("ArriveNotification", "pos_error", -(2**15) - 1),
            ("ArriveNotification", "status_bits", 256),
            ("ArriveNotification", "flags", -1),
            ("StopNotification", "stop_reason", 0),
            ("StopNotification", "output_level", 256),
            ("CmdAck", "ack_msg", 16),
            ("CmdAck", "result", 6),
            ("CmdAck", "detail", "0"),
            ("AxisFault", "fault_bits", 65536),
            ("AxisFault", "local_action", 0),
            ("AxisFault", "duration_ms", -1),
            ("LimitEvent", "limit_type", 3),
            ("VacuumLoss", "pressure_raw", -(2**31) - 1),
            ("VacuumLoss", "loss_threshold", 65536),
        )
        for name, field, value in cases:
            with self.subTest(message=name, field=field, value=value):
                source = deepcopy(SAMPLES[name])
                source[field] = value
                with self.assertRaises(ContractError):
                    parse_feedback(name, source)

    def test_imu_measurements_reject_nonfinite_boolean_and_float32_overflow(self):
        for name, field, value in (
            ("TuoLuoYi", "rotation_angle", float("nan")),
            ("TuoLuoYi", "x", True),
            ("GyroFeedback", "gyro_x", float("-inf")),
            ("GyroFeedback", "accel_x", 3.5e38),
        ):
            with self.subTest(message=name, field=field):
                source = deepcopy(SAMPLES[name])
                source[field] = value
                with self.assertRaises(ContractError):
                    parse_feedback(name, source)

    def test_module_status_fields_and_cross_field_rules_are_checked(self):
        cases = (
            {"seg": 255},
            {"status": 2},
            {"status": False},
            {"status": 0, "seg": 1},
            {"arm_slot": 0},
            {"axis_base": 5},
            {"arm_slot": 2, "axis_base": 7},
            {"exist_mask": 8},
            {"ready_mask": 8},
            {"module_state": 256},
            {"token": 65536},
        )
        for fields in cases:
            with self.subTest(fields=fields):
                source = deepcopy(SAMPLES["ModuleStatus"])
                source.update(fields)
                with self.assertRaises(ContractError):
                    parse_feedback("ModuleStatus", source)

    def test_known_messages_require_ros2_header(self):
        cases = (
            None,
            {},
            {"stamp": {"secs": 1, "nsecs": 0}, "frame_id": "module_0"},
            {"stamp": {"sec": 1, "nanosec": 10**9}, "frame_id": "module_0"},
            {"stamp": {"sec": True, "nanosec": 0}, "frame_id": "module_0"},
        )
        for header in cases:
            with self.subTest(header=header):
                source = deepcopy(SAMPLES["SensorCmd"])
                source["header"] = header
                with self.assertRaises(ContractError):
                    parse_feedback("SensorCmd", source)

    def test_topic_to_type_consistency_is_explicit(self):
        confirmed = {"/confirmed/pressure": "SensorCmd"}
        result = parse_feedback(
            "SensorCmd", SAMPLES["SensorCmd"], topic="/confirmed/pressure", topic_message_types=confirmed
        )
        self.assertTrue(result.is_known)
        for name, topic in (("SensorCmd", None), ("SensorCmd", "/other"), ("TuoLuoYi", "/confirmed/pressure")):
            with self.subTest(message=name, topic=topic):
                with self.assertRaises(ContractError):
                    parse_feedback(name, SAMPLES[name], topic=topic, topic_message_types=confirmed)

    def test_unknown_messages_have_no_trusted_identity_or_values(self):
        for name in ("Heartbeat", "HomeStatus", "Kinematics", "UidAnnounce", "RotationCmd", "robot_control_backend/msg/SensorCmd", "FutureFeedback"):
            with self.subTest(message=name):
                source = {"module_id": 17, "device_id": 21, "position": [99]}
                result = parse_feedback(name, source)
                self.assertFalse(result.is_known)
                self.assertIsNone(result.address)
                self.assertIsNone(result.header)
                self.assertEqual(result.values, {})
                self.assertEqual(result.units, {})
                self.assertEqual(result.pending, ("unknown_message",))
                self.assertEqual(result.raw, source)
                source["position"][0] = 0
                self.assertEqual(result.raw["position"], [99])

    def test_bad_container_or_message_name_is_rejected(self):
        for source in (None, [], "payload", 0):
            with self.subTest(source=source):
                with self.assertRaises(ContractError):
                    parse_feedback("SensorCmd", source)
        for name in (None, "", 1):
            with self.subTest(name=name):
                with self.assertRaises(ContractError):
                    parse_feedback(name, {})


if __name__ == "__main__":
    unittest.main()
