#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import rospy
from std_msgs.msg import Header
from robot_control_backend.msg import (
    RotationCmd,
    TelescopicCmd,
    SensorCmd,
    Feedback,
    IntCmd,
    Kinematics
)

class FeedbackNode:
    def __init__(self):
        rospy.init_node("feedback_node")
        rospy.loginfo("=" * 60)
        rospy.loginfo("✅ 反馈节点已启动（带完整调试日志）")
        rospy.loginfo("=" * 60)

        # ================= 常量 =================
        self.ENC_TO_DEG = 0.01248
        self.TELES_MM_PER_REV = 0.7
        self.PRESSURE_MAX_ADC = 16777215
        self.PRESSURE_MAX_KG = 10.0
        self.MODULE_ID = 17

        # ================= 发布者 =================
        self.pub_arm_cmd = rospy.Publisher("/arm/cmd_vel", IntCmd, queue_size=10)

        self.pub_rot_fb = rospy.Publisher("/hardware/rotation_feedback", RotationCmd, queue_size=10)
        self.pub_swing_fb = rospy.Publisher("/hardware/swing_feedback", RotationCmd, queue_size=10)
        self.pub_tel_fb = rospy.Publisher("/hardware/telescope_feedback", TelescopicCmd, queue_size=10)
        self.pub_sensor_fb = rospy.Publisher("/hardware/sensor_feedback", SensorCmd, queue_size=10)
        self.pub_md_fb = rospy.Publisher("/hardware/module_cmd", IntCmd, queue_size=10)

        # ================= 订阅者 =================
        rospy.Subscriber("/hardware/all_feedback", Feedback, self.cb_all_fb)
        rospy.Subscriber("/hardware/rotation_output", IntCmd, self.cb_rot_out)
        rospy.Subscriber("/hardware/swing_output", IntCmd, self.cb_swing_out)
        rospy.Subscriber("/hardware/telescope_output", IntCmd, self.cb_tel_out)

    # ==========================
    # 硬件原始反馈解析（带完整调试日志）
    # ==========================
    def cb_all_fb(self, msg):
        module_id = msg.module_id
        device_id = msg.device_id
        raw_code = msg.position[0]

        # 总入口日志
        rospy.loginfo("[原始硬件反馈] module: %d | device: %d | 原始编码: %d" % (
            module_id, device_id, raw_code
        ))

        # --- 旋转轴 41 ---
        if device_id == 41:
            angle = raw_code * self.ENC_TO_DEG
            rospy.loginfo("→ 旋转轴 [41] 转换: %.4f°" % angle)

            m = RotationCmd()
            m.header = Header()
            m.module_id = self.MODULE_ID
            m.device_id = 41
            m.position = [angle]
            self.pub_rot_fb.publish(m)
            rospy.loginfo("✅ 已发布旋转轴反馈 → /hardware/rotation_feedback")

        # --- 摆动轴 42 ---
        elif device_id == 42:
            angle = raw_code * self.ENC_TO_DEG
            rospy.loginfo("→ 摆动轴 [42] 转换: %.4f°" % angle)

            m = RotationCmd()
            m.header = Header()
            m.module_id = self.MODULE_ID
            m.device_id = 42
            m.position = [angle]
            self.pub_swing_fb.publish(m)
            rospy.loginfo("✅ 已发布摆动轴反馈 → /hardware/swing_feedback")

        # --- 伸缩轴 43 ---
        elif device_id == 43:
            length = raw_code * self.ENC_TO_DEG * (self.TELES_MM_PER_REV / 360.0)
            rospy.loginfo("→ 伸缩轴 [43] 转换: %.4f mm" % length)

            m = TelescopicCmd()
            m.header = Header()
            m.module_id = self.MODULE_ID
            m.device_id = 43
            m.position = [length]
            self.pub_tel_fb.publish(m)
            rospy.loginfo("✅ 已发布伸缩轴反馈 → /hardware/telescope_feedback")

        # --- 压力传感器 49 ---
        elif device_id == 49:
            kg = (raw_code / self.PRESSURE_MAX_ADC) * self.PRESSURE_MAX_KG
            N = kg * 9.81
            rospy.loginfo("→ 压力传感器 [49] 转换: %.4f kg → %.4f N" % (kg, N))

            m = SensorCmd()
            m.header = Header()
            m.id = 0
            m.module_id = self.MODULE_ID
            m.device_id = 49
            m.position = [N]
            self.pub_sensor_fb.publish(m)
            rospy.loginfo("✅ 已发布传感器反馈 → /hardware/sensor_feedback")

        # --- 模块ID 0 ---
        elif device_id == 0:
            rospy.loginfo("→ 模块指令 [0] 透传")
            m = IntCmd()
            m.header = Header()
            m.module_id = module_id
            m.device_id = device_id
            m.position = [0]
            self.pub_md_fb.publish(m)
            rospy.loginfo("✅ 已发布模块反馈 → /hardware/module_cmd")

        # 未知设备
        else:
            rospy.logwarn("⚠️  未知设备ID: %d，已忽略" % device_id)


    # ==========================
    # 轴指令转发日志
    # ==========================
    def cb_rot_out(self, msg):
        rospy.loginfo("[指令转发] 旋转轴 → /arm/cmd_vel | 编码: %d" % msg.position[0])
        self.pub_arm_cmd.publish(msg)

    def cb_swing_out(self, msg):
        rospy.loginfo("[指令转发] 摆动轴 → /arm/cmd_vel | 编码: %d" % msg.position[0])
        self.pub_arm_cmd.publish(msg)

    def cb_tel_out(self, msg):
        rospy.loginfo("[指令转发] 伸缩轴 → /arm/cmd_vel | 编码: %d" % msg.position[0])
        self.pub_arm_cmd.publish(msg)

if __name__ == "__main__":
    try:
        node = FeedbackNode()
        rospy.spin()
    except rospy.ROSInterruptException:
        rospy.loginfo("❌ 反馈节点已停止")
    except Exception as e:
        rospy.logerr("❌ 反馈节点异常: %s" % str(e))