#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
控制节点：接收逆解三话题 → 旋转→等8s→摆动→等8s→伸缩 时序转发至 _sequenced 话题
第二套功能：接收前端调节命令，直接转发至 _sequenced 话题
device_id 新规则：Arm1:33/34/35, Arm2:65/66/67, Arm3:97/98/99
"""

import rospy
import threading
from collections import defaultdict
from std_msgs.msg import Header
from robot_control_backend.msg import RotationCmd, SwingCmd, TelescopicCmd

class ArmSequenceController:
    def __init__(self):
        rospy.init_node("arm_sequence_controller")

        # ---------- 输出话题 ----------
        self.pub_rot_seq  = rospy.Publisher("/control/kinematics_rotation_cmd_sequenced",   RotationCmd,   queue_size=10)
        self.pub_sw_seq   = rospy.Publisher("/control/kinematics_swing_cmd_sequenced",      SwingCmd,      queue_size=10)
        self.pub_tel_seq  = rospy.Publisher("/control/kinematics_telescopic_cmd_sequenced", TelescopicCmd, queue_size=10)

        self.pub_adj_rot  = rospy.Publisher("/control/adjust_rotation_cmd_sequenced",   RotationCmd,   queue_size=10)
        self.pub_adj_sw   = rospy.Publisher("/control/adjust_swing_cmd_sequenced",      SwingCmd,      queue_size=10)
        self.pub_adj_tel  = rospy.Publisher("/control/adjust_telescopic_cmd_sequenced", TelescopicCmd, queue_size=10)

        # ---------- 指令缓冲 ----------
        self.buffer_lock = threading.Lock()
        self.cmd_buffer = defaultdict(lambda: defaultdict(dict))
        self.ready_queue = []
        self.seq_thread = threading.Thread(target=self._sequence_worker)
        self.seq_thread.daemon = True
        self.seq_thread.start()

        # ---------- 订阅逆运算原始话题 ----------
        rospy.Subscriber("/control/kinematics_rotation_cmd",   RotationCmd,   self.cb_rotation)
        rospy.Subscriber("/control/kinematics_swing_cmd",      SwingCmd,      self.cb_swing)
        rospy.Subscriber("/control/kinematics_telescopic_cmd", TelescopicCmd, self.cb_telescopic)

        # ---------- 第二套功能：前端调节 ----------
        rospy.Subscriber("/control/adjust_rotation_cmd", RotationCmd, self.cb_adjust)

        rospy.loginfo("🔧 控制节点启动（新 device_id 规则: 33-35, 65-67, 97-99）")

    # ---------- device_id 解析（新规则）----------
    def _parse_device(self, device_id):
        """
        新规则：Arm1 基址32, Arm2 基址64, Arm3 基址96
        返回 (arm_index 0~2, joint_name)
        """
        base = 32
        arm_idx = (device_id - 1) // base - 1       # 33->0, 65->1, 97->2
        joint_code = (device_id - 1) % base + 1     # 33%32=1, 34%32=2, 35%32=3
        joint_map = {1: "rotate", 2: "swing", 3: "extend"}
        return arm_idx, joint_map[joint_code]

    # ---------- 逆解收集 ----------
    def cb_rotation(self, msg):
        self._store_cmd(msg, "rotate")

    def cb_swing(self, msg):
        self._store_cmd(msg, "swing")

    def cb_telescopic(self, msg):
        self._store_cmd(msg, "extend")

    def _store_cmd(self, msg, joint_name):
        arm_idx, _ = self._parse_device(msg.device_id)
        mid = msg.module_id
        with self.buffer_lock:
            self.cmd_buffer[mid][arm_idx][joint_name] = msg
            if len(self.cmd_buffer[mid]) >= 3 and all(
                len(self.cmd_buffer[mid].get(i, {})) == 3 for i in range(3)
            ):
                pkg = {
                    "module_id": mid,
                    "arms": {i: self.cmd_buffer[mid][i].copy() for i in sorted(self.cmd_buffer[mid].keys())}
                }
                self.ready_queue.append(pkg)
                del self.cmd_buffer[mid]
                rospy.loginfo(f"✅ 模块{mid} 指令集齐，加入队列")

    # ---------- 顺序执行线程 ----------
    def _sequence_worker(self):
        while not rospy.is_shutdown():
            if self.ready_queue:
                with self.buffer_lock:
                    if self.ready_queue:
                        task = self.ready_queue.pop(0)
                    else:
                        task = None
                if task:
                    self._execute_module(task)
            else:
                rospy.sleep(0.1)

    def _execute_module(self, task):
        mid = task["module_id"]
        arms = task["arms"]
        try:
            # 旋转阶段（同时发布）
            for arm_idx in sorted(arms.keys()):
                msg = arms[arm_idx]["rotate"]
                msg.header.stamp = rospy.Time.now()
                self.pub_rot_seq.publish(msg)
                rospy.loginfo(f"🚀 模块{mid} Arm{arm_idx+1} 旋转增量 {msg.position[0]:.2f}°")
            rospy.sleep(8.0)

            # 摆动阶段
            for arm_idx in sorted(arms.keys()):
                msg = arms[arm_idx]["swing"]
                msg.header.stamp = rospy.Time.now()
                self.pub_sw_seq.publish(msg)
                rospy.loginfo(f"🚀 模块{mid} Arm{arm_idx+1} 摆动增量 {msg.position[0]:.2f}°")
            rospy.sleep(8.0)

            # 伸缩阶段
            for arm_idx in sorted(arms.keys()):
                msg = arms[arm_idx]["extend"]
                msg.header.stamp = rospy.Time.now()
                self.pub_tel_seq.publish(msg)
                rospy.loginfo(f"🚀 模块{mid} Arm{arm_idx+1} 伸缩增量 {msg.position[0]:.1f}mm")
            # 功能节点收到伸缩指令后自行管理压力传感器
        except Exception as e:
            rospy.logerr(f"模块{mid} 顺序执行异常: {e}")

    # ---------- 第二套：前端调节（已修正）----------
    def cb_adjust(self, msg):
        try:
            # 使用统一的 device_id 解析，与新规则完全一致
            arm_idx, joint_name = self._parse_device(msg.device_id)
            if arm_idx < 0 or arm_idx > 2:
                rospy.logerr(f"device_id {msg.device_id} 非法")
                return

            msg.header.stamp = rospy.Time.now()
            if joint_name == "rotate":
                self.pub_adj_rot.publish(msg)
                rospy.loginfo(f"🎯 前端调节 Arm{arm_idx+1} 旋转 -> {msg.position[0]:.2f}°")
            elif joint_name == "swing":
                self.pub_adj_sw.publish(msg)
                rospy.loginfo(f"🎯 前端调节 Arm{arm_idx+1} 摆动 -> {msg.position[0]:.2f}°")
            elif joint_name == "extend":
                self.pub_adj_tel.publish(msg)
                rospy.loginfo(f"🎯 前端调节 Arm{arm_idx+1} 伸缩 -> {msg.position[0]:.2f}mm")
            else:
                rospy.logerr(f"未知关节类型 {joint_name}")
        except Exception as e:
            rospy.logerr(f"前端调节异常: {e}")

if __name__ == "__main__":
    try:
        controller = ArmSequenceController()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass