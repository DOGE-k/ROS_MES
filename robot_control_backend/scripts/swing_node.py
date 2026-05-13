#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import rospy
import os
from std_msgs.msg import Header
from robot_control_backend.msg import SwingCmd, IntCmd

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

## --------------------摆动轴功能节点----------------
class SwingSimple:
    def __init__(self):
        load_env_config()
        rospy.init_node("swing_simple_node")
        rospy.loginfo("✅ 摆动轴节点启动")

        # --- 核心参数（从环境变量读取） ---
        self.DEGREE_PER_TICK = float(os.environ.get('DEGREE_PER_TICK', '0.01248'))
        self.MODULE_ID = int(os.environ.get('MODULE_ID', '17'))
        self.DEV_SWING_CONTROL = int(os.environ.get('DEV_SWING_CONTROL', '34'))
        self.DEV_SENSOR = int(os.environ.get('DEV_SENSOR', '49'))

        # 编码器限位（从环境变量读取）
        self.ENC_MID = int(os.environ.get('ENC_MID', '15000'))
        self.ENC_MIN = int(os.environ.get('ENC_MIN', '580'))
        self.ENC_MAX = int(os.environ.get('ENC_MAX', '29420'))

        # 话题名称（从环境变量读取）
        TOPIC_ADJUST_SWING_CMD = os.environ.get('ROS_TOPIC_ADJUST_SWING_CMD', '/control/adjust_swing_cmd')
        TOPIC_KINEMATICS_SWING_CMD = os.environ.get('ROS_TOPIC_KINEMATICS_SWING_CMD', '/control/kinematics_swing_cmd')
        TOPIC_SWING_FEEDBACK = os.environ.get('ROS_TOPIC_SWING_FEEDBACK', '/hardware/swing_feedback')
        TOPIC_SWING_OUTPUT = os.environ.get('ROS_TOPIC_SWING_OUTPUT', '/hardware/swing_output')
        TOPIC_SENSOR_CMD = os.environ.get('ROS_TOPIC_SENSOR_CMD', '/control/sensor_cmd')

        # 核心变量
        self.target_delta_deg = 0.0
        self.current_swing_deg = 0.0
        self.target_reach_deg = 0.0

        # 订阅双指令
        rospy.Subscriber(TOPIC_ADJUST_SWING_CMD, SwingCmd, self.cmd_callback)
        rospy.Subscriber(TOPIC_KINEMATICS_SWING_CMD, SwingCmd, self.cmd_callback)
        rospy.Subscriber(TOPIC_SWING_FEEDBACK, SwingCmd, self.feedback_callback)

        # 发布输出
        self.output_pub = rospy.Publisher(TOPIC_SWING_OUTPUT, IntCmd, queue_size=10)
        self.sensor_cmd = rospy.Publisher(TOPIC_SENSOR_CMD, IntCmd, queue_size=10)

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
        int_cmd_msg.module_id = self.MODULE_ID
        int_cmd_msg.device_id = self.DEV_SWING_CONTROL
        int_cmd_msg.position = [target_tick]

        sen_cmd_msg = IntCmd()
        sen_cmd_msg.header = Header()
        sen_cmd_msg.header.stamp = rospy.Time.now()
        sen_cmd_msg.module_id = self.MODULE_ID
        sen_cmd_msg.device_id = self.DEV_SENSOR
        sen_cmd_msg.position = 0

        # 只发一次！
        self.output_pub.publish(int_cmd_msg)
        self.sensor_cmd.publish(sen_cmd_msg)

        # 日志
        cmd_topic = msg._connection_header.get('topic', '未知话题')
        if cmd_topic == os.environ.get('ROS_TOPIC_ADJUST_SWING_CMD', '/control/adjust_swing_cmd'):
            rospy.loginfo("摆动轴微调：+%.4f° → 下发编码：%d" % (self.target_delta_deg, target_tick))
        elif cmd_topic == os.environ.get('ROS_TOPIC_KINEMATICS_SWING_CMD', '/control/kinematics_swing_cmd'):
            rospy.loginfo("摆动轴运动学：+%.4f° → 下发编码：%d" % (self.target_delta_deg, target_tick))

    def feedback_callback(self, msg):
        """仅监控，不发指令"""
        if msg.device_id == self.DEV_SWING_CONTROL or msg.device_id == int(os.environ.get('DEV_SWING', '42')):
            self.current_swing_deg = msg.position[0]

if __name__ == "__main__":
    try:
        node = SwingSimple()
        rospy.spin()  # 无循环，纯事件驱动
    except rospy.ROSInterruptException:
        rospy.loginfo("摆动轴节点停止")
    except Exception as e:
        rospy.logerr("摆动轴异常：%s" % str(e))
