import unittest

from app.ros.normalizer import normalize_feedback_message


class RosbridgeGatewayTest(unittest.TestCase):
    def test_normalize_axis_feedback_keeps_frontend_feedback_shape(self):
        feedback = normalize_feedback_message(
            "/hardware/rotation_feedback",
            {
                "header": {"stamp": {"secs": 1, "nsecs": 2}},
                "module_id": 17,
                "device_id": 1,
                "position": 45.5,
            },
        )

        self.assertEqual(feedback["topic"], "/hardware/rotation_feedback")
        self.assertEqual(feedback["module_id"], 17)
        self.assertEqual(feedback["device_id"], 1)
        self.assertEqual(feedback["position"], 45.5)
        self.assertEqual(feedback["data_type"], "rotation_axis_encoder")
        self.assertEqual(feedback["feedback_type"], "臂1旋转轴编码器")

    def test_normalize_axis_feedback_uses_feedback_device_ids(self):
        # V2.1 三轴 3 轴 ID 布局：每臂 关节1=旋转 / 关节2=摆动 / 关节3=伸缩
        cases = [
            ("/hardware/rotation_feedback", 1, "rotation_axis_encoder", "臂1旋转轴编码器"),
            ("/hardware/swing_feedback", 5, "swing_axis_encoder", "臂2摆动轴编码器"),
            ("/hardware/telescope_feedback", 9, "telescope_axis_encoder", "臂3伸缩轴编码器"),
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
                "device_id": 21,
                "position": 12.75,
            },
        )

        self.assertEqual(feedback["device_id"], 21)
        self.assertEqual(feedback["position"], 12.75)
        self.assertEqual(feedback["data_type"], "pressure_sensor")
        self.assertEqual(feedback["feedback_type"], "臂1压力传感器")

    def test_normalize_imu_pose_feedback_keeps_pose_fields(self):
        feedback = normalize_feedback_message(
            "/hardware/imu_angles",
            {
                "module_id": 17,
                "device_id": 21,
                "swing_angle": 12.5,
                "rotation_angle": -8.25,
                "x": 1.2,
                "y": 3.4,
                "z": 5.6,
            },
        )

        self.assertEqual(feedback["topic"], "/hardware/imu_angles")
        self.assertEqual(feedback["device_id"], 21)
        self.assertEqual(feedback["data_type"], "imu_pose")
        self.assertEqual(feedback["feedback_type"], "臂1陀螺仪姿态")
        self.assertEqual(feedback["swing_angle"], 12.5)
        self.assertEqual(feedback["rotation_angle"], -8.25)
        self.assertEqual(feedback["x"], 1.2)
        self.assertEqual(feedback["y"], 3.4)
        self.assertEqual(feedback["z"], 5.6)

    def test_normalize_imu_topic_with_axis_device_id_is_not_a_measurement(self):
        # IMU 话题上的轴号不能被误当伸缩轴实测值。
        feedback = normalize_feedback_message(
            "/hardware/imu_angles",
            {"module_id": 17, "device_id": 9},
        )

        self.assertEqual(feedback["data_type"], "unknown")
        self.assertFalse(feedback["position_valid"])
        self.assertIsNone(feedback["position"])

    def test_normalize_pressure_average_topic_branches_before_label_table(self):
        # V2 新增：/hardware/pressure_avg 独立平均值话题（不再与瞬时值混流）
        feedback = normalize_feedback_message(
            "/hardware/pressure_avg",
            {"module_id": 17, "device_id": 22, "position": [12.5]},
        )

        self.assertEqual(feedback["data_type"], "pressure_average")
        self.assertEqual(feedback["feedback_type"], "臂2压力平均值(5s窗口)")

    def test_normalize_vacuum_loss_topic_branches_before_label_table(self):
        # V2 新增：/hardware/vacuum_loss 失压事件话题
        feedback = normalize_feedback_message(
            "/hardware/vacuum_loss",
            {"module_id": 17, "device_id": 23, "position": [1]},
        )

        self.assertEqual(feedback["data_type"], "vacuum_loss_event")
        self.assertEqual(feedback["feedback_type"], "臂3吸盘失压告警")

    def test_normalize_cmd_ack_branches_before_label_table(self):
        # V2.1：/hardware/cmd_ack 指令回执（超位拒绝），透传 result/detail
        feedback = normalize_feedback_message(
            "/hardware/cmd_ack",
            {"module_id": 3, "device_id": 9, "ack_msg": 1, "result": 3, "detail": 1},
        )

        self.assertEqual(feedback["data_type"], "cmd_ack")
        self.assertEqual(feedback["feedback_type"], "指令回执")
        self.assertEqual(feedback["result"], 3)
        self.assertEqual(feedback["detail"], 1)


if __name__ == "__main__":
    unittest.main()
