"""Offline checks against fixed addressing rules from the supplied msg design."""
import unittest
from dataclasses import FrozenInstanceError

from app.ros2_contract.addressing import (
    Address,
    AxisKind,
    EntityKind,
    arm_of,
    axis_kind,
    device_id_for,
    entity_kind,
    validate_arm,
    validate_device,
    validate_seg,
)
from app.ros2_contract.validation import (
    ContractError,
    PendingContractError,
    require_header,
    require_int,
    require_number,
    require_object,
)


class AddressingContractTest(unittest.TestCase):
    def test_seg_zero_and_fourteen_are_physical_modules(self):
        self.assertEqual(validate_seg(0), 0)
        self.assertEqual(validate_seg(14), 14)

    def test_seg_does_not_coerce_business_or_malformed_ids(self):
        for value in (None, -1, 15, 17, True, False, 0.0, "0", [], {}):
            with self.subTest(value=value), self.assertRaises(ContractError):
                validate_seg(value)

    def test_arm_slots_do_not_decode_legacy_unit_ids(self):
        self.assertEqual(validate_arm(1), 1)
        self.assertEqual(validate_arm(5), 5)
        for value in (0, 6, 32, 64, 160, None, True, 1.0, "1"):
            with self.subTest(value=value), self.assertRaises(ContractError):
                validate_arm(value)

    def test_entity_categories_use_separate_segments(self):
        cases = (
            (0, EntityKind.SYSTEM),
            (1, EntityKind.AXIS),
            (15, EntityKind.AXIS),
            (21, EntityKind.ARM),
            (25, EntityKind.ARM),
            (31, EntityKind.PRESSURE),
            (35, EntityKind.PRESSURE),
            (36, EntityKind.IMU),
            (40, EntityKind.IMU),
        )
        for device_id, expected in cases:
            with self.subTest(device_id=device_id):
                self.assertIs(entity_kind(device_id), expected)

    def test_reserved_ids_are_not_entities(self):
        for value in (*range(16, 21), *range(26, 31), -1, 41, 49, True, None, "31", 31.0):
            with self.subTest(value=value), self.assertRaises(ContractError):
                entity_kind(value)

    def test_system_entity_has_no_arm(self):
        self.assertIsNone(arm_of(0))

    def test_second_and_fifth_arm_have_fixed_entity_ids(self):
        for device_id, expected in (
            (4, 2), (5, 2), (6, 2), (22, 2), (32, 2), (37, 2),
            (13, 5), (14, 5), (15, 5), (25, 5), (35, 5), (40, 5),
        ):
            with self.subTest(device_id=device_id):
                self.assertEqual(arm_of(device_id), expected)

    def test_invalid_arm_lookup_raises_instead_of_guessing(self):
        for value in (16, 20, 26, 30, None, True):
            with self.subTest(value=value), self.assertRaises(ContractError):
                arm_of(value)

    def test_joint_categories_match_the_documented_five_arm_layout(self):
        for expected, device_ids in (
            (AxisKind.ROTATION, (1, 4, 7, 10, 13)),
            (AxisKind.SWING, (2, 5, 8, 11, 14)),
            (AxisKind.TELESCOPIC, (3, 6, 9, 12, 15)),
        ):
            for device_id in device_ids:
                with self.subTest(device_id=device_id):
                    self.assertIs(axis_kind(device_id), expected)

    def test_non_axis_entity_cannot_be_a_joint(self):
        for device_id in (0, 21, 25, 31, 35, 36, 40):
            with self.subTest(device_id=device_id), self.assertRaises(ContractError):
                axis_kind(device_id)

    def test_kind_validation_rejects_old_sensor_ids_and_cross_segment_ids(self):
        for device_id, kind in ((21, EntityKind.PRESSURE), (25, EntityKind.IMU), (31, EntityKind.IMU), (36, EntityKind.PRESSURE)):
            with self.subTest(device_id=device_id, kind=kind), self.assertRaises(ContractError):
                validate_device(device_id, kind)
        self.assertEqual(validate_device(32, EntityKind.PRESSURE), 32)
        self.assertEqual(validate_device(37, EntityKind.IMU), 37)

    def test_second_arm_ids_are_built_without_database_or_bus_mapping(self):
        cases = (
            (EntityKind.AXIS, AxisKind.ROTATION, 4),
            (EntityKind.AXIS, AxisKind.SWING, 5),
            (EntityKind.AXIS, AxisKind.TELESCOPIC, 6),
            (EntityKind.ARM, None, 22),
            (EntityKind.PRESSURE, None, 32),
            (EntityKind.IMU, None, 37),
        )
        for kind, axis, expected in cases:
            with self.subTest(kind=kind, axis=axis):
                self.assertEqual(device_id_for(2, kind, axis), expected)

    def test_device_construction_requires_explicit_compatible_categories(self):
        for args in (
            (2, EntityKind.SYSTEM),
            (2, EntityKind.AXIS),
            (2, EntityKind.AXIS, "rotation"),
            (2, EntityKind.PRESSURE, AxisKind.ROTATION),
            (2, "pressure"),
        ):
            with self.subTest(args=args), self.assertRaises(ContractError):
                device_id_for(*args)
        with self.assertRaises(ContractError):
            validate_device(31, "pressure")

    def test_entity_identity_includes_the_module(self):
        identities = {Address(0, 32), Address(14, 32)}
        self.assertEqual(len(identities), 2)
        self.assertEqual(Address(0, 32), Address(0, 32))

    def test_address_is_immutable_and_validated_on_construction(self):
        with self.assertRaises(FrozenInstanceError):
            Address(0, 32).module_id = 1
        for module_id, device_id in ((17, 32), (None, 32), (0, 16), (0, True)):
            with self.subTest(module_id=module_id, device_id=device_id), self.assertRaises(ContractError):
                Address(module_id, device_id)


