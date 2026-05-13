#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
        rospy.loginfo("压力传感器控制节点已启动")

        # 话题名称（从环境变量读取）
        TOPIC_ARM_CMD_VEL = os.environ.get('ROS_TOPIC_ARM_CMD_VEL', '/arm/cmd_vel')
        TOPIC_SENSOR_CMD = os.environ.get('ROS_TOPIC_SENSOR_CMD', '/control/sensor_cmd')

        # 设备参数（从环境变量读取）
        self.DEV_SENSOR = int(os.environ.get('DEV_SENSOR', '49'))

        # 发布：向下位机发送压力传感器开关指令
        self.pub_sensor_cmd = rospy.Publisher(
            TOPIC_ARM_CMD_VEL, 
            IntCmd, 
            queue_size=10
        )

        # 订阅：任意节点发来的触发信号（用来获取 module_id）
        rospy.Subscriber(TOPIC_SENSOR_CMD, IntCmd, self.trigger_callback)

    def trigger_callback(self, msg):
        """收到触发信号 → 自动发送 2 帧压力传感器指令"""
        rospy.loginfo("收到触发指令，开始发送压力传感器开关序列...")

        target_module_id = msg.module_id

        time.sleep(7)
        # ======================
        # 第 1 次发送
        # ======================
        cmd1 = IntCmd()
        cmd1.header = Header()
        cmd1.header.stamp = rospy.Time.now()
        cmd1.module_id = target_module_id
        cmd1.device_id = self.DEV_SENSOR
        cmd1.position = 0

        self.pub_sensor_cmd.publish(cmd1)
        rospy.loginfo(f"第1帧发送：module={target_module_id}, device={self.DEV_SENSOR}, pos=0")

        # 间隔 0.5 秒
        time.sleep(0.5)

        # ======================
        # 第 2 次发送
        # ======================
        cmd2 = IntCmd()
        cmd2.header = Header()
        cmd2.header.stamp = rospy.Time.now()
        cmd2.module_id = target_module_id
        cmd2.device_id = self.DEV_SENSOR
        cmd2.position = 1

        self.pub_sensor_cmd.publish(cmd2)
        rospy.loginfo(f"第2帧发送： module={target_module_id}, device={self.DEV_SENSOR}, pos=1")

        rospy.loginfo("压力传感器开关指令序列发送完成！")

if __name__ == '__main__':
    try:
        PressureSensorControlNode()
        rospy.spin()
    except rospy.ROSInterruptException:
        rospy.loginfo("❌ 压力传感器控制节点已停止")
