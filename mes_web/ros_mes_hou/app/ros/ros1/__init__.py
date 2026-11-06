# app/ros/ros1/__init__.py
"""ROS1 适配器：rosbridge 通道为主，rospy 原生节点保留作历史兼容。

- 下发/订阅/测试页：全部走 rosbridge（干净 venv 无 rospy 也能完整工作）；
- start_native_node 会叠加启动 rospy 原生节点线程（/web_cmd、/robot_status，
  原 app/services/ros_service.py 迁入）；rospy 不可用时静默跳过，不影响其他功能。
"""
from typing import Any, Dict

from app.ros.profile import ROS1_PROFILE
from app.ros.ros1 import native
from app.ros.rosbridge import RosbridgeTransport


class Ros1Dispatcher(RosbridgeTransport):
    profile = ROS1_PROFILE

    def start_native_node(self) -> None:
        super().start_native_node()  # /robot_status 后台订阅（测试页状态来源）
        if self.client.execution_mode == "real":
            native.start_ros_thread()  # rospy 原生节点（历史兼容，可用时启动）

    def publish_native_web_cmd(self, command: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """rospy 直发通道（保留给需要绕过 rosbridge 的场景，常规用继承的 publish_web_cmd）。"""
        return native.publish_ros_command(command, payload)