class ValueValidationTest(unittest.TestCase):
    def test_pending_definition_is_a_contract_error(self):
        self.assertTrue(issubclass(PendingContractError, ContractError))

    def test_integers_keep_exact_boundaries_and_reject_coercion(self):
        self.assertEqual(require_int(-32768, "error", -32768, 32767), -32768)
        self.assertEqual(require_int(32767, "error", -32768, 32767), 32767)
        for value in (-32769, 32768, True, 3.0, "3", None):
            with self.subTest(value=value), self.assertRaises(ContractError):
                require_int(value, "error", -32768, 32767)

    def test_valid_zero_is_preserved_and_numeric_values_are_finite(self):
        self.assertEqual(require_number(0, "position"), 0.0)
        self.assertEqual(require_number(-1.25, "position"), -1.25)
        for value in (True, False, "0", None, float("nan"), float("inf"), float("-inf"), 10**1000):
            with self.subTest(value=type(value).__name__), self.assertRaises(ContractError):
                require_number(value, "position")

    def test_objects_are_not_coerced_from_other_shapes(self):
        source = {"position": [0]}
        self.assertIs(require_object(source, "message"), source)
        for value in (None, [], "{}", 0, True):
            with self.subTest(value=value), self.assertRaises(ContractError):
                require_object(value, "message")

    def test_header_is_detached_and_has_only_ros2_standard_fields(self):
        source = {"stamp": {"sec": 0, "nanosec": 999999999, "extra": []}, "frame_id": "module_0", "extra": {}}
        header = require_header(source)
        self.assertEqual(header, {"stamp": {"sec": 0, "nanosec": 999999999}, "frame_id": "module_0"})
        header["stamp"]["sec"] = 5
        self.assertEqual(source["stamp"]["sec"], 0)

    def test_header_accepts_ros2_sec_int32_boundaries(self):
        for sec in (-(2**31), 2**31 - 1):
            with self.subTest(sec=sec):
                self.assertEqual(require_header({"stamp": {"sec": sec, "nanosec": 0}, "frame_id": ""})["stamp"]["sec"], sec)

    def test_header_does_not_invent_timestamp_or_frame(self):
        values = (
            None, {}, {"stamp": {}}, {"stamp": {"sec": 0, "nanosec": 0}},
            {"stamp": {"secs": 0, "nsecs": 0}, "frame_id": "module_0"},
            {"stamp": {"sec": 0, "nanosec": -1}, "frame_id": ""},
            {"stamp": {"sec": 0, "nanosec": 1000000000}, "frame_id": ""},
            {"stamp": {"sec": 2**31, "nanosec": 0}, "frame_id": ""},
            {"stamp": {"sec": -(2**31) - 1, "nanosec": 0}, "frame_id": ""},
            {"stamp": {"sec": True, "nanosec": 0}, "frame_id": ""},
            {"stamp": {"sec": 0, "nanosec": 0.0}, "frame_id": ""},
            {"stamp": {"sec": 0, "nanosec": 0}, "frame_id": False},
        )
        for header in values:
            with self.subTest(header=header), self.assertRaises(ContractError):
                require_header(header)


if __name__ == "__main__":
    unittest.main()
