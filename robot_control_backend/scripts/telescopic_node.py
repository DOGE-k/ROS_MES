#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from robot_control_backend.msg import CmdAck, IntCmd, TelescopicCmd
from robot_control_runtime.params import declare_env_parameter, load_environment
from robot_control_runtime.telemetry import SensorLog


class TelescopeSimple(Node):
    TELESCOPIC_AXES = {3: 0, 6: 1, 9: 2, 12: 3, 15: 4}

    def __init__(self) -> None:
        super().__init__("telescope_simple_node")
        env, _ = load_environment(self)

        self._command_topic = declare_env_parameter(
            self,
            env,
            "telescopic_command_topic",
            "ROS_TOPIC_KINEMATICS_TELESCOPIC_CMD_SEQ",
            "/control/kinematics_telescopic_cmd_sequenced",
        )
        self._feedback_topic = declare_env_parameter(
            self,
            env,
            "telescopic_feedback_topic",
            "ROS_TOPIC_TELESCOPE_FEEDBACK",
            "/hardware/telescope_feedback",
        )
        self._output_topic = declare_env_parameter(
            self,
            env,
            "telescopic_output_topic",
            "ROS_TOPIC_TELESCOPE_OUTPUT",
            "/hardware/telescope_output",
        )
        self._ack_topic = declare_env_parameter(
            self,
            env,
            "cmd_ack_topic",
            "ROS_TOPIC_CMD_ACK",
            "/hardware/cmd_ack",
        )
        self._min_mm = declare_env_parameter(
            self, env, "telescopic_min_mm", "TELESCOPIC_MIN_MM", 0.0, float
        )
        self._max_mm = declare_env_parameter(
            self, env, "telescopic_max_mm", "TELESCOPIC_MAX_MM", 150.0, float
        )
        self._mm_per_rev = declare_env_parameter(
            self, env, "mm_per_rev", "MM_PER_REV", 0.7, float
        )
        self._feedback_timeout_s = declare_env_parameter(
            self, env, "feedback_timeout_s", "FEEDBACK_TIMEOUT_S", 1.0, float
        )
        db_path = declare_env_parameter(
            self, env, "db_path", "DB_PATH", "ros_database.db"
        )
        if self._min_mm >= self._max_mm:
            raise ValueError("telescopic length limits are inverted")
        if self._mm_per_rev <= 0.0:
            raise ValueError("mm_per_rev must be greater than zero")
        if self._feedback_timeout_s <= 0.0:
            raise ValueError("feedback_timeout_s must be greater than zero")

        self._mm_per_degree = self._mm_per_rev / 360.0
        self._degrees_per_mm = 360.0 / self._mm_per_rev
        self._lengths = {arm: 0.0 for arm in range(5)}
        self._axis_ready = {arm: False for arm in range(5)}
        self._last_feedback_s = {arm: 0.0 for arm in range(5)}

        self._output_publisher = self.create_publisher(IntCmd, self._output_topic, 10)
        self._ack_publisher = self.create_publisher(CmdAck, self._ack_topic, 10)
        self.create_subscription(
            TelescopicCmd, self._command_topic, self._on_command, 10
        )
        self.create_subscription(
            TelescopicCmd, self._feedback_topic, self._on_feedback, 10
        )
        self._sensor_log = SensorLog(db_path, self.get_logger())

        self.get_logger().info(
            f"Telescopic node ready: limits {self._min_mm:.2f}..{self._max_mm:.2f} mm"
        )

    def _now_s(self) -> float:
        return self.get_clock().now().nanoseconds / 1_000_000_000.0

    def _header(self):
        return self.get_clock().now().to_msg()

    def _publish_over_limit(self, source: TelescopicCmd, detail: int) -> None:
        ack = CmdAck()
        ack.header.stamp = self._header()
        ack.module_id = source.module_id
        ack.device_id = source.device_id
        ack.ack_msg = 1
        ack.result = 3
        ack.detail = detail
        self._ack_publisher.publish(ack)

    def _on_command(self, message: TelescopicCmd) -> None:
        arm_index = self.TELESCOPIC_AXES.get(int(message.device_id), -1)
        if arm_index < 0:
            self.get_logger().warning(
                "Telescopic command ignored for "
                f"unknown device_id={message.device_id}"
            )
            return
        if not message.position:
            self.get_logger().warning("Telescopic command has an empty position array")
            return
        if not self._axis_ready[arm_index]:
            self.get_logger().warning(
                f"Arm {arm_index + 1} has no telescopic feedback baseline; "
                "command rejected",
                throttle_duration_sec=2.0,
            )
            return

        delta_mm = float(message.position[0])
        next_length = self._lengths[arm_index] + delta_mm
        if next_length < self._min_mm or next_length > self._max_mm:
            detail = 1 if next_length > self._max_mm else 2
            self._publish_over_limit(message, detail)
            self.get_logger().warning(
                f"Arm {arm_index + 1} telescopic limit hit: {next_length:.3f} mm, "
                f"allowed {self._min_mm:.2f}..{self._max_mm:.2f}"
            )
            return

        self._lengths[arm_index] = next_length
        delta_centideg = int(round(delta_mm * self._degrees_per_mm * 100.0))
        output = IntCmd()
        output.header.stamp = self._header()
        output.module_id = message.module_id
        output.device_id = message.device_id
        output.position = [delta_centideg]
        self._output_publisher.publish(output)
        self._sensor_log.insert(
            message.module_id,
            message.device_id,
            delta_centideg,
            "telescopic increment output",
        )
        self.get_logger().info(
            f"Arm {arm_index + 1} telescopic {delta_mm:+.3f} mm -> "
            f"{delta_centideg} centideg, length {next_length:+.3f} mm"
        )

    def _on_feedback(self, message: TelescopicCmd) -> None:
        arm_index = self.TELESCOPIC_AXES.get(int(message.device_id), -1)
        if arm_index < 0 or not message.position:
            return

        length_mm = float(message.position[0]) * self._mm_per_degree
        now_s = self._now_s()
        previous_s = self._last_feedback_s[arm_index]
        if not self._axis_ready[arm_index]:
            self._lengths[arm_index] = length_mm
            self._axis_ready[arm_index] = True
            self.get_logger().info(
                f"Arm {arm_index + 1} telescopic baseline set to {length_mm:+.3f} mm"
            )
        elif now_s - previous_s > self._feedback_timeout_s:
            self._lengths[arm_index] = length_mm
            self.get_logger().warning(
                f"Arm {arm_index + 1} telescopic feedback resumed after "
                f"{now_s - previous_s:.2f}s; baseline reset to {length_mm:+.3f} mm"
            )
        self._last_feedback_s[arm_index] = now_s

    def destroy_node(self) -> bool:
        if hasattr(self, "_sensor_log"):
            self._sensor_log.close()
        return super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = None
    try:
        node = TelescopeSimple()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
