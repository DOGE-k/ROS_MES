#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from robot_control_backend.msg import IntCmd
from robot_control_runtime.params import declare_env_parameter, load_environment


class EmergencyStopNode(Node):
    CMD_EMERGENCY_STOP = 0x01
    CMD_RELEASE_STOP = 0x04
    SYSTEM_DEVICE_ID = 0

    def __init__(self) -> None:
        super().__init__("softstop_node")
        env, _ = load_environment(self)

        output_topic = declare_env_parameter(
            self,
            env,
            "arm_command_topic",
            "ROS_TOPIC_ARM_CMD_VEL",
            "/arm/cmd_vel",
        )
        stop_topic = declare_env_parameter(
            self,
            env,
            "softstop_topic",
            "ROS_TOPIC_SOFTSTOP",
            "/control/softstop",
        )
        release_topic = declare_env_parameter(
            self,
            env,
            "softstop_release_topic",
            "ROS_TOPIC_SOFTSTOP_RELEASE",
            "/control/softstop_release",
        )

        self._command_publisher = self.create_publisher(IntCmd, output_topic, 10)
        self.create_subscription(IntCmd, stop_topic, self._on_stop, 10)
        self.create_subscription(IntCmd, release_topic, self._on_release, 10)
        self.get_logger().info(
            f"Softstop node ready: trigger={stop_topic}, release={release_topic}"
        )

    def _publish_system_command(self, command: int, tag: str, source: IntCmd) -> None:
        output = IntCmd()
        output.header.stamp = self.get_clock().now().to_msg()
        output.module_id = int(source.module_id)
        output.device_id = self.SYSTEM_DEVICE_ID
        output.position = [command]
        self._command_publisher.publish(output)
        self.get_logger().warning(
            f"{tag}: module_id={output.module_id}, device_id=0, "
            f"position=[0x{command:02X}]"
        )

    def _on_stop(self, message: IntCmd) -> None:
        self._publish_system_command(self.CMD_EMERGENCY_STOP, "ESTOP", message)

    def _on_release(self, message: IntCmd) -> None:
        self._publish_system_command(self.CMD_RELEASE_STOP, "RELEASE", message)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = None
    try:
        node = EmergencyStopNode()
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
