#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import rospy
import os
from robot_control_backend.msg import IntCmd

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

class TestStopReceiver:
    def __init__(self):
        load_env_config()
        rospy.init_node('test_stop_receiver', anonymous=True)
        
        # 从环境变量获取话题名称
        topic_arm_cmd = os.environ.get('ROS_TOPIC_ARM_CMD_VEL', '/arm/cmd_vel')
        rospy.Subscriber(topic_arm_cmd, IntCmd, self.stop_callback)
        rospy.loginfo("Test receiver ready, waiting for stop command on %s", topic_arm_cmd)

    def stop_callback(self, msg):
        """接收到停止指令的回调"""
        if not msg.position or all(v == 0 for v in msg.position):
            rospy.loginfo("SUCCESS received stop command: module_id=%d, device_id=%d, position=%s",
                          msg.module_id, msg.device_id, msg.position)
        else:
            rospy.loginfo("Received non-stop command (ignored): module_id=%d, device_id=%d",
                          msg.module_id, msg.device_id)

    def run(self):
        rospy.spin()

if __name__ == '__main__':
    try:
        receiver = TestStopReceiver()
        receiver.run()
    except rospy.ROSInterruptException:
        pass