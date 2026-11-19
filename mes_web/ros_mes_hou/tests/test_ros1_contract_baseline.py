"""Fixed legacy messages that the independent ROS2 contract must not alter."""

from dataclasses import replace
import unittest
from unittest.mock import patch

from app.ros.normalizer import normalize_feedback_message
from app.ros.profile import ROS1_PROFILE
from app.ros.rosbridge import (
    build_axis_zero_publish_payload,
    build_fine_tuning_publish_payload,
    build_module_confirm_publish_payload,
)


class Ros1ContractBaselineTest(unittest.TestCase):
    def setUp(self):
        # Topic overrides are deployment inputs; keep these samples independent
        # of the workstation's ROS_TOPIC_* environment variables.
        self.profile = replace(ROS1_PROFILE, topics={
            **ROS1_PROFILE.topics,
            "fine_tuning_rotation": "/control/adjust_rotation_cmd",
            "fine_tuning_swing": "/control/adjust_swing_cmd",
            "fine_tuning_telescopic": "/control/adjust_telescopic_cmd",
            "module_cmd": "/control/module_cmd",
            "axis_zero": "/control/axis_zero",
            "feedback_sensor": "/hardware/sensor_feedback",
            "feedback_imu": "/hardware/imu_angles",
            "feedback_cmd_ack": "/hardware/cmd_ack",
        })

    def test_three_axis_messages_keep_business_module_and_ros1_header(self):
        samples = (
            ("rotation", 4, 1.5, "/control/adjust_rotation_cmd", "RotationCmd"),
            ("swing", 5, -2.0, "/control/adjust_swing_cmd", "SwingCmd"),
            ("telescopic", 6, 0.75, "/control/adjust_telescopic_cmd", "TelescopicCmd"),
        )
        with patch("app.ros.rosbridge.time.time", return_value=1700000000.25):
            for parameter, axis, increment, topic, message_name in samples:
                with self.subTest(parameter=parameter):
                    actual = build_fine_tuning_publish_payload(
                        parameter, increment, 17, axis, profile=self.profile,
                    )
                    self.assertEqual(actual, {
                        "topic": topic,
                        "message_type": "robot_control_backend/" + message_name,
                        "message": {
                            "header": {
                                "stamp": {"secs": 1700000000, "nsecs": 250000000},
                                "frame_id": "",
                            },
                            "module_id": 17,
                            "device_id": axis,
                            "position": [increment],
                        },
                        "parameter_name": parameter,
                    })

    def test_module_confirmation_keeps_business_number_and_explicit_binding(self):
        with patch("app.ros.rosbridge.time.time", return_value=1700000000.25):
            actual = build_module_confirm_publish_payload(
                17, seg=0, arm=2, profile=self.profile,
            )
        self.assertEqual(actual, {
            "topic": "/control/module_cmd",
            "message_type": "robot_control_backend/IntCmd",
            "message": {
                "header": {
                    "stamp": {"secs": 1700000000, "nsecs": 250000000},
                    "frame_id": "",
                },
                "module_id": 17,
                "device_id": 0,
                "position": [100, 0, 2],
            },
        })

    def test_axis_zero_keeps_legacy_arm_payload(self):
        with patch("app.ros.rosbridge.time.time", return_value=1700000000.25):
            actual = build_axis_zero_publish_payload(17, 64, profile=self.profile)
        self.assertEqual(actual, {
            "topic": "/control/axis_zero",
            "message_type": "robot_control_backend/IntCmd",
            "message": {
                "header": {
                    "stamp": {"secs": 1700000000, "nsecs": 250000000},
                    "frame_id": "",
                },
                "module_id": 17,
                "device_id": 0,
                "position": [2],
            },
            "arm": 2,
        })

    def test_legacy_pressure_22_remains_valid_including_zero(self):
        message = {
            "header": {"stamp": {"secs": 123, "nsecs": 0}, "frame_id": ""},
            "module_id": 0, "device_id": 22, "id": 3, "position": [0.0],
        }
        with patch("app.ros.normalizer.time.time", return_value=1700000000.25):
            actual = normalize_feedback_message(
                "/hardware/sensor_feedback", message, self.profile.topics,
            )
        self.assertEqual(actual, {
            "time_id": 1700000000.25,
            "topic": "/hardware/sensor_feedback",
            "header": {"secs": 123, "nsecs": 0},
            "module_id": 0,
            "module_id_space": "seg",
            "device_id": 22,
            "position": 0.0,
            "position_valid": True,
            "valid_fields": ["position"],
            "data_type": "pressure_sensor",
            "feedback_type": "臂2压力传感器",
            "raw": message,
            "id": 3,
        })

    def test_legacy_imu_22_is_distinguished_by_topic(self):
        message = {
            "header": {"stamp": {"secs": 123, "nsecs": 0}, "frame_id": ""},
            "module_id": 0, "device_id": 22,
            "swing_angle": 0.0, "rotation_angle": 12.5,
            "x": 1.0, "y": 2.0, "z": 3.0,
        }
        with patch("app.ros.normalizer.time.time", return_value=1700000000.25):
            actual = normalize_feedback_message(
                "/hardware/imu_angles", message, self.profile.topics,
            )
        self.assertEqual(actual, {
            "time_id": 1700000000.25,
            "topic": "/hardware/imu_angles",
            "header": {"secs": 123, "nsecs": 0},
            "module_id": 0,
            "module_id_space": "seg",
            "device_id": 22,
            "position": None,
            "position_valid": False,
            "valid_fields": ["swing_angle", "rotation_angle", "x", "y", "z"],
            "data_type": "imu_pose",
            "feedback_type": "臂2陀螺仪姿态",
            "raw": message,
            "swing_angle": 0.0,
            "rotation_angle": 12.5,
            "x": 1.0, "y": 2.0, "z": 3.0,
        })

    def test_legacy_ack_preserves_mixed_namespace_and_raw_result(self):
        message = {
            "module_id": 0, "device_id": 4,
            "ack_msg": 1, "result": 0, "detail": 0,
        }
        with patch("app.ros.normalizer.time.time", return_value=1700000000.25), \
                patch("app.ros.normalizer.settings.ROS_MODULE_SEG_MAP", '{"17":0}'):
            actual = normalize_feedback_message(
                "/hardware/cmd_ack", message, self.profile.topics,
            )
        self.assertEqual(actual, {
            "time_id": 1700000000.25,
            "topic": "/hardware/cmd_ack",
            "header": {},
            "module_id": 0,
            "module_id_space": "mixed",
            "device_id": 4,
            "position": None,
            "position_valid": False,
            "valid_fields": [],
            "data_type": "cmd_ack",
            "feedback_type": "指令回执",
            "raw": message,
            "ack_msg": 1, "result": 0, "detail": 0,
            "module_candidates": [17],
            "module_resolution": "resolved",
            "business_module_id": 17,
        })


if __name__ == "__main__":
    unittest.main()
