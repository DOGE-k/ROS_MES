#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
软急停节点 V2 —— 三级急停体系

V2 系统指令（device_id=0，position[0] 子命令，hardware_node 翻译为 CAN 帧）：
    position=[0x01] → 全局急停，CAN ID = 0x00000000
    position=[0x04] → 急停解除，CAN ID = 0x00000004
    position=[0x08, module_id] → 模块级安全停，CAN ID = 0x00000008 + 模块偏移
    position=[0x0C] → 单轴急停（device_id 为轴），CAN ID = 0x0000210C + 偏移

订阅：
    /control/softstop          (IntCmd) 全局急停
    /control/softstop_release  (IntCmd) 急停解除
发布：
    /arm/cmd_vel (IntCmd) → hardware_node
"""

import rospy
import os
from robot_control_backend.msg import IntCmd
from std_msgs.msg import Header


def load_env_config():
    env_path = os.path.join(os.path.dirname(__file__), '../rob_arm.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value
        rospy.loginfo("Loaded config from rob_arm.env")


class EmergencyStopNode:
    # V2 急停子命令码
    CMD_EMERGENCY_STOP = 0x01   # 全局急停 → 0x00000000
    CMD_RELEASE_STOP = 0x04     # 急停解除 → 0x00000004
    CMD_MODULE_STOP = 0x08      # 模块安全停 → 0x00000008+模块偏移
    CMD_AXIS_STOP = 0x0C        # 单轴急停 → 0x0000210C+偏移
    SYSTEM_DEVICE_ID = 0

    def __init__(self):
        load_env_config()
        rospy.init_node('softstop_node')

        # V2：module_id 不做静态配置，从前端触发消息（IntCmd.module_id）原样透传

        topic_arm_cmd = os.environ['ROS_TOPIC_ARM_CMD_VEL']
        topic_softstop = os.environ['ROS_TOPIC_SOFTSTOP']
        topic_release = os.environ['ROS_TOPIC_SOFTSTOP_RELEASE']

        self.cmd_pub = rospy.Publisher(topic_arm_cmd, IntCmd, queue_size=10)
        rospy.Subscriber(topic_softstop, IntCmd, self.stop_callback, queue_size=10)
        rospy.Subscriber(topic_release, IntCmd, self.release_callback, queue_size=10)

        rospy.loginfo("Softstop node V2 started: trigger=%s, release=%s",
                      topic_softstop, topic_release)

    def _publish_system_cmd(self, sub_cmd, tag, src_msg):
        """系统级指令：module_id 透传前端消息；device_id 系统级=0（单轴急停时透传消息值）"""
        cmd = IntCmd()
        cmd.header = Header(stamp=rospy.Time.now())
        cmd.module_id = int(src_msg.module_id)
        cmd.device_id = self.SYSTEM_DEVICE_ID
        cmd.position = [sub_cmd]
        self.cmd_pub.publish(cmd)
        rospy.logwarn("[%s] system command: module_id=%d, device_id=0, position=[0x%02X]",
                      tag, cmd.module_id, sub_cmd)

    def stop_callback(self, msg):
        """全局急停"""
        self._publish_system_cmd(self.CMD_EMERGENCY_STOP, "ESTOP", msg)

    def release_callback(self, msg):
        """急停解除（V2 ID 变更：0x02 → 0x04）"""
        self._publish_system_cmd(self.CMD_RELEASE_STOP, "RELEASE", msg)


    def run(self):
        rospy.spin()


if __name__ == '__main__':
    try:
        node = EmergencyStopNode()
        node.run()
    except rospy.ROSInterruptException:
        pass

