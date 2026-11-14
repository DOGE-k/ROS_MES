import os
import unittest
from unittest.mock import patch

from app.ros.profile import ROS1_PROFILE, ROS2_PROFILE
from app.ros.rosbridge import (
    build_axis_zero_publish_payload,
    build_drawing_path_publish_payload,
    build_fine_tuning_publish_payload,
    build_module_confirm_publish_payload,
)


class RosProfileDialectTest(unittest.TestCase):
    """ROS1/ROS2 协议差异契约：类型串格式与 header.stamp 字段名。"""

    def test_ros1_profile_uses_ros1_dialect(self):
        self.assertEqual(ROS1_PROFILE.message_type("IntCmd"), "robot_control_backend/IntCmd")
        self.assertEqual(ROS1_PROFILE.std_message_type("String"), "std_msgs/String")
        self.assertEqual(ROS1_PROFILE.stamp_fields, ("secs", "nsecs"))
        self.assertTrue(ROS1_PROFILE.native_node)

    def test_ros2_profile_uses_ros2_dialect(self):
        self.assertEqual(ROS2_PROFILE.message_type("IntCmd"), "robot_control_backend/msg/IntCmd")
        self.assertEqual(ROS2_PROFILE.std_message_type("String"), "std_msgs/msg/String")
        self.assertEqual(ROS2_PROFILE.stamp_fields, ("sec", "nanosec"))
        self.assertFalse(ROS2_PROFILE.native_node)

    def test_payload_builders_accept_explicit_ros2_profile(self):
        fine = build_fine_tuning_publish_payload("rotation", 1.5, 2, 5, profile=ROS2_PROFILE)
        self.assertEqual(fine["message_type"], "robot_control_backend/msg/RotationCmd")
        self.assertEqual(sorted(fine["message"]["header"]["stamp"]), ["nanosec", "sec"])

        module = build_module_confirm_publish_payload(5, seg=6, arm=2, profile=ROS2_PROFILE)
        self.assertEqual(module["message_type"], "robot_control_backend/msg/IntCmd")
        self.assertEqual(module["message"]["position"], [100, 6, 2])
        self.assertEqual(sorted(module["message"]["header"]["stamp"]), ["nanosec", "sec"])

        drawing = build_drawing_path_publish_payload("a/b.json", profile=ROS2_PROFILE)
        self.assertEqual(drawing["message_type"], "std_msgs/msg/String")

    def test_axis_zero_payload_maps_each_business_unit_to_one_arm(self):
        for unit_id, arm in ((1, 1), (5, 5), (32, 1), (64, 2), (96, 3), (128, 4), (160, 5)):
            with self.subTest(unit_id=unit_id):
                payload = build_axis_zero_publish_payload(17, unit_id, profile=ROS1_PROFILE)
                self.assertEqual(payload["topic"], "/control/axis_zero")
                self.assertEqual(payload["message_type"], "robot_control_backend/IntCmd")
                self.assertEqual(payload["message"]["module_id"], 17)
                self.assertEqual(payload["message"]["device_id"], 0)
                self.assertEqual(payload["message"]["position"], [arm])
                self.assertEqual(payload["arm"], arm)

    def test_fine_tuning_payload_rejects_out_of_range_axis(self):
        # V2.1 三轴布局：轴号 1~15，16 起非法（四轴残留 17~20 一并拒绝）
        with self.assertRaises(Exception):
            build_fine_tuning_publish_payload("rotation", 1.0, 2, 16)

    def test_default_builders_keep_ros1_contract(self):
        with patch.dict(os.environ, {"ROS_VERSION": "1"}):
            module = build_module_confirm_publish_payload(5, seg=6, arm=2)
            self.assertEqual(module["message_type"], "robot_control_backend/IntCmd")
            self.assertEqual(sorted(module["message"]["header"]["stamp"]), ["nsecs", "secs"])


if __name__ == "__main__":
    unittest.main()
