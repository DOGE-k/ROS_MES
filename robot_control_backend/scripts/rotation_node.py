#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import rospy
import os
from std_msgs.msg import Header
from robot_control_backend.msg import RotationCmd, IntCmd

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

## -------旋转轴功能节点-------------
class RotationSimple:
    def __init__(self):
        load_env_config()
        rospy.init_node("rotation_simple_node")
        rospy.loginfo("旋转轴节点启动")

        # 编码器换算系数（从环境变量读取）
        self.DEGREE_PER_TICK = float(os.environ.get('DEGREE_PER_TICK', '0.01248'))
        self.MODULE_ID = int(os.environ.get('MODULE_ID', '17'))
        self.DEV_ROTATE_CONTROL = int(os.environ.get('DEV_ROTATE_CONTROL', '33'))
        self.DEV_SENSOR = int(os.environ.get('DEV_SENSOR', '49'))

        # ================== 编码器限位（从环境变量读取） ==================
        self.ENC_MID = int(os.environ.get('ENC_MID', '15000'))
        self.ENC_MIN = int(os.environ.get('ENC_MIN', '580'))
        self.ENC_MAX = int(os.environ.get('ENC_MAX', '29420'))

        # ================== 话题名称（从环境变量读取） ==================
        TOPIC_ADJUST_ROTATION_CMD = os.environ.get('ROS_TOPIC_ADJUST_ROTATION_CMD', '/control/adjust_rotation_cmd')
        TOPIC_KINEMATICS_ROTATION_CMD = os.environ.get('ROS_TOPIC_KINEMATICS_ROTATION_CMD', '/control/kinematics_rotation_cmd')
        TOPIC_ROTATION_FEEDBACK = os.environ.get('ROS_TOPIC_ROTATION_FEEDBACK', '/hardware/rotation_feedback')
        TOPIC_ROTATION_OUTPUT = os.environ.get('ROS_TOPIC_ROTATION_OUTPUT', '/hardware/rotation_output')
        TOPIC_SENSOR_CMD = os.environ.get('ROS_TOPIC_SENSOR_CMD', '/control/sensor_cmd')

        # 核心变量
        self.has_new_command = False    # 是否有新指令需要下发
        self.target_delta_deg = 0.0     # 增量角度指令
        self.current_angle_deg = 0.0    # 当前实际角度
        self.target_reach_deg = 0.0     # 目标角度

        # 订阅双指令话题
        rospy.Subscriber(TOPIC_ADJUST_ROTATION_CMD, RotationCmd, self.cmd_callback)
        rospy.Subscriber(TOPIC_KINEMATICS_ROTATION_CMD, RotationCmd, self.cmd_callback)
        rospy.Subscriber(TOPIC_ROTATION_FEEDBACK, RotationCmd, self.feedback_callback)

        # 发布输出
        self.output_pub = rospy.Publisher(TOPIC_ROTATION_OUTPUT, IntCmd, queue_size=10)
        self.sensor_cmd = rospy.Publisher(TOPIC_SENSOR_CMD, IntCmd, queue_size=10)

    def cmd_callback(self, msg):
        """接收增量指令 → 计算目标 → 只发一次命令"""
        self.target_delta_deg = msg.position[0]
        self.target_reach_deg = self.current_angle_deg + self.target_delta_deg

        # ================== 角度 → 编码器编码（带限位） ==================
        target_tick = self.ENC_MID + int(round(self.target_reach_deg / self.DEGREE_PER_TICK))
        target_tick = max(self.ENC_MIN, min(target_tick, self.ENC_MAX))

        # ================== 构建消息并发布（只发一次） ==================
        int_cmd_msg = IntCmd()
        int_cmd_msg.header = Header()
        int_cmd_msg.header.stamp = rospy.Time.now()
        int_cmd_msg.module_id = self.MODULE_ID
        int_cmd_msg.device_id = self.DEV_ROTATE_CONTROL
        int_cmd_msg.position = [target_tick]

        sen_cmd_msg = IntCmd()
        sen_cmd_msg.header = Header()
        sen_cmd_msg.header.stamp = rospy.Time.now()
        sen_cmd_msg.module_id = self.MODULE_ID
        sen_cmd_msg.device_id = self.DEV_SENSOR
        sen_cmd_msg.position = 0

        self.output_pub.publish(int_cmd_msg)
        self.sensor_cmd.publish(sen_cmd_msg)

        # 日志
        cmd_topic = msg._connection_header.get('topic', '未知话题')
        if cmd_topic == os.environ.get('ROS_TOPIC_ADJUST_ROTATION_CMD', '/control/adjust_rotation_cmd'):
            rospy.loginfo("旋转轴微调：+%.4f° → 下发编码：%d" % (self.target_delta_deg, target_tick))
        elif cmd_topic == os.environ.get('ROS_TOPIC_KINEMATICS_ROTATION_CMD', '/control/kinematics_rotation_cmd'):
            rospy.loginfo("旋转轴运动学：+%.4f° → 下发编码：%d" % (self.target_delta_deg, target_tick))

    def feedback_callback(self, msg):
        """仅更新当前角度，监控状态"""
        if msg.device_id == self.DEV_ROTATE_CONTROL or msg.device_id == int(os.environ.get('DEV_ROTATE', '41')):
            self.current_angle_deg = msg.position[0]

if __name__ == "__main__":
    try:
        node = RotationSimple()
        rospy.spin()  
    except rospy.ROSInterruptException:
        rospy.loginfo("旋转轴节点停止")
    except Exception as e:
        rospy.logerr("旋转轴异常：%s" % str(e))
