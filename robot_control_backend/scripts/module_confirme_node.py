#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import rospy
import os
from std_msgs.msg import Header
from robot_control_backend.msg import IntCmd

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

class ModuleConfirm:
    def __init__(self):
        load_env_config()
        rospy.init_node("module_confirme_node")
        rospy.loginfo("✅ 模块确认节点已启动")

        # ================= 模块ID（从环境变量读取） =================
        self.TARGET_MODULE_ID = int(os.environ.get('TARGET_MODULE_ID', '17'))

        # ================= 话题名称（从环境变量读取） =================
        TOPIC_ARM_CMD_VEL = os.environ.get('ROS_TOPIC_ARM_CMD_VEL', '/arm/cmd_vel')
        TOPIC_MODULE_CONFIRM_SUCCESS = os.environ.get('ROS_TOPIC_MODULE_CONFIRM_SUCCESS', '/control/module_confirm_success')
        TOPIC_MODULE_CMD = os.environ.get('ROS_TOPIC_MODULE_CMD', '/control/module_cmd')
        TOPIC_HARDWARE_MODULE_CMD = os.environ.get('ROS_TOPIC_MODULE_CMD', '/hardware/module_cmd')

        # ================= 发布者 =================
        self.pub_cmd = rospy.Publisher(TOPIC_ARM_CMD_VEL, IntCmd, queue_size=10)
        self.pub_success = rospy.Publisher(TOPIC_MODULE_CONFIRM_SUCCESS, IntCmd, queue_size=10)

        # ================= 订阅者 =================
        rospy.Subscriber(TOPIC_MODULE_CMD, IntCmd, self.cb_upper_cmd)
        rospy.Subscriber(TOPIC_HARDWARE_MODULE_CMD, IntCmd, self.cb_hardware_feedback)

        self.original_module_id = None
        self.first_position = None

    # -------------------------------------------------------------------------
    # 上位机指令回调
    # -------------------------------------------------------------------------
    def cb_upper_cmd(self, msg):
        self.original_module_id = msg.module_id
        device_id = msg.device_id
        self.first_position = 0

        if device_id == 0:
            m = IntCmd()
            m.header = Header()
            m.header.stamp = rospy.Time.now()
            m.module_id = self.original_module_id
            m.device_id = 0
            m.position = [self.first_position]
            self.pub_cmd.publish(m)
            rospy.loginfo("[第一次下发] 模块确认 → module_id=%d" % self.original_module_id)

    # -------------------------------------------------------------------------
    # 硬件反馈回调（核心比对）
    # -------------------------------------------------------------------------
    def cb_hardware_feedback(self, msg):
        if self.original_module_id is None:
            rospy.loginfo("module_id is none")
            return

        feedback_module_id = msg.module_id
        if feedback_module_id == self.original_module_id:
            rospy.loginfo("[比对成功] 硬件返回 ID 匹配: %d" % feedback_module_id)

            # 二次下发（去重）
            second_position = 1
            m = IntCmd()
            m.header = Header()
            m.header.stamp = rospy.Time.now()
            m.module_id = self.original_module_id
            m.device_id = 0
            m.position = [second_position]
            self.pub_cmd.publish(m)
            rospy.loginfo("[二次下发] 确认指令已发送")

            success_msg = IntCmd()
            success_msg.header = Header()
            success_msg.header.stamp = rospy.Time.now()
            success_msg.module_id = self.original_module_id
            success_msg.device_id = 0
            success_msg.position = [100]  # 100 = 成功信号
            self.pub_success.publish(success_msg)
            rospy.loginfo("[成功] 已向前端发送确认信号")

            # 重置
            self.original_module_id = None
            self.first_position = None

    def run(self):
        rospy.spin()

if __name__ == "__main__":
    try:
        node = ModuleConfirm()
        node.run()
    except rospy.ROSInterruptException:
        rospy.loginfo("❌ 模块确认节点停止")
    except Exception as e:
        rospy.logerr("❌ 模块节点异常: %s" % str(e))
