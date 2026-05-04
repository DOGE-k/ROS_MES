#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import rospy
from std_msgs.msg import Header
from robot_control_backend.msg import RotationCmd, IntCmd

## -------旋转轴功能节点-------------
class RotationSimple:
    def __init__(self):
        rospy.init_node("rotation_simple_node")
        rospy.loginfo("✅ 旋转轴节点启动")

        # 编码器换算系数
        self.DEGREE_PER_TICK = 0.01248  # 1编码 = 0.01248°

        # ==========================
        # 编码器硬件限位（你提供的参数）
        # ==========================
        self.ENC_MID = 15000
        self.ENC_MIN = 580
        self.ENC_MAX = 29420

        # 核心变量
        self.target_delta_deg = 0.0     # 增量角度指令
        self.current_angle_deg = 0.0    # 当前实际角度
        self.target_reach_deg = 0.0     # 目标角度

        # 订阅双指令话题
        rospy.Subscriber("/control/adjust_rotation_cmd", RotationCmd, self.cmd_callback)
        rospy.Subscriber("/control/kinematics_rotation_cmd", RotationCmd, self.cmd_callback)

        # ==========================
        # ✅ 修复问题1：消息类型改为 RotationCmd
        # ==========================
        rospy.Subscriber("/hardware/rotation_feedback", RotationCmd, self.feedback_callback)
        
        # 发布输出
        self.output_pub = rospy.Publisher("/hardware/rotation_output", IntCmd, queue_size=10)

        # 控制频率
        self.rate = rospy.Rate(20)

    def cmd_callback(self, msg):
        """接收增量指令，更新目标角度（不会被反馈冲掉）"""
        self.target_delta_deg = msg.position[0]
        # ✅ 修复问题2：只在指令来时更新目标，反馈不覆盖
        self.target_reach_deg = self.current_angle_deg + self.target_delta_deg

        cmd_topic = msg._connection_header.get('topic', '未知话题')
        if cmd_topic == "/control/adjust_rotation_cmd":
            rospy.loginfo(f"📥 旋转轴微调：+{self.target_delta_deg:.4f}°")
        elif cmd_topic == "/control/kinematics_rotation_cmd":
            rospy.loginfo(f"📥 旋转轴运动学指令：+{self.target_delta_deg:.4f}°")

    def feedback_callback(self, msg):
        """仅更新当前角度，不修改目标（彻底解决指令被冲掉）"""
        if msg.device_id == 33:
            self.current_angle_deg = msg.position[0]
            rospy.logdebug(f"📩 旋转轴反馈：{self.current_angle_deg:.2f}°")

    def run(self):
        """核心运行循环 + 闭环限位"""
        while not rospy.is_shutdown():
            # 角度 → 编码器值（以中位15000为基准）
            target_tick = self.ENC_MID + int(round(self.target_reach_deg / self.DEGREE_PER_TICK))

            # ==========================
            # ✅ 修复问题3：硬件硬限位
            # ==========================
            target_tick = max(self.ENC_MIN, min(target_tick, self.ENC_MAX))

            # 下发 IntCmd
            int_cmd_msg = IntCmd()
            int_cmd_msg.header = Header()
            int_cmd_msg.header.stamp = rospy.Time.now()
            int_cmd_msg.module_id = 17
            int_cmd_msg.device_id = 33
            int_cmd_msg.position = [target_tick]

            self.output_pub.publish(int_cmd_msg)

            # 调试日志
            rospy.loginfo_throttle(1, 
                f"🔄 旋转轴 | 当前:{self.current_angle_deg:.2f}° | "
                f"目标:{self.target_reach_deg:.2f}° | "
                f"下发编码:{target_tick}"
            )

            self.rate.sleep()

if __name__ == "__main__":
    try:
        node = RotationSimple()
        node.run()
    except rospy.ROSInterruptException:
        rospy.loginfo("❌ 旋转轴节点停止")
    except Exception as e:
        rospy.logerr(f"❌ 旋转轴异常：{str(e)}")