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

class TestSoftStopPublisher:
    def __init__(self):
        load_env_config()
        rospy.init_node('test_softstop_publisher', anonymous=True)
        self.pub = rospy.Publisher('/control/softstop', IntCmd, queue_size=10)
        
        # 从环境变量获取触发ID
        self.trigger_id = int(os.environ.get('TARGET_MODULE_ID', '17'))
        rospy.loginfo("Test publisher ready, will trigger with module_id=%d", self.trigger_id)

    def send_trigger(self):
        """构造并发送一次急停触发指令"""
        msg = IntCmd()
        msg.header = Header(stamp=rospy.Time.now())
        msg.module_id = self.trigger_id
        msg.device_id = 0
        msg.position = []
        self.pub.publish(msg)
        rospy.loginfo("SUCCESS sent emergency trigger: module_id=%d", self.trigger_id)

    def run(self):
        rospy.sleep(1.0)
        self.send_trigger()
        rospy.sleep(0.5)
        rospy.signal_shutdown("Test complete")

if __name__ == '__main__':
    try:
        node = TestSoftStopPublisher()
        node.run()
    except rospy.ROSInterruptException:
        pass