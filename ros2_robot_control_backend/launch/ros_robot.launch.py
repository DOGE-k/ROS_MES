#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ROS MES V2 启动文件（ROS2 版）

用法：
    ros2 launch robot_control_backend ros_robot.launch.py

注意：
    本文件只包含 ros2_robot_control_backend/scripts 中已存在的节点。
    module_confirme_node、sim_lower_machine 等仍留在 ROS1 目录，迁移后再加。
    首次验证建议先按清单手动 ros2 run 逐个起，确认无误再用本 launch。
"""

from launch import LaunchDescription
from launch_ros.actions import Node

PACKAGE = 'robot_control_backend'


def _node(executable, name):
    return Node(
        package=PACKAGE,
        executable=executable,
        name=name,
        output='screen',
        emulate_tty=True,
    )


def generate_launch_description():
    return LaunchDescription([
        # 点云预处理 → 模块切分（含 Flask 5000 三视图）
        _node('data_process_node.py', 'data_process_node'),
        # 策略链选点（垂直 → 水平 → 曲面）
        _node('calculation_node.py', 'calculation_node'),
        # 逆解 + 增量限幅 + 下发三轴指令
        _node('kinematics_node.py', 'kinematics_node'),
    ])
