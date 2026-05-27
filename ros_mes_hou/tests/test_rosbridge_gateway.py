import unittest

from app.services.rosbridge_gateway import normalize_feedback_message


class RosbridgeGatewayTest(unittest.TestCase):
    def test_normalize_axis_feedback_keeps_frontend_feedback_shape(self):
        feedback = normalize_feedback_message(
            "/hardware/rotation_feedback",
            {
                "header": {"stamp": {"secs": 1, "nsecs": 2}},
                "module_id": 17,
                "device_id": 33,
                "position": 45.5,
            },
        )

        self.assertEqual(feedback["topic"], "/hardware/rotation_feedback")
        self.assertEqual(feedback["module_id"], 17)
        self.assertEqual(feedback["device_id"], 33)
        self.assertEqual(feedback["position"], 45.5)
        self.assertEqual(feedback["data_type"], "axis_encoder")
        self.assertEqual(feedback["feedback_type"], "旋转轴编码器")

    def test_normalize_axis_feedback_uses_feedback_device_ids(self):
        cases = [
            ("/hardware/rotation_feedback", 41, "rotation_axis_encoder", "旋转轴编码器"),
            ("/hardware/swing_feedback", 42, "swing_axis_encoder", "摆动轴编码器"),
            ("/hardware/telescope_feedback", 43, "telescope_axis_encoder", "伸缩轴编码器"),
        ]

        for topic, device_id, data_type, feedback_type in cases:
            with self.subTest(device_id=device_id):
                feedback = normalize_feedback_message(
                    topic,
                    {
                        "module_id": 17,
                        "device_id": device_id,
                        "position": [6.5],
                    },
                )

                self.assertEqual(feedback["device_id"], device_id)
                self.assertEqual(feedback["position"], 6.5)
                self.assertEqual(feedback["data_type"], data_type)
                self.assertEqual(feedback["feedback_type"], feedback_type)

    def test_normalize_pressure_feedback_keeps_frontend_feedback_shape(self):
        feedback = normalize_feedback_message(
            "/hardware/sensor_feedback",
            {
                "module_id": 17,
                "device_id": 49,
                "position": 12.75,
            },
        )

        self.assertEqual(feedback["device_id"], 49)
        self.assertEqual(feedback["position"], 12.75)
        self.assertEqual(feedback["data_type"], "pressure_sensor")
        self.assertEqual(feedback["feedback_type"], "压力传感器")

    def test_normalize_imu_pose_feedback_keeps_pose_fields(self):
        feedback = normalize_feedback_message(
            "/hardware/imu_angles",
            {
                "module_id": 17,
                "device_id": 50,
                "swing_angle": 12.5,
                "rotation_angle": -8.25,
                "x": 1.2,
                "y": 3.4,
                "z": 5.6,
            },
        )

        self.assertEqual(feedback["topic"], "/hardware/imu_angles")
        self.assertEqual(feedback["device_id"], 50)
        self.assertEqual(feedback["data_type"], "imu_pose")
        self.assertEqual(feedback["feedback_type"], "陀螺仪姿态")
        self.assertEqual(feedback["swing_angle"], 12.5)
        self.assertEqual(feedback["rotation_angle"], -8.25)
        self.assertEqual(feedback["x"], 1.2)
        self.assertEqual(feedback["y"], 3.4)
        self.assertEqual(feedback["z"], 5.6)


if __name__ == "__main__":
    unittest.main()
