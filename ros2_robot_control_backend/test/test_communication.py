#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROS与下位机通信测试脚本
用于测试：伸缩轴指令 → 触发压力传感器 → 硬件桥接 的完整流程
不需要实际的伸缩杆电机和压力传感器硬件
"""

import rospy
import time
from std_msgs.msg import Header
from robot_control_backend.msg import TelescopicCmd, IntCmd, Feedback

class CommunicationTest:
    def __init__(self):
        rospy.init_node('communication_test_node')
        
        # 发布者：模拟上位机发送伸缩轴指令
        self.pub_telescopic_cmd = rospy.Publisher(
            '/control/adjust_telescopic_cmd', 
            TelescopicCmd, 
            queue_size=10
        )
        
        # 订阅者：监控各个节点的输出
        rospy.Subscriber('/hardware/telescope_output', IntCmd, self.telescope_output_callback)
        rospy.Subscriber('/control/sensor_cmd', IntCmd, self.sensor_cmd_callback)
        rospy.Subscriber('/arm/cmd_vel', IntCmd, self.arm_cmd_vel_callback)
        rospy.Subscriber('/hardware/all_feedback', Feedback, self.feedback_callback)
        
        rospy.loginfo("🔧 通信测试节点已启动")
        rospy.loginfo("等待其他节点启动...")
        time.sleep(3)  # 等待其他节点启动
        
    def telescope_output_callback(self, msg):
        """收到伸缩轴输出指令"""
        rospy.loginfo(f"✅ 伸缩轴节点输出: module_id={msg.module_id}, device_id={msg.device_id}, position={msg.position}")
        
    def sensor_cmd_callback(self, msg):
        """收到传感器触发指令"""
        rospy.loginfo(f"✅ 传感器触发信号: module_id={msg.module_id}, device_id={msg.device_id}, position={msg.position}")
        
    def arm_cmd_vel_callback(self, msg):
        """收到硬件指令"""
        rospy.loginfo(f"✅ 硬件指令: module_id={msg.module_id}, device_id={msg.device_id}, position={msg.position}")
        
    def feedback_callback(self, msg):
        """收到反馈数据"""
        rospy.loginfo(f"📡 反馈数据: module_id={msg.module_id}, device_id={msg.device_id}, position={msg.position}")
        
    def send_test_command(self):
        """发送测试指令"""
        rospy.loginfo("\n=== 发送测试指令 ===")
        
        # 创建伸缩轴指令
        cmd = TelescopicCmd()
        cmd.header = Header(stamp=rospy.Time.now())
        cmd.module_id = 17  # 目标模块ID
        cmd.device_id = 35  # 伸缩轴设备ID
        cmd.position = [10.0]  # 移动10mm
        
        rospy.loginfo(f"发送伸缩轴指令: +10mm")
        self.pub_telescopic_cmd.publish(cmd)
        
        # 等待流程完成
        rospy.loginfo("等待流程执行...")
        time.sleep(10)  # 等待压力传感器延迟和序列发送
        
    def run(self):
        self.send_test_command()
        rospy.loginfo("\n=== 测试完成 ===")

if __name__ == '__main__':
    try:
        test = CommunicationTest()
        test.run()
    except rospy.ROSInterruptException:
        rospy.loginfo("测试节点已停止")
    except Exception as e:
        rospy.logerr(f"测试异常: {e}")
