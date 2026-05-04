#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import rospy
from std_msgs.msg import Header
from robot_control_backend.msg import TelescopicCmd, IntCmd

# -------------------伸缩轴功能节点------------------
class TelescopeSimple:
    def __init__(self):
        rospy.init_node("telescope_simple_node")
        rospy.loginfo("✅ 伸缩轴节点启动")

        # 1. 电机参数
        self.DEGREE_PER_TICK = 0.01248
        self.MM_PER_REV = 0.7
        self.TICK_PER_MM = (360.0 / self.MM_PER_REV) / self.DEGREE_PER_TICK

        # ==========================
        # 编码器硬件限位（安全保护）
        # ==========================
        self.ENC_MID = 15000
        self.ENC_MIN = 580
        self.ENC_MAX = 29420

        # 长度机械限位
        self.MIN_LENGTH = 0.0
        self.MAX_LENGTH = 150.0

        rospy.loginfo(f"✅ 参数：1mm ≈ {self.TICK_PER_MM:.2f} 编码，长度限位 {self.MIN_LENGTH}-{self.MAX_LENGTH}mm")

        # 核心变量
        self.target_delta_mm = 0.0
        self.current_length_mm = 0.0
        self.target_reach_mm = 0.0

        # 订阅双指令
        rospy.Subscriber("/control/adjust_telescopic_cmd", TelescopicCmd, self.cmd_callback)
        rospy.Subscriber("/control/kinematics_telescopic_cmd", TelescopicCmd, self.cmd_callback)

        # ==========================
        # ✅ 修复：反馈消息类型改为 TelescopicCmd
        # ==========================
        rospy.Subscriber("/hardware/telescope_feedback", TelescopicCmd, self.feedback_callback)

        # ==========================
        # ✅ 修复：输出改为 IntCmd
        # ==========================
        self.output_pub = rospy.Publisher("/hardware/telescope_output", IntCmd, queue_size=10)

        self.rate = rospy.Rate(20)

    def cmd_callback(self, msg):
        """接收增量指令，立刻更新目标（修复逻辑失效）"""
        self.target_delta_mm = msg.position[0]

        # ==========================
        # ✅ 安全过滤：异常值直接截断
        # ==========================
        self.target_delta_mm = max(-50, min(self.target_delta_mm, 50))

        # ==========================
        # ✅ 修复：新指令必须更新目标
        # ==========================
        self.target_reach_mm = self.current_length_mm + self.target_delta_mm

        # 长度限位
        self.target_reach_mm = max(self.MIN_LENGTH, min(self.target_reach_mm, self.MAX_LENGTH))

        cmd_topic = msg._connection_header.get('topic', '未知话题')
        if cmd_topic == "/control/adjust_telescopic_cmd":
            rospy.loginfo(f"📥 伸缩轴微调：+{self.target_delta_mm:.2f}mm")
        elif cmd_topic == "/control/kinematics_telescopic_cmd":
            rospy.loginfo(f"📥 伸缩轴运动学指令：+{self.target_delta_mm:.2f}mm")

    def feedback_callback(self, msg):
        """仅更新当前长度，不覆盖目标"""
        # ==========================
        # ✅ 修复：device_id = 43
        # ==========================
        if msg.device_id == 43:
            self.current_length_mm = msg.position[0]
            rospy.logdebug(f"📩 伸缩轴反馈：{self.current_length_mm:.2f}mm")

    def run(self):
        while not rospy.is_shutdown():
            # 目标长度 → 编码值（中位基准）
            target_tick = self.ENC_MID + int(round(self.target_reach_mm * self.TICK_PER_MM))

            # ==========================
            # ✅ 硬件硬限位（绝对安全）
            # ==========================
            target_tick = max(self.ENC_MIN, min(target_tick, self.ENC_MAX))

            # 下发 IntCmd
            int_cmd_msg = IntCmd()
            int_cmd_msg.header = Header()
            int_cmd_msg.header.stamp = rospy.Time.now()
            int_cmd_msg.module_id = 17
            int_cmd_msg.device_id = 35
            int_cmd_msg.position = [target_tick]

            self.output_pub.publish(int_cmd_msg)

            # 日志
            rospy.loginfo_throttle(1,
                f"🔄 伸缩轴 | 当前:{self.current_length_mm:.1f}mm | "
                f"目标:{self.target_reach_mm:.1f}mm | "
                f"编码:{target_tick}"
            )

            self.rate.sleep()

if __name__ == "__main__":
    try:
        node = TelescopeSimple()
        node.run()
    except rospy.ROSInterruptException:
        rospy.loginfo("❌ 伸缩轴节点停止")
    except Exception as e:
        rospy.logerr(f"❌ 伸缩轴异常：{str(e)}")