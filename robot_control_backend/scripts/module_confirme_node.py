#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import rospy
from std_msgs.msg import Header
from robot_control_backend.msg import Kinematics

class ModuleConfirm:
    def __init__(self):
        rospy.init_node("module_confirme_node")
        rospy.loginfo("✅ 模块确认节点已启动")

        # ================= 发布者 =================
        self.pub_cmd = rospy.Publisher("/arm/cmd_vel", Kinematics, queue_size=10)
        self.pub_success = rospy.Publisher("/control/module_confirm_success", Kinematics, queue_size=10)

        # ================= 订阅者 =================
        rospy.Subscriber("/control/module_cmd", Kinematics, self.cb_upper_cmd)
        
        # ==========================
        # ✅ 修复问题2：消息类型改为 Kinematics
        # ==========================
        rospy.Subscriber("/hardware/module_cmd", Kinematics, self.cb_hardware_feedback)

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
            m = Kinematics()
            m.header = Header()
            m.header.stamp = rospy.Time.now()
            m.module_id = self.original_module_id
            m.device_id = 0
            m.position = [self.first_position]
            self.pub_cmd.publish(m)
            rospy.loginfo(f"[第一次下发] 模块确认 → module_id={self.original_module_id}")

    # -------------------------------------------------------------------------
    # 硬件反馈回调（核心比对）
    # -------------------------------------------------------------------------
    def cb_hardware_feedback(self, msg):
        if self.original_module_id is None:
            return

        feedback_module_id = msg.module_id
        if feedback_module_id == self.original_module_id:
            rospy.loginfo(f"[比对成功] 硬件返回 ID 匹配: {feedback_module_id}")

            # 二次下发（去重）
            second_position = 1
            m = Kinematics()
            m.header = Header()
            m.header.stamp = rospy.Time.now()
            m.module_id = self.original_module_id
            m.device_id = 0
            m.position = [second_position]
            self.pub_cmd.publish(m)
            rospy.loginfo(f"[二次下发] 确认指令已发送")

            success_msg = Kinematics()
            success_msg.header = Header()
            success_msg.header.stamp = rospy.Time.now()
            success_msg.module_id = self.original_module_id
            success_msg.device_id = 0
            success_msg.position = [100.0]  # 100 = 成功信号
            self.pub_success.publish(success_msg)
            rospy.loginfo(f"[成功] 已向前端发送确认信号")

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
        rospy.logerr(f"❌ 模块节点异常: {str(e)}")