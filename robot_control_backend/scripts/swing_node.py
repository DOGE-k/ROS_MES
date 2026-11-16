#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from robot_control_backend.msg import CmdAck, IntCmd, SwingCmd
from robot_control_runtime.params import declare_env_parameter, load_environment
from robot_control_runtime.telemetry import SensorLog


class SwingSimple(Node):
    SWING_AXES = {2: 0, 5: 1, 8: 2, 11: 3, 14: 4}

    def __init__(self) -> None:
        super().__init__("swing_simple_node")
        env, _ = load_environment(self)

        self._command_topic = declare_env_parameter(
            self,
            env,
            "swing_command_topic",
            "ROS_TOPIC_KINEMATICS_SWING_CMD_SEQ",
            "/control/kinematics_swing_cmd_sequenced",
        )
        self._feedback_topic = declare_env_parameter(
            self,
            env,
            "swing_feedback_topic",
            "ROS_TOPIC_SWING_FEEDBACK",
            "/hardware/swing_feedback",
        )
        self._output_topic = declare_env_parameter(
            self,
            env,
            "swing_output_topic",
            "ROS_TOPIC_SWING_OUTPUT",
            "/hardware/swing_output",
        )
        self._ack_topic = declare_env_parameter(
            self,
            env,
            "cmd_ack_topic",
            "ROS_TOPIC_CMD_ACK",
            "/hardware/cmd_ack",
        )
        self._min_angle = declare_env_parameter(
            self, env, "swing_min_angle", "SWING_MIN_ANGLE", 0.0, float
        )
        self._max_angle = declare_env_parameter(
            self, env, "swing_max_angle", "MAX_SWING_ANGLE", 15.0, float
        )
        self._feedback_timeout_s = declare_env_parameter(
            self, env, "feedback_timeout_s", "FEEDBACK_TIMEOUT_S", 1.0, float
        )
        db_path = declare_env_parameter(
            self, env, "db_path", "DB_PATH", "ros_database.db"
        )
        if self._min_angle >= self._max_angle:
            raise ValueError("swing angle limits are inverted")
        if self._feedback_timeout_s <= 0.0:
            raise ValueError("feedback_timeout_s must be greater than zero")

        self._angles = {arm: 0.0 for arm in range(5)}
        self._axis_ready = {arm: False for arm in range(5)}
        self._last_feedback_s = {arm: 0.0 for arm in range(5)}

        self._output_publisher = self.create_publisher(IntCmd, self._output_topic, 10)
        self._ack_publisher = self.create_publisher(CmdAck, self._ack_topic, 10)
        self.create_subscription(SwingCmd, self._command_topic, self._on_command, 10)
        self.create_subscription(SwingCmd, self._feedback_topic, self._on_feedback, 10)
        self._sensor_log = SensorLog(db_path, self.get_logger())

        self.get_logger().info(
            f"Swing node ready: limits {self._min_angle:.2f}..{self._max_angle:.2f} deg"
        )

    def _now_s(self) -> float:
        return self.get_clock().now().nanoseconds / 1_000_000_000.0

    def _header(self):
        return self.get_clock().now().to_msg()

    def _publish_over_limit(self, source: SwingCmd, detail: int) -> None:
        ack = CmdAck()
        ack.header.stamp = self._header()
        ack.module_id = source.module_id
        ack.device_id = source.device_id
        ack.ack_msg = 1
        ack.result = 3
        ack.detail = detail
        self._ack_publisher.publish(ack)

    def _on_command(self, message: SwingCmd) -> None:
        arm_index = self.SWING_AXES.get(int(message.device_id), -1)
        if arm_index < 0:
            self.get_logger().warning(
                f"Swing command ignored for unknown device_id={message.device_id}"
            )
            return
        if not message.position:
            self.get_logger().warning("Swing command has an empty position array")
            return
        if not self._axis_ready[arm_index]:
            self.get_logger().warning(
                f"Arm {arm_index + 1} has no swing feedback baseline; command rejected",
                throttle_duration_sec=2.0,
            )
            return

        delta_degrees = float(message.position[0])
        next_angle = self._angles[arm_index] + delta_degrees
        if next_angle < self._min_angle or next_angle > self._max_angle:
            detail = 1 if next_angle > self._max_angle else 2
            self._publish_over_limit(message, detail)
            self.get_logger().warning(
                f"Arm {arm_index + 1} swing limit hit: {next_angle:.3f} deg, "
                f"allowed {self._min_angle:.2f}..{self._max_angle:.2f}"
            )
            return

        self._angles[arm_index] = next_angle
        delta_centideg = int(round(delta_degrees * 100.0))
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
            "swing increment output",
        )
        self.get_logger().info(
            f"Arm {arm_index + 1} swing {delta_degrees:+.4f} deg -> "
            f"{delta_centideg} centideg, position {next_angle:+.3f} deg"
        )

    def _on_feedback(self, message: SwingCmd) -> None:
        arm_index = self.SWING_AXES.get(int(message.device_id), -1)
        if arm_index < 0 or not message.position:
            return

        angle = float(message.position[0])
        now_s = self._now_s()
        previous_s = self._last_feedback_s[arm_index]
        if not self._axis_ready[arm_index]:
            self._angles[arm_index] = angle
            self._axis_ready[arm_index] = True
            self.get_logger().info(
                f"Arm {arm_index + 1} swing baseline set to {angle:+.3f} deg"
            )
        elif now_s - previous_s > self._feedback_timeout_s:
            self._angles[arm_index] = angle
            self.get_logger().warning(
                f"Arm {arm_index + 1} swing feedback resumed after "
                f"{now_s - previous_s:.2f}s; baseline reset to {angle:+.3f} deg"
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
        node = SwingSimple()
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
