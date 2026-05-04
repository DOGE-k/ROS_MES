#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import rospy
from std_msgs.msg import Header
from robot_control_backend.msg import RotationCmd, IntCmd

## -------旋转轴功能节点-------------
class RotationSimple:
    def __init__(self):
        rospy.init_node("rotation_simple_node")
        rospy.loginfo("旋转轴节点启动")

        # 编码器换算系数
        self.DEGREE_PER_TICK = 0.01248  # 1编码 = 0.01248°

        # ==========================
        # 编码器硬件限位
        # ==========================
        self.ENC_MID = 15000
        self.ENC_MIN = 580
        self.ENC_MAX = 29420

        # 核心变量
        self.has_new_command = False    # 是否有新指令需要下发
        self.target_delta_deg = 0.0     # 增量角度指令
        self.current_angle_deg = 0.0    # 当前实际角度
        self.target_reach_deg = 0.0     # 目标角度

        # 订阅双指令话题
        rospy.Subscriber("/control/adjust_rotation_cmd", RotationCmd, self.cmd_callback)
        rospy.Subscriber("/control/kinematics_rotation_cmd", RotationCmd, self.cmd_callback)
        rospy.Subscriber("/hardware/rotation_feedback", RotationCmd, self.feedback_callback)
        
        # 发布输出
        self.output_pub = rospy.Publisher("/hardware/rotation_output", IntCmd, queue_size=10)
        self.sensor_cmd = rospy.Publisher("/control/sensor_cmd", IntCmd, queue_size=10)


    def cmd_callback(self, msg):
        """接收增量指令 → 计算目标 → 只发一次命令"""
        self.target_delta_deg = msg.position[0]
        self.target_reach_deg = self.current_angle_deg + self.target_delta_deg

        # ==========================
        # 角度 → 编码器编码（带限位）
        # ==========================
        target_tick = self.ENC_MID + int(round(self.target_reach_deg / self.DEGREE_PER_TICK))
        target_tick = max(self.ENC_MIN, min(target_tick, self.ENC_MAX))

        # ==========================
        # 构建消息并发布（只发一次）
        # ==========================
        int_cmd_msg = IntCmd()
        int_cmd_msg.header = Header()
        int_cmd_msg.header.stamp = rospy.Time.now()
        int_cmd_msg.module_id = 17
        int_cmd_msg.device_id = 33
        int_cmd_msg.position = [target_tick]

        sen_cmd_msg = IntCmd()
        sen_cmd_msg.header = Header()
        sen_cmd_msg.header.stamp = rospy.Time.now()
        sen_cmd_msg.module_id = 17
        sen_cmd_msg.device_id = 49
        sen_cmd_msg.position = 0

        self.output_pub.publish(int_cmd_msg)
        self.sensor_cmd.publish(sen_cmd_msg)
        # 日志
        cmd_topic = msg._connection_header.get('topic', '未知话题')
        if cmd_topic == "/control/adjust_rotation_cmd":
            rospy.loginfo(f"旋转轴微调：+{self.target_delta_deg:.4f}° → 下发编码：{target_tick}")
        elif cmd_topic == "/control/kinematics_rotation_cmd":
            rospy.loginfo(f"旋转轴运动学：+{self.target_delta_deg:.4f}° → 下发编码：{target_tick}")

    def feedback_callback(self, msg):
        """仅更新当前角度，监控状态"""
        if msg.device_id == 33:
            self.current_angle_deg = msg.position[0]

if __name__ == "__main__":
    try:
        node = RotationSimple()
        rospy.spin()  
    except rospy.ROSInterruptException:
        rospy.loginfo("旋转轴节点停止")
    except Exception as e:
        rospy.logerr(f"旋转轴异常：{str(e)}")