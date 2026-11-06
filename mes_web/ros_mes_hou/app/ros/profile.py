# app/ros/profile.py
"""ROS1 / ROS2 协议差异集中定义。

前后端与 ROS 端之间全部走 rosbridge 的 JSON 协议（advertise/publish/subscribe），
该协议在 ROS1 与 ROS2 下语义一致，真正的版本差异只有：

- 消息类型串格式：ROS1 为 `robot_control_backend/RotationCmd`，ROS2 为 `robot_control_backend/msg/RotationCmd`
- header.stamp 字段名：ROS1 为 `secs/nsecs`，ROS2 为 `sec/nanosec`
- rospy 原生节点（仅 ROS1 保留为历史兼容；测试页通道已统一走 rosbridge，两版行为一致）

切换方式：环境变量 `ROS_VERSION`（支持 1/ros1/2/ros2，默认 1）。
话题名默认与 ROS1 现网一致；ROS 端调整话题时优先用环境变量
`ROS_TOPIC_<键名大写>`（如 ROS_TOPIC_DRAWING_PATH）覆盖，无需改代码。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, Tuple

from app.core.config import settings


# 话题默认值（键名即环境变量后缀，如 ROS_TOPIC_DRAWING_PATH）
TOPIC_DEFAULTS: Dict[str, str] = {
    "fine_tuning_rotation": "/control/adjust_rotation_cmd",
    "fine_tuning_swing": "/control/adjust_swing_cmd",
    "fine_tuning_telescopic": "/control/adjust_telescopic_cmd",
    "feedback_rotation": "/hardware/rotation_feedback",
    "feedback_swing": "/hardware/swing_feedback",
    "feedback_telescope": "/hardware/telescope_feedback",
    "feedback_sensor": "/hardware/sensor_feedback",
    "feedback_imu": "/hardware/imu_angles",
    # V2 新增：独立压力平均值话题（不再与瞬时值同话题混流）与失压事件话题
    "feedback_pressure_avg": "/hardware/pressure_avg",
    "feedback_vacuum_loss": "/hardware/vacuum_loss",
    # V2.1：轴节点指令回执（超位拒绝等 CmdAck），转发前端 otherwise 静默丢失
    "feedback_cmd_ack": "/hardware/cmd_ack",
    "feedback_axis_status": "/hardware/axis_status",
    "feedback_arrive": "/hardware/arrive_notification",
    "feedback_stop": "/hardware/stop_notification",
    "feedback_fault": "/hardware/axis_fault",
    "feedback_limit": "/hardware/limit_event",
    "drawing_path": "/frontend_pointcloud_topic",
    "module_cmd": "/control/module_cmd",
    "module_confirm_success": "/hardware/module_confirm_success",
    "module_confirm_failed": "/hardware/web_module_cmd",
    "softstop": "/control/softstop",
    "softstop_release": "/control/softstop_release",
    # 测试通道（/ros/** 接口）：ROS1 走 rospy、ROS2 走 rosbridge，话题契约一致
    "web_cmd": "/web_cmd",
    "robot_status": "/robot_status",
}


def _topics() -> Dict[str, str]:
    topics = dict(TOPIC_DEFAULTS)
    for key in topics:
        env_value = os.getenv(f"ROS_TOPIC_{key.upper()}")
        if env_value:
            topics[key] = env_value
    return topics


@dataclass(frozen=True)
class RosProfile:
    name: str                        # "ros1" / "ros2"
    type_prefix: str                 # 自定义包消息类型前缀
    std_type_prefix: str             # std_msgs 消息类型前缀
    stamp_fields: Tuple[str, str]    # header.stamp 的两个字段名
    native_node: bool                # 是否启动 rospy 原生节点
    scripts_dir: str                 # ROS 端脚本目录（子进程工具用）
    topics: Dict[str, str] = field(default_factory=_topics)

    def message_type(self, msg: str) -> str:
        return f"{self.type_prefix}/{msg}"

    def std_message_type(self, msg: str) -> str:
        return f"{self.std_type_prefix}/{msg}"


ROS1_PROFILE = RosProfile(
    name="ros1",
    type_prefix="robot_control_backend",
    std_type_prefix="std_msgs",
    stamp_fields=("secs", "nsecs"),
    native_node=True,
    scripts_dir=settings.ROS_SCRIPTS_DIR,
)

ROS2_PROFILE = RosProfile(
    name="ros2",
    type_prefix="robot_control_backend/msg",
    std_type_prefix="std_msgs/msg",
    stamp_fields=("sec", "nanosec"),
    native_node=False,
    scripts_dir=settings.ROS_SCRIPTS_DIR,
)

_PROFILES = {"ros1": ROS1_PROFILE, "ros2": ROS2_PROFILE}


def resolve_ros_version() -> str:
    """解析 ROS_VERSION 环境变量为 "ros1" / "ros2"。

    每次调用时读取（不缓存到 settings），便于测试与部署脚本切换。
    """
    raw = (os.getenv("ROS_VERSION") or "1").strip().lower()
    if raw not in ("1", "ros1", "2", "ros2"):
        raise RuntimeError(f"ROS_VERSION 环境变量非法: {raw!r}（支持 1/ros1/2/ros2）")
    return "ros1" if raw in ("1", "ros1") else "ros2"


def get_active_profile() -> RosProfile:
    return _PROFILES[resolve_ros_version()]
