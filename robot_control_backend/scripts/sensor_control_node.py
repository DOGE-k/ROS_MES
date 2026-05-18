#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
压力传感器控制节点 - 独立节点
订阅话题：/control/sensor_cmd
发布话题：/arm/cmd_vel (IntCmd)

功能：接收触发信号后，延迟7秒发送压力传感器开关序列
"""

import rospy
import os
import time
from std_msgs.msg import Header
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
        rospy.loginfo("✅ 已从 rob_arm.env 加载配置")

class PressureSensorControlNode:
    def __init__(self):
        load_env_config()
        rospy.init_node("pressure_sensor_control_node")
        
        # 配置参数（从环境变量读取）
        self.DEV_SENSOR = int(os.environ.get('DEV_SENSOR', '49'))
        self.SENSOR_DELAY = float(os.environ.get('SENSOR_DELAY', '7.0'))
        
        rospy.loginfo(f"压力传感器控制节点已启动 | 延迟: {self.SENSOR_DELAY}s")

        # 话题名称（从环境变量读取）
        TOPIC_ARM_CMD_VEL = os.environ.get('ROS_TOPIC_ARM_CMD_VEL', '/arm/cmd_vel')
        TOPIC_SENSOR_CMD = os.environ.get('ROS_TOPIC_SENSOR_CMD', '/control/sensor_cmd')

        # 发布：向下位机发送压力传感器开关指令
        self.pub_sensor_cmd = rospy.Publisher(TOPIC_ARM_CMD_VEL, IntCmd, queue_size=10)

        # 订阅：触发信号
        rospy.Subscriber(TOPIC_SENSOR_CMD, IntCmd, self.trigger_callback)

    def trigger_callback(self, msg):
        """收到触发信号 → 延迟7秒后发送压力传感器开关序列"""
        target_module_id = msg.module_id
        rospy.loginfo(f"📡 收到传感器触发指令，module_id={target_module_id}")
        
        # 延迟指定时间后发送传感器指令
        rospy.loginfo(f"⏳ 将在 {self.SENSOR_DELAY}s 后发送压力传感器指令")
        rospy.Timer(rospy.Duration(self.SENSOR_DELAY), 
                    lambda event, mid=target_module_id: self.send_sensor_sequence(mid),
                    oneshot=True)

    def send_sensor_sequence(self, module_id):
        """发送压力传感器开关序列（2帧）"""
        rospy.loginfo("🔌 发送压力传感器指令序列")

        # 第1帧：关闭
        cmd1 = IntCmd()
        cmd1.header = Header()
        cmd1.header.stamp = rospy.Time.now()
        cmd1.module_id = module_id
        cmd1.device_id = self.DEV_SENSOR
        cmd1.position = 0
        self.pub_sensor_cmd.publish(cmd1)
        rospy.loginfo(f"压力传感器指令1: module={module_id}, pos=0")

        # 延迟0.5秒发送第2帧
        time.sleep(0.5)

        # 第2帧：打开
        cmd2 = IntCmd()
        cmd2.header = Header()
        cmd2.header.stamp = rospy.Time.now()
        cmd2.module_id = module_id
        cmd2.device_id = self.DEV_SENSOR
        cmd2.position = 1
        self.pub_sensor_cmd.publish(cmd2)
        rospy.loginfo(f"压力传感器指令2: module={module_id}, pos=1")

        rospy.loginfo("✅ 压力传感器指令序列发送完成")

if __name__ == '__main__':
    try:
        PressureSensorControlNode()
        rospy.spin()
    except rospy.ROSInterruptException:
        rospy.loginfo("❌ 压力传感器控制节点已停止")
