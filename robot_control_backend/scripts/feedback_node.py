#!/usr/bin/env python3
# -*- coding: utf-8 -*-
""" """
import rospy
import os
from std_msgs.msg import Header
from robot_control_backend.msg import (
    RotationCmd,
    TelescopicCmd,
    SensorCmd,
    Feedback,
    IntCmd,
    Kinematics
)

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

class FeedbackNode:
    def __init__(self):
        load_env_config()
        rospy.init_node("feedback_node")
        rospy.loginfo("=" * 60)
        rospy.loginfo("✅ 反馈节点已启动（带完整调试日志）")
        rospy.loginfo("=" * 60)

        # ================= 常量（从环境变量读取） =================
        self.ENC_TO_DEG = float(os.environ.get('ENC_TO_DEG', '0.01248'))
        self.TELES_MM_PER_REV = float(os.environ.get('TELES_MM_PER_REV', '0.7'))
        self.PRESSURE_MAX_ADC = float(os.environ.get('PRESSURE_MAX_ADC', '16777215'))
        self.PRESSURE_MAX_KG = float(os.environ.get('PRESSURE_MAX_KG', '10.0'))
        self.MODULE_ID = int(os.environ.get('MODULE_ID', '17'))

        # ================= 话题名称（从环境变量读取） =================
        TOPIC_ARM_CMD_VEL = os.environ.get('ROS_TOPIC_ARM_CMD_VEL', '/arm/cmd_vel')
        TOPIC_ROTATION_FEEDBACK = os.environ.get('ROS_TOPIC_ROTATION_FEEDBACK', '/hardware/rotation_feedback')
        TOPIC_SWING_FEEDBACK = os.environ.get('ROS_TOPIC_SWING_FEEDBACK', '/hardware/swing_feedback')
        TOPIC_TELESCOPE_FEEDBACK = os.environ.get('ROS_TOPIC_TELESCOPE_FEEDBACK', '/hardware/telescope_feedback')
        TOPIC_SENSOR_FEEDBACK = os.environ.get('ROS_TOPIC_SENSOR_FEEDBACK', '/hardware/sensor_feedback')
        TOPIC_MODULE_CMD = os.environ.get('ROS_TOPIC_MODULE_CMD', '/hardware/module_cmd')
        TOPIC_ALL_FEEDBACK = os.environ.get('ROS_TOPIC_ALL_FEEDBACK', '/hardware/all_feedback')
        TOPIC_ROTATION_OUTPUT = os.environ.get('ROS_TOPIC_ROTATION_OUTPUT', '/hardware/rotation_output')
        TOPIC_SWING_OUTPUT = os.environ.get('ROS_TOPIC_SWING_OUTPUT', '/hardware/swing_output')
        TOPIC_TELESCOPE_OUTPUT = os.environ.get('ROS_TOPIC_TELESCOPE_OUTPUT', '/hardware/telescope_output')

        # ================= 设备ID（从环境变量读取） =================
        self.DEV_ROTATE = int(os.environ.get('DEV_ROTATE', '41'))
        self.DEV_SWING = int(os.environ.get('DEV_SWING', '42'))
        self.DEV_TELES = int(os.environ.get('DEV_TELES', '43'))
        self.DEV_SENSOR = int(os.environ.get('DEV_SENSOR', '49'))

        # ================= 发布者 =================
        self.pub_arm_cmd = rospy.Publisher(TOPIC_ARM_CMD_VEL, IntCmd, queue_size=10)
        self.pub_rot_fb = rospy.Publisher(TOPIC_ROTATION_FEEDBACK, RotationCmd, queue_size=10)
        self.pub_swing_fb = rospy.Publisher(TOPIC_SWING_FEEDBACK, RotationCmd, queue_size=10)
        self.pub_tel_fb = rospy.Publisher(TOPIC_TELESCOPE_FEEDBACK, TelescopicCmd, queue_size=10)
        self.pub_sensor_fb = rospy.Publisher(TOPIC_SENSOR_FEEDBACK, SensorCmd, queue_size=10)
        self.pub_md_fb = rospy.Publisher(TOPIC_MODULE_CMD, IntCmd, queue_size=10)

        # ================= 订阅者 =================
        rospy.Subscriber(TOPIC_ALL_FEEDBACK, Feedback, self.cb_all_fb)
        rospy.Subscriber(TOPIC_ROTATION_OUTPUT, IntCmd, self.cb_rot_out)
        rospy.Subscriber(TOPIC_SWING_OUTPUT, IntCmd, self.cb_swing_out)
        rospy.Subscriber(TOPIC_TELESCOPE_OUTPUT, IntCmd, self.cb_tel_out)

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

        # --- 旋转轴 ---
        if device_id == self.DEV_ROTATE:
            angle = raw_code * self.ENC_TO_DEG
            rospy.loginfo("→ 旋转轴 [%d] 转换: %.4f°" % (device_id, angle))

            m = RotationCmd()
            m.header = Header()
            m.module_id = self.MODULE_ID
            m.device_id = device_id
            m.position = [angle]
            self.pub_rot_fb.publish(m)
            rospy.loginfo("✅ 已发布旋转轴反馈")

        # --- 摆动轴 ---
        elif device_id == self.DEV_SWING:
            angle = raw_code * self.ENC_TO_DEG
            rospy.loginfo("→ 摆动轴 [%d] 转换: %.4f°" % (device_id, angle))

            m = RotationCmd()
            m.header = Header()
            m.module_id = self.MODULE_ID
            m.device_id = device_id
            m.position = [angle]
            self.pub_swing_fb.publish(m)
            rospy.loginfo("✅ 已发布摆动轴反馈")

        # --- 伸缩轴 ---
        elif device_id == self.DEV_TELES:
            length = raw_code * self.ENC_TO_DEG * (self.TELES_MM_PER_REV / 360.0)
            rospy.loginfo("→ 伸缩轴 [%d] 转换: %.4f mm" % (device_id, length))

            m = TelescopicCmd()
            m.header = Header()
            m.module_id = self.MODULE_ID
            m.device_id = device_id
            m.position = [length]
            self.pub_tel_fb.publish(m)
            rospy.loginfo("✅ 已发布伸缩轴反馈")

        # --- 压力传感器 ---
        elif device_id == self.DEV_SENSOR:
            kg = (raw_code / self.PRESSURE_MAX_ADC) * self.PRESSURE_MAX_KG
            N = kg * 9.81
            rospy.loginfo("→ 压力传感器 [%d] 转换: %.4f kg → %.4f N" % (device_id, kg, N))

            m = SensorCmd()
            m.header = Header()
            m.id = 0
            m.module_id = self.MODULE_ID
            m.device_id = device_id
            m.position = [N]
            self.pub_sensor_fb.publish(m)
            rospy.loginfo("✅ 已发布传感器反馈")

        # --- 模块ID 0 ---
        elif device_id == 0:
            rospy.loginfo("→ 模块指令 [0] 透传")
            m = IntCmd()
            m.header = Header()
            m.module_id = module_id
            m.device_id = device_id
            m.position = [0]
            self.pub_md_fb.publish(m)
            rospy.loginfo("✅ 已发布模块反馈")

        # 未知设备
        else:
            rospy.logwarn("⚠️  未知设备ID: %d，已忽略" % device_id)

    # ==========================
    # 轴指令转发日志
    # ==========================
    def cb_rot_out(self, msg):
        rospy.loginfo("[指令转发] 旋转轴 → %s | 编码: %d" % (
            os.environ.get('ROS_TOPIC_ARM_CMD_VEL', '/arm/cmd_vel'),
            msg.position[0]
        ))
        self.pub_arm_cmd.publish(msg)

    def cb_swing_out(self, msg):
        rospy.loginfo("[指令转发] 摆动轴 → %s | 编码: %d" % (
            os.environ.get('ROS_TOPIC_ARM_CMD_VEL', '/arm/cmd_vel'),
            msg.position[0]
        ))
        self.pub_arm_cmd.publish(msg)

    def cb_tel_out(self, msg):
        rospy.loginfo("[指令转发] 伸缩轴 → %s | 编码: %d" % (
            os.environ.get('ROS_TOPIC_ARM_CMD_VEL', '/arm/cmd_vel'),
            msg.position[0]
        ))
        self.pub_arm_cmd.publish(msg)

if __name__ == "__main__":
    try:
        node = FeedbackNode()
        rospy.spin()
    except rospy.ROSInterruptException:
        rospy.loginfo("❌ 反馈节点已停止")
    except Exception as e:
        rospy.logerr("❌ 反馈节点异常: %s" % str(e))
