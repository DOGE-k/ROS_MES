"""Offline, literal examples from the proposed message rules."""
import copy
import unittest

from app.ros2_contract.addressing import AxisKind
from app.ros2_contract.commands import build_axis_zero_message, build_fine_tuning_message
from app.ros2_contract.models import BindingState
from app.ros2_contract.validation import ContractError, PendingContractError


HEADER = {"stamp": {"sec": 123, "nanosec": 456}, "frame_id": "module_0"}


class CommandContractTest(unittest.TestCase):
    def setUp(self):
        self.binding = BindingState(0, 0, 1, 2, 4)

    def test_rotation_literal_message_accepts_seg_zero(self):
        result = build_fine_tuning_message("rotation", -1.5, 0, 4, header=HEADER, binding=self.binding)
        self.assertEqual(result.message_name, "RotationCmd")
        self.assertEqual(result.message, {
            "header": {"stamp": {"sec": 123, "nanosec": 456}, "frame_id": "module_0"},
            "module_id": 0, "device_id": 4, "position": [-1.5],
        })
        self.assertEqual(list(result.message), ["header", "module_id", "device_id", "position"])
        self.assertIn("runtime_checks_not_performed", result.pending)
        self.assertNotIn("op", result.to_dict())
        self.assertNotIn("topic", result.to_dict())

    def test_all_three_axis_messages_preserve_signed_increment(self):
        for kind, device, name in ((AxisKind.ROTATION, 4, "RotationCmd"),
                                   (AxisKind.SWING, 5, "SwingCmd"),
                                   (AxisKind.TELESCOPIC, 6, "TelescopicCmd")):
            with self.subTest(kind=kind):
                result = build_fine_tuning_message(kind, -2, 0, device, header=HEADER, binding=self.binding)
                self.assertEqual((result.message_name, result.message["position"]), (name, [-2.0]))
                self.assertIn("absolute_limits_not_checked", result.pending)

    def test_fifth_arm_and_last_seg_have_literal_axis_and_arm_ids(self):
        binding = BindingState(14, 14, 1, 5, 13)
        header = {"stamp": {"sec": 0, "nanosec": 0}, "frame_id": "module_14"}
        result = build_fine_tuning_message("rotation", 0, 14, 13, header=header, binding=binding)
        self.assertEqual((result.message["module_id"], result.message["device_id"]), (14, 13))
        self.assertEqual(result.message["position"], [0.0])
        zero = build_axis_zero_message(14, 5, header=header, binding=binding)
        self.assertEqual((zero.message["device_id"], zero.message["position"]), (25, [25]))

    def test_axis_zero_uses_new_arm_entity_in_both_fields(self):
        result = build_axis_zero_message(0, 2, header=HEADER, binding=self.binding)
        self.assertEqual(result.message_name, "IntCmd")
        self.assertEqual(result.message, {
            "header": {"stamp": {"sec": 123, "nanosec": 456}, "frame_id": "module_0"},
            "module_id": 0, "device_id": 22, "position": [22],
        })
        self.assertIn("reset_confirmation_not_defined", result.pending)

    def test_unknown_binding_does_not_default_to_seg_zero(self):
        with self.assertRaises(PendingContractError):
            build_fine_tuning_message("rotation", 1, 0, 4, header=HEADER)
        with self.assertRaises(PendingContractError):
            build_axis_zero_message(0, 2, header=HEADER)

    def test_unbound_or_wrong_route_bound_seg_or_arm_is_rejected(self):
        for binding in (BindingState(0, 0, 0, 2, 4), BindingState(1, 0, 1, 2, 4),
                        BindingState(0, 1, 1, 2, 4), BindingState(0, 0, 1, 1, 1)):
            with self.subTest(binding=binding), self.assertRaises(ContractError):
                build_fine_tuning_message("rotation", 1, 0, 4, header=HEADER, binding=binding)
            with self.subTest(reset_binding=binding), self.assertRaises(ContractError):
                build_axis_zero_message(0, 2, header=HEADER, binding=binding)

    def test_wrong_axis_kind_reserved_old_arm_and_sensor_ids_are_rejected(self):
        for device in (5, 6, 16, 22, 32, 37, True, 4.0, "4"):
            with self.subTest(device=device), self.assertRaises(ContractError):
                build_fine_tuning_message("rotation", 1, 0, device, header=HEADER, binding=self.binding)

    def test_bad_seg_parameter_and_nonfinite_increment_are_rejected(self):
        for seg in (15, 17, -1, True, 0.0, "0", None):
            with self.subTest(seg=seg), self.assertRaises(ContractError):
                build_fine_tuning_message("rotation", 1, seg, 4, header=HEADER, binding=self.binding)
        for value in (True, "1", None, float("nan"), float("inf"), 10**400):
            with self.subTest(value_type=type(value).__name__), self.assertRaises(ContractError):
                build_fine_tuning_message("rotation", value, 0, 4, header=HEADER, binding=self.binding)
        for parameter in ("unknown", "RotationCmd", 1, None):
            with self.subTest(parameter=parameter), self.assertRaises(ContractError):
                build_fine_tuning_message(parameter, 1, 0, 4, header=HEADER, binding=self.binding)

    def test_rotation_frame_and_ros2_header_are_required(self):
        for header in ({"stamp": {"sec": 0, "nanosec": 0}, "frame_id": ""},
                       {"stamp": {"secs": 0, "nsecs": 0}, "frame_id": "module_0"},
                       {"stamp": {"sec": 0, "nanosec": -1}, "frame_id": "module_0"}, None):
            with self.subTest(header=header), self.assertRaises(ContractError):
                build_fine_tuning_message("rotation", 1, 0, 4, header=header, binding=self.binding)

    def test_supplied_headers_and_exported_copies_do_not_alias(self):
        header = copy.deepcopy(HEADER)
        result = build_axis_zero_message(0, 2, header=header, binding=self.binding)
        header["stamp"]["sec"] = 999
        exported = result.to_dict()
        exported["message"]["position"][0] = 99
        self.assertEqual(result.message["header"]["stamp"]["sec"], 123)
        self.assertEqual(result.message["position"], [22])

    def test_binding_validation_preserves_distinct_seg_values(self):
        state = BindingState(0, 4, 1, 2, 4)
        self.assertEqual((state.route_seg, state.bound_seg), (0, 4))
        for values in ((0, 1, 0, 2, 4), (0, 0, True, 2, 4), (0, 0, 1, 2, 1),
                       (0, 0, 1, 0, 1), (0, 15, 1, 2, 4)):
            with self.subTest(values=values), self.assertRaises(ContractError):
                BindingState(*values)


if __name__ == "__main__":
    unittest.main()
