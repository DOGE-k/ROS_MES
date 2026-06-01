#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import rospy
import os
from robot_control_backend.msg import IntCmd
from std_msgs.msg import Header

def load_env_config():
    """从 .env 文件加载配置"""
    env_path = os.path.join(os.path.dirname(__file__), '../rob_arm.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    os.environ[key] = value
        rospy.loginfo("Loaded config from rob_arm.env")

class EmergencyStopNode:
    def __init__(self):
        load_env_config()
        rospy.init_node('softstop_node')

        # 从环境变量获取配置
        default_module_id = int(os.environ.get('MODULE_ID', '17'))
        self.stop_trigger_device_id = int(os.environ.get('EMERGENCY_STOP_DEVICE_ID', '1'))
        self.stop_cmd_module = int(os.environ.get('MODULE_ID', str(default_module_id)))
        self.stop_cmd_device = self.stop_trigger_device_id

        # 发布者：机械臂速度指令话题
        topic_arm_cmd = os.environ.get('ROS_TOPIC_ARM_CMD_VEL', '/arm/cmd_vel')
        self.cmd_pub = rospy.Publisher(topic_arm_cmd, IntCmd, queue_size=10)
        # 订阅者：前端软停指令
        rospy.Subscriber('/control/softstop', IntCmd, self.cmd_callback, queue_size=10)

        rospy.loginfo("Emergency stop node started, watching device_id=%d", self.stop_trigger_device_id)

    def cmd_callback(self, msg):
        # 检查 device_id 是否匹配急停触发条件
        if msg.device_id == 1:
            rospy.logwarn("Emergency stop triggered by device_id %d, module_id=%d", msg.device_id, msg.module_id)
            self.publish_stop(msg.module_id)
        # 其他 device_id 可忽略或转发（根据需求扩展）

    def publish_stop(self, module_id):
        """构造并发布停止指令，使所有运动轴速度置零"""
        stop_cmd = IntCmd()
        stop_cmd.header = Header(stamp=rospy.Time.now())
        stop_cmd.module_id = module_id
        stop_cmd.device_id = self.stop_cmd_device
        stop_cmd.position = []
        self.cmd_pub.publish(stop_cmd)
        rospy.logdebug("Stop command sent: module=%d, device=%d, position=%s",
                       stop_cmd.module_id, stop_cmd.device_id, stop_cmd.position)

    def run(self):
        rospy.spin()

if __name__ == '__main__':
    try:
        node = EmergencyStopNode()
        node.run()
    except rospy.ROSInterruptException:
        pass
