#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os

import rospy
from std_msgs.msg import Header

from robot_control_backend.msg import (
    RotationCmd,
    SwingCmd,
    TelescopicCmd,
    SensorCmd,
    Feedback,
    IntCmd,
)


def load_env_config():
    env_path = os.path.join(os.path.dirname(__file__), '../rob_arm.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value
        rospy.loginfo("✅ feedback_node 已从 rob_arm.env 加载配置")


class FeedbackNode:
    def __init__(self):
        load_env_config()
        rospy.init_node("feedback_node")

        # V2：位置量为绝对角度（0.01°），不再需要编码器换算系数
        self.angle_scale = 0.01              # 0.01° → 度
        self.g_to_n = float(os.environ['PRESSURE_G_TO_N'])
        # V2：module_id 不做静态配置，全部从接收消息透传（上行源自 CAN 帧 SEG 位域）

        # ---------- 话题（只读 rob_arm.env，无硬编码默认值）----------
        topic_arm_cmd = os.environ['ROS_TOPIC_ARM_CMD_VEL']
        topic_rot_fb = os.environ['ROS_TOPIC_ROTATION_FEEDBACK']
        topic_sw_fb = os.environ['ROS_TOPIC_SWING_FEEDBACK']
        topic_tel_fb = os.environ['ROS_TOPIC_TELESCOPE_FEEDBACK']
        topic_sensor_fb = os.environ['ROS_TOPIC_SENSOR_FEEDBACK']
        topic_sensor_raw = os.environ['ROS_TOPIC_SENSOR_RAW']
        topic_rot_out = os.environ['ROS_TOPIC_ROTATION_OUTPUT']
        topic_sw_out = os.environ['ROS_TOPIC_SWING_OUTPUT']
        topic_tel_out = os.environ['ROS_TOPIC_TELESCOPE_OUTPUT']
        topic_can_rot = os.environ['ROS_TOPIC_CAN_ROTATION_RAW']
        topic_can_sw = os.environ['ROS_TOPIC_CAN_SWING_RAW']
        topic_can_tel = os.environ['ROS_TOPIC_CAN_TELESCOPIC_RAW']
        topic_can_pressure = os.environ['ROS_TOPIC_CAN_PRESSURE_RAW']

        self.pub_arm_cmd = rospy.Publisher(topic_arm_cmd, IntCmd, queue_size=10)
        self.pub_rot_fb = rospy.Publisher(topic_rot_fb, RotationCmd, queue_size=10)
        self.pub_sw_fb = rospy.Publisher(topic_sw_fb, SwingCmd, queue_size=10)
        self.pub_tel_fb = rospy.Publisher(topic_tel_fb, TelescopicCmd, queue_size=10)
        self.pub_sensor_raw = rospy.Publisher(topic_sensor_raw, SensorCmd, queue_size=10)
        self.pub_sensor_fb = rospy.Publisher(topic_sensor_fb, SensorCmd, queue_size=10)

        rospy.Subscriber(topic_can_rot, Feedback, self._cb_rotation_raw)
        rospy.Subscriber(topic_can_sw, Feedback, self._cb_swing_raw)
        rospy.Subscriber(topic_can_tel, Feedback, self._cb_telescopic_raw)
        rospy.Subscriber(topic_can_pressure, SensorCmd, self._cb_pressure_raw)

        rospy.Subscriber(topic_rot_out, IntCmd, self._cb_forward)
        rospy.Subscriber(topic_sw_out, IntCmd, self._cb_forward)
        rospy.Subscriber(topic_tel_out, IntCmd, self._cb_forward)

        rospy.loginfo("✅ 反馈节点 V2 启动（0.01°→° 角度换算 + 指令汇聚）")

    # ====================== 角度 0.01° → 度 ======================
    def _cb_rotation_raw(self, msg):
        angle = int(msg.position[0]) * self.angle_scale
        m = RotationCmd(header=Header(stamp=rospy.Time.now()),
                        module_id=msg.module_id, device_id=msg.device_id, position=[angle])
        self.pub_rot_fb.publish(m)

    def _cb_swing_raw(self, msg):
        angle = int(msg.position[0]) * self.angle_scale
        m = SwingCmd(header=Header(stamp=rospy.Time.now()),
                     module_id=msg.module_id, device_id=msg.device_id, position=[angle])
        self.pub_sw_fb.publish(m)

    def _cb_telescopic_raw(self, msg):
        """伸缩轴反馈也是角度（0.01°），换算为度后发布；mm↔角度换算由 telescopic_node/kinematics_node 自行完成"""
        angle = int(msg.position[0]) * self.angle_scale
        m = TelescopicCmd(header=Header(stamp=rospy.Time.now()),
                          module_id=msg.module_id, device_id=msg.device_id, position=[angle])
        self.pub_tel_fb.publish(m)

    def _cb_pressure_raw(self, msg):
        """压力 PressureRaw → N（PressureRaw 单位由嵌入式侧标定，此处按克→牛换算）"""
        raw = msg.position[0] if msg.position else 0.0
        newton = raw / 1000.0 * self.g_to_n
        for pub in (self.pub_sensor_raw, self.pub_sensor_fb):
            m = SensorCmd(header=Header(stamp=rospy.Time.now()), id=0,
                          module_id=msg.module_id, device_id=msg.device_id, position=[newton])
            pub.publish(m)

    # ====================== 指令汇聚转发 ======================
    def _cb_forward(self, msg):
        self.pub_arm_cmd.publish(msg)


if __name__ == "__main__":
    try:
        node = FeedbackNode()
        rospy.spin()
    except rospy.ROSInterruptException:
        rospy.loginfo("❌ 反馈节点已停止")
    except Exception as e:
        rospy.logerr("❌ 反馈节点异常: %s" % str(e))
