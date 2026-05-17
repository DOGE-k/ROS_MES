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


if __name__ == "__main__":
    unittest.main()
