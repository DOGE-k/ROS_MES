#!/usr/bin/env python3

import threading

import rclpy
from rclpy.node import Node
from robot_control_backend.msg import IntCmd
from robot_control_runtime.params import declare_env_parameter, load_environment


class ModuleConfirmer(Node):
    """Runs the two-stage command and publishes one aggregate result."""

    RESULT_SUCCESS = 100
    RESULT_FAILED = 1
    STATE_IDLE = 0
    STATE_WAIT_FEEDBACK = 1

    def __init__(self) -> None:
        super().__init__("module_confirme_node")
        env, _ = load_environment(self)

        self._trigger_topic = declare_env_parameter(
            self,
            env,
            "module_trigger_topic",
            "ROS_TOPIC_MODULE_CMD",
            "/control/module_cmd",
        )
        self._command_topic = declare_env_parameter(
            self,
            env,
            "module_command_topic",
            "ROS_TOPIC_MODULE_COMMAND_OUT",
            "/hardware/module_cmd",
        )
        self._feedback_topic = declare_env_parameter(
            self,
            env,
            "module_feedback_topic",
            "ROS_TOPIC_MODULE_FEEDBACK",
            "/hardware/module_feedback",
        )
        self._success_topic = declare_env_parameter(
            self,
            env,
            "module_success_topic",
            "ROS_TOPIC_MODULE_CONFIRM_SUCCESS",
            "/hardware/module_confirm_success",
        )
        self._failed_topic = declare_env_parameter(
            self,
            env,
            "module_failed_topic",
            "ROS_TOPIC_MODULE_CONFIRM_FAILED",
            "/hardware/web_module_cmd",
        )
        self._feedback_timeout_s = declare_env_parameter(
            self,
            env,
            "module_confirm_feedback_timeout_s",
            "MODULE_CONFIRM_FEEDBACK_TIMEOUT_S",
            5.0,
            float,
        )
        if self._feedback_timeout_s <= 0.0:
            raise ValueError(
                "module_confirm_feedback_timeout_s must be greater than zero"
            )

        self._lock = threading.Lock()
        self._state = self.STATE_IDLE
        self._pending_module_id: int | None = None
        self._deadline_s = 0.0

        self._command_publisher = self.create_publisher(IntCmd, self._command_topic, 10)
        self._success_publisher = self.create_publisher(IntCmd, self._success_topic, 10)
        self._failed_publisher = self.create_publisher(IntCmd, self._failed_topic, 10)
        self.create_subscription(IntCmd, self._trigger_topic, self._on_trigger, 10)
        self.create_subscription(IntCmd, self._feedback_topic, self._on_feedback, 10)
        self.create_timer(0.05, self._check_timeout)

        self.get_logger().info(
            "Module confirmer ready: "
            f"{self._trigger_topic} -> {self._command_topic}, "
            f"feedback timeout {self._feedback_timeout_s:.2f}s"
        )

    def _now_s(self) -> float:
        return self.get_clock().now().nanoseconds / 1_000_000_000.0

    def _publish_command(self, module_id: int, stage: int) -> None:
        message = IntCmd()
        message.header.stamp = self.get_clock().now().to_msg()
        message.module_id = module_id
        message.device_id = 0
        message.position = [stage]
        self._command_publisher.publish(message)
        self.get_logger().info(f"Module {module_id}: sent stage [{stage}]")

    def _publish_result(self, success: bool, module_id: int) -> None:
        message = IntCmd()
        message.header.stamp = self.get_clock().now().to_msg()
        message.module_id = module_id
        message.device_id = 0
        message.position = [
            self.RESULT_SUCCESS if success else self.RESULT_FAILED
        ]
        publisher = self._success_publisher if success else self._failed_publisher
        publisher.publish(message)

    def _on_trigger(self, message: IntCmd) -> None:
        if not message.position or int(message.position[0]) != 100:
            self.get_logger().warning(
                "Module confirm trigger must use position=[100]; ignored "
                f"{list(message.position)}"
            )
            return

        module_id = int(message.module_id)
        with self._lock:
            if self._state != self.STATE_IDLE:
                self.get_logger().warning(
                    f"Module {self._pending_module_id} confirmation replaced by "
                    f"module {module_id}"
                )
            self._pending_module_id = module_id
            self._deadline_s = self._now_s() + self._feedback_timeout_s
            self._state = self.STATE_WAIT_FEEDBACK
            self._publish_command(module_id, 0)

    def _on_feedback(self, message: IntCmd) -> None:
        with self._lock:
            if self._state != self.STATE_WAIT_FEEDBACK:
                return
            expected_module_id = self._pending_module_id
            if int(message.module_id) != expected_module_id:
                self.get_logger().warning(
                    f"Module confirm ignored feedback from {message.module_id}; "
                    f"waiting for {expected_module_id}",
                    throttle_duration_sec=1.0,
                )
                return

            self._state = self.STATE_IDLE
            self._pending_module_id = None
            self._deadline_s = 0.0
            self._publish_command(expected_module_id, 1)
            self._publish_result(True, expected_module_id)

        self.get_logger().info(
            f"Module {expected_module_id}: feedback matched, confirmation complete"
        )

    def _check_timeout(self) -> None:
        with self._lock:
            if self._state != self.STATE_WAIT_FEEDBACK:
                return
            if self._now_s() < self._deadline_s:
                return
            module_id = self._pending_module_id
            self._state = self.STATE_IDLE
            self._pending_module_id = None
            self._deadline_s = 0.0
            self._publish_result(False, module_id)

        self.get_logger().warning(
            f"Module {module_id}: feedback timed out after "
            f"{self._feedback_timeout_s:.2f}s"
        )


def main(args=None) -> None:
    rclpy.init(args=args)
    node = None
    try:
        node = ModuleConfirmer()
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
