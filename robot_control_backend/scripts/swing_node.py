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

        # 编码器限位（和旋转轴保持一致）
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

        # ==========================
        # ✅ 修复问题1：消息类型改为 SwingCmd
        # ==========================
        rospy.Subscriber("/hardware/swing_feedback", SwingCmd, self.feedback_callback)

        # ==========================
        # ✅ 修复问题2：输出改为 IntCmd
        # ==========================
        self.output_pub = rospy.Publisher("/hardware/swing_output", IntCmd, queue_size=10)

        self.rate = rospy.Rate(20)

    def cmd_callback(self, msg):
        """接收增量指令，立刻更新目标（修复问题4）"""
        self.target_delta_deg = msg.position[0]
        # ✅ 修复问题4：收到新指令必须更新目标
        self.target_reach_deg = self.current_swing_deg + self.target_delta_deg

        cmd_topic = msg._connection_header.get('topic', '未知话题')
        if cmd_topic == "/control/adjust_swing_cmd":
            rospy.loginfo(f"📥 摆动轴微调：+{self.target_delta_deg:.4f}°")
        elif cmd_topic == "/control/kinematics_swing_cmd":
            rospy.loginfo(f"📥 摆动轴运动学指令：+{self.target_delta_deg:.4f}°")

    def feedback_callback(self, msg):
        """仅更新当前角度，不覆盖目标"""
        # ==========================
        # ✅ 修复问题3：device_id 从 34 → 42
        # ==========================
        if msg.device_id == 42:
            self.current_swing_deg = msg.position[0]
            rospy.logdebug(f"📩 摆动轴反馈：{self.current_swing_deg:.2f}°")

    def run(self):
        while not rospy.is_shutdown():
            # 角度 → 编码器值（中位15000基准）
            target_tick = self.ENC_MID + int(round(self.target_reach_deg / self.DEGREE_PER_TICK))

            # 硬件限位
            target_tick = max(self.ENC_MIN, min(target_tick, self.ENC_MAX))

            # 下发 IntCmd
            int_cmd_msg = IntCmd()
            int_cmd_msg.header = Header()
            int_cmd_msg.header.stamp = rospy.Time.now()
            int_cmd_msg.module_id = 17
            int_cmd_msg.device_id = 34  # 执行ID = 34
            int_cmd_msg.position = [target_tick]

            self.output_pub.publish(int_cmd_msg)

            # 日志
            rospy.loginfo_throttle(1,
                f"🔄 摆动轴 | 当前:{self.current_swing_deg:.2f}° | "
                f"目标:{self.target_reach_deg:.2f}° | "
                f"下发编码:{target_tick}"
            )

            self.rate.sleep()

if __name__ == "__main__":
    try:
        node = SwingSimple()
        node.run()
    except rospy.ROSInterruptException:
        rospy.loginfo("❌ 摆动轴节点停止")
    except Exception as e:
        rospy.logerr(f"❌ 摆动轴异常：{str(e)}")