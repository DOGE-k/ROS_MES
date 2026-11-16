#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from robot_control_backend.msg import CmdAck, IntCmd, RotationCmd
from robot_control_runtime.params import declare_env_parameter, load_environment
from robot_control_runtime.telemetry import SensorLog


class RotationSimple(Node):
    """Checks each rotation increment against the raw encoder limits."""

    ROTATION_AXES = {1: 0, 4: 1, 7: 2, 10: 3, 13: 4}

    def __init__(self) -> None:
        super().__init__("rotation_simple_node")
        env, _ = load_environment(self)

        self._command_topic = declare_env_parameter(
            self,
            env,
            "rotation_command_topic",
            "ROS_TOPIC_KINEMATICS_ROTATION_CMD_SEQ",
            "/control/kinematics_rotation_cmd_sequenced",
        )
        self._feedback_topic = declare_env_parameter(
            self,
            env,
            "rotation_feedback_topic",
            "ROS_TOPIC_ROTATION_FEEDBACK",
            "/hardware/rotation_feedback",
        )
        self._output_topic = declare_env_parameter(
            self,
            env,
            "rotation_output_topic",
            "ROS_TOPIC_ROTATION_OUTPUT",
            "/hardware/rotation_output",
        )
        self._ack_topic = declare_env_parameter(
            self,
            env,
            "cmd_ack_topic",
            "ROS_TOPIC_CMD_ACK",
            "/hardware/cmd_ack",
        )
        self._encoder_min = declare_env_parameter(
            self, env, "rotation_encoder_min", "ENC_MIN", 580, int
        )
        self._encoder_max = declare_env_parameter(
            self, env, "rotation_encoder_max", "ENC_MAX", 29420, int
        )
        self._degrees_per_tick = declare_env_parameter(
            self, env, "rotation_deg_per_tick", "DEG_PER_TICK", 0.01248, float
        )
        self._feedback_timeout_s = declare_env_parameter(
            self, env, "feedback_timeout_s", "FEEDBACK_TIMEOUT_S", 1.0, float
        )
        db_path = declare_env_parameter(
            self, env, "db_path", "DB_PATH", "ros_database.db"
        )

        if self._degrees_per_tick <= 0.0:
            raise ValueError("rotation_deg_per_tick must be greater than zero")
        if self._encoder_min >= self._encoder_max:
            raise ValueError("rotation encoder limits are inverted")
        if self._feedback_timeout_s <= 0.0:
            raise ValueError("feedback_timeout_s must be greater than zero")

        self._angles = {arm: 0.0 for arm in range(5)}
        self._axis_ready = {arm: False for arm in range(5)}
        self._last_feedback_s = {arm: 0.0 for arm in range(5)}

        self._output_publisher = self.create_publisher(IntCmd, self._output_topic, 10)
        self._ack_publisher = self.create_publisher(CmdAck, self._ack_topic, 10)
        self.create_subscription(RotationCmd, self._command_topic, self._on_command, 10)
        self.create_subscription(
            RotationCmd, self._feedback_topic, self._on_feedback, 10
        )
        self._sensor_log = SensorLog(db_path, self.get_logger())

        self.get_logger().info(
            "Rotation node ready: "
            f"encoder limits {self._encoder_min}..{self._encoder_max}, "
            f"{self._degrees_per_tick} deg/tick"
        )

    def _now_s(self) -> float:
        return self.get_clock().now().nanoseconds / 1_000_000_000.0

    def _header(self):
        return self.get_clock().now().to_msg()

    def _arm_index(self, device_id: int) -> int:
        return self.ROTATION_AXES.get(int(device_id), -1)

    def _publish_over_limit(self, source: RotationCmd, detail: int) -> None:
        ack = CmdAck()
        ack.header.stamp = self._header()
        ack.module_id = source.module_id
        ack.device_id = source.device_id
        ack.ack_msg = 1
        ack.result = 3
        ack.detail = detail
        self._ack_publisher.publish(ack)

    def _on_command(self, message: RotationCmd) -> None:
        arm_index = self._arm_index(message.device_id)
        if arm_index < 0:
            self.get_logger().warning(
                f"Rotation command ignored for unknown device_id={message.device_id}"
            )
            return
        if not message.position:
            self.get_logger().warning("Rotation command has an empty position array")
            return
        if not self._axis_ready[arm_index]:
            self.get_logger().warning(
                f"Arm {arm_index + 1} has no rotation feedback baseline; command rejected",
                throttle_duration_sec=2.0,
            )
            return

        delta_degrees = float(message.position[0])
        next_angle = self._angles[arm_index] + delta_degrees
        next_tick = round(next_angle / self._degrees_per_tick)
        if next_tick < self._encoder_min or next_tick > self._encoder_max:
            detail = 1 if next_tick > self._encoder_max else 2
            self._publish_over_limit(message, detail)
            self.get_logger().warning(
                f"Arm {arm_index + 1} rotation limit hit: "
                f"{next_angle:.3f} deg is tick {next_tick}, "
                f"allowed {self._encoder_min}..{self._encoder_max}"
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
            "rotation increment output",
        )
        self.get_logger().info(
            f"Arm {arm_index + 1} rotation {delta_degrees:+.4f} deg -> "
            f"{delta_centideg} centideg, position {next_angle:+.3f} deg"
        )

    def _on_feedback(self, message: RotationCmd) -> None:
        arm_index = self._arm_index(message.device_id)
        if arm_index < 0 or not message.position:
            return

        angle = float(message.position[0])
        now_s = self._now_s()
        previous_s = self._last_feedback_s[arm_index]
        if not self._axis_ready[arm_index]:
            self._angles[arm_index] = angle
            self._axis_ready[arm_index] = True
            self.get_logger().info(
                f"Arm {arm_index + 1} rotation baseline set to {angle:+.3f} deg"
            )
        elif now_s - previous_s > self._feedback_timeout_s:
            self._angles[arm_index] = angle
            self.get_logger().warning(
                f"Arm {arm_index + 1} rotation feedback resumed after "
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
        node = RotationSimple()
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
