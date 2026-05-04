#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import rospy
from std_msgs.msg import Header
from robot_control_backend.msg import SwingCmd, IntCmd

## --------------------摆动轴功能节点----------------
class SwingSimple:
    def __init__(self):
        rospy.init_node("swing_simple_node")
        rospy.loginfo("✅ 摆动轴节点启动")

        # --- 核心参数 ---
        self.DEGREE_PER_TICK = 0.01248

        # 编码器限位
        self.ENC_MID = 15000
        self.ENC_MIN = 580
        self.ENC_MAX = 29420

        # 核心变量
        self.target_delta_deg = 0.0
        self.current_swing_deg = 0.0
        self.target_reach_deg = 0.0

        # 订阅双指令
        rospy.Subscriber("/control/adjust_swing_cmd", SwingCmd, self.cmd_callback)
        rospy.Subscriber("/control/kinematics_swing_cmd", SwingCmd, self.cmd_callback)
        rospy.Subscriber("/hardware/swing_feedback", SwingCmd, self.feedback_callback)

        # 发布输出
        self.output_pub = rospy.Publisher("/hardware/swing_output", IntCmd, queue_size=10)
        self.sensor_cmd = rospy.Publisher("/control/sensor_cmd", IntCmd, queue_size=10)


    def cmd_callback(self, msg):
        """收到指令 → 计算 → 只发一次"""
        self.target_delta_deg = msg.position[0]
        self.target_reach_deg = self.current_swing_deg + self.target_delta_deg

        # 角度 → 编码（带限位）
        target_tick = self.ENC_MID + int(round(self.target_reach_deg / self.DEGREE_PER_TICK))
        target_tick = max(self.ENC_MIN, min(target_tick, self.ENC_MAX))

        # 构建消息
        int_cmd_msg = IntCmd()
        int_cmd_msg.header = Header()
        int_cmd_msg.header.stamp = rospy.Time.now()
        int_cmd_msg.module_id = 17
        int_cmd_msg.device_id = 34
        int_cmd_msg.position = [target_tick]

        sen_cmd_msg = IntCmd()
        sen_cmd_msg.header = Header()
        sen_cmd_msg.header.stamp = rospy.Time.now()
        sen_cmd_msg.module_id = 17
        sen_cmd_msg.device_id = 49
        sen_cmd_msg.position = 0

        # 只发一次！
        self.output_pub.publish(int_cmd_msg)
        self.sensor_cmd.publish(sen_cmd_msg)

        # 日志
        cmd_topic = msg._connection_header.get('topic', '未知话题')
        if cmd_topic == "/control/adjust_swing_cmd":
            rospy.loginfo(f"摆动轴微调：+{self.target_delta_deg:.4f}° → 下发编码：{target_tick}")
        elif cmd_topic == "/control/kinematics_swing_cmd":
            rospy.loginfo(f"摆动轴运动学：+{self.target_delta_deg:.4f}° → 下发编码：{target_tick}")

    def feedback_callback(self, msg):
        """仅监控，不发指令"""
        if msg.device_id == 42:
            self.current_swing_deg = msg.position[0]

if __name__ == "__main__":
    try:
        node = SwingSimple()
        rospy.spin()  # 无循环，纯事件驱动
    except rospy.RosInterruptException:
        rospy.loginfo("摆动轴节点停止")
    except Exception as e:
        rospy.logerr(f"摆动轴异常：{str(e)}")