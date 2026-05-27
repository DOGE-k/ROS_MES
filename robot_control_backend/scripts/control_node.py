#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import rospy
import os
import threading
from collections import defaultdict
from std_msgs.msg import Header
from robot_control_backend.msg import RotationCmd, SwingCmd, TelescopicCmd, IntCmd

def load_env_config():
    """加载 .env 配置到环境变量（控制节点也使用）"""
    env_path = os.path.join(os.path.dirname(__file__), '../rob_arm.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    os.environ[key] = value
        rospy.loginfo("✅ 控制节点已从 rob_arm.env 加载配置")

class ArmSequenceController:
    def __init__(self):
        load_env_config()   # 先加载配置
        rospy.init_node("arm_sequence_controller")

        # ---------- 输出话题（发布给功能节点，复用 .env 中已定义的变量）----------
        self.pub_rot_seq = rospy.Publisher(
            os.environ.get('ROS_TOPIC_KINEMATICS_ROTATION_CMD_SEQ', '/control/kinematics_rotation_cmd_sequenced'),
            RotationCmd, queue_size=10)
        self.pub_sw_seq  = rospy.Publisher(
            os.environ.get('ROS_TOPIC_KINEMATICS_SWING_CMD_SEQ', '/control/kinematics_swing_cmd_sequenced'),
            SwingCmd, queue_size=10)
        self.pub_tel_seq = rospy.Publisher(
            os.environ.get('ROS_TOPIC_KINEMATICS_TELESCOPIC_CMD_SEQ', '/control/kinematics_telescopic_cmd_sequenced'),
            TelescopicCmd, queue_size=10)

        # 压力传感器触发话题（发布）
        self.pub_sensor_trigger = rospy.Publisher(
            os.environ.get('ROS_TOPIC_SENSOR_CMD', '/control/sensor_cmd'),
            IntCmd, queue_size=10)

        # ---------- 指令缓冲 ----------
        self.buffer_lock = threading.Lock()
        self.cmd_buffer = defaultdict(lambda: defaultdict(dict))
        self.ready_queue = []
        self.seq_thread = threading.Thread(target=self._sequence_worker)
        self.seq_thread.daemon = True
        self.seq_thread.start()

        # 压力传感器定时器
        self.timers_lock = threading.Lock()
        self.adjust_timers = {}

        # ---------- 订阅逆运算原始话题（从 .env 读取）----------
        rospy.Subscriber(
            os.environ.get('ROS_TOPIC_KINEMATICS_ROTATION_CMD_INPUT', '/control/kinematics_rotation_cmd'),
            RotationCmd, self.cb_rotation)
        rospy.Subscriber(
            os.environ.get('ROS_TOPIC_KINEMATICS_SWING_CMD_INPUT', '/control/kinematics_swing_cmd'),
            SwingCmd, self.cb_swing)
        rospy.Subscriber(
            os.environ.get('ROS_TOPIC_KINEMATICS_TELESCOPIC_CMD_INPUT', '/control/kinematics_telescopic_cmd'),
            TelescopicCmd, self.cb_telescopic)

        # ---------- 第二套功能：订阅前端微调话题 ----------
        rospy.Subscriber(
            os.environ.get('ROS_TOPIC_ADJUST_ROTATION_CMD_INPUT', '/control/adjust_rotation_cmd'),
            RotationCmd, self.cb_adjust_rotation)
        rospy.Subscriber(
            os.environ.get('ROS_TOPIC_ADJUST_SWING_CMD_INPUT', '/control/adjust_swing_cmd'),
            SwingCmd, self.cb_adjust_swing)
        rospy.Subscriber(
            os.environ.get('ROS_TOPIC_ADJUST_TELESCOPIC_CMD_INPUT', '/control/adjust_telescopic_cmd'),
            TelescopicCmd, self.cb_adjust_telescopic)

        rospy.loginfo("🔧 控制节点启动（话题全部从 .env 读取）")

    # ---------- device_id 解析 ----------
    def _parse_device(self, device_id):
        base = 32
        arm_idx = (device_id - 1) // base - 1
        joint_code = (device_id - 1) % base + 1
        joint_map = {1: "rotate", 2: "swing", 3: "extend"}
        return arm_idx, joint_map[joint_code]

    # ---------- 压力传感器触发管理 ----------
    def _send_pressure_trigger(self, module_id):
        trigger = IntCmd()
        trigger.header = Header(stamp=rospy.Time.now())
        trigger.module_id = module_id
        trigger.device_id = 0
        trigger.position = [0]
        self.pub_sensor_trigger.publish(trigger)
        rospy.loginfo(f"📡 已发送压力传感器触发消息 (module={module_id})")

    def _schedule_pressure(self, module_id):
        with self.timers_lock:
            if module_id in self.adjust_timers:
                self.adjust_timers[module_id].shutdown()
            new_timer = rospy.Timer(
                rospy.Duration(7.0),
                lambda event, mid=module_id: self._on_pressure_timeout(mid),
                oneshot=True
            )
            self.adjust_timers[module_id] = new_timer
            rospy.loginfo(f"⏳ 模块{module_id} 压力传感器定时器已启动/重置 (7s)")

    def _on_pressure_timeout(self, module_id):
        with self.timers_lock:
            if module_id in self.adjust_timers:
                del self.adjust_timers[module_id]
        self._send_pressure_trigger(module_id)

    # ================= 第一套功能（逆解，带话题过滤）=================
    def cb_rotation(self, msg):
        expected_topic = os.environ.get('ROS_TOPIC_KINEMATICS_ROTATION_CMD_INPUT', '/control/kinematics_rotation_cmd')
        if msg._connection_header.get('topic', '') != expected_topic:
            return
        self._store_cmd(msg, "rotate")

    def cb_swing(self, msg):
        expected_topic = os.environ.get('ROS_TOPIC_KINEMATICS_SWING_CMD_INPUT', '/control/kinematics_swing_cmd')
        if msg._connection_header.get('topic', '') != expected_topic:
            return
        self._store_cmd(msg, "swing")

    def cb_telescopic(self, msg):
        expected_topic = os.environ.get('ROS_TOPIC_KINEMATICS_TELESCOPIC_CMD_INPUT', '/control/kinematics_telescopic_cmd')
        if msg._connection_header.get('topic', '') != expected_topic:
            return
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
            for arm_idx in sorted(arms.keys()):
                msg = arms[arm_idx]["rotate"]
                msg.header.stamp = rospy.Time.now()
                self.pub_rot_seq.publish(msg)
                rospy.loginfo(f"[逆运算] 🚀 模块{mid} Arm{arm_idx+1} 旋转增量 {msg.position[0]:.2f}°")
            rospy.sleep(8.0)

            for arm_idx in sorted(arms.keys()):
                msg = arms[arm_idx]["swing"]
                msg.header.stamp = rospy.Time.now()
                self.pub_sw_seq.publish(msg)
                rospy.loginfo(f"[逆运算] 🚀 模块{mid} Arm{arm_idx+1} 摆动增量 {msg.position[0]:.2f}°")
            rospy.sleep(8.0)

            for arm_idx in sorted(arms.keys()):
                msg = arms[arm_idx]["extend"]
                msg.header.stamp = rospy.Time.now()
                self.pub_tel_seq.publish(msg)
                rospy.loginfo(f"[逆运算] 🚀 模块{mid} Arm{arm_idx+1} 伸缩增量 {msg.position[0]:.1f}mm")

            self._schedule_pressure(mid)
        except Exception as e:
            rospy.logerr(f"模块{mid} 顺序执行异常: {e}")

    # ================= 第二套功能（前端微调）=================
    def cb_adjust_rotation(self, msg):
        expected_topic = os.environ.get('ROS_TOPIC_ADJUST_ROTATION_CMD_INPUT', '/control/adjust_rotation_cmd')
        if msg._connection_header.get('topic', '') != expected_topic:
            return
        self._handle_adjust(msg, "rotate")

    def cb_adjust_swing(self, msg):
        expected_topic = os.environ.get('ROS_TOPIC_ADJUST_SWING_CMD_INPUT', '/control/adjust_swing_cmd')
        if msg._connection_header.get('topic', '') != expected_topic:
            return
        self._handle_adjust(msg, "swing")

    def cb_adjust_telescopic(self, msg):
        expected_topic = os.environ.get('ROS_TOPIC_ADJUST_TELESCOPIC_CMD_INPUT', '/control/adjust_telescopic_cmd')
        if msg._connection_header.get('topic', '') != expected_topic:
            return
        self._handle_adjust(msg, "extend")

    def _handle_adjust(self, msg, joint_name):
        try:
            device_id = msg.device_id
            arm_idx, _ = self._parse_device(device_id)
            if arm_idx < 0 or arm_idx > 2:
                rospy.logerr(f"device_id {device_id} 非法")
                return

            module_id = msg.module_id
            msg.header.stamp = rospy.Time.now()

            if joint_name == "rotate":
                self.pub_rot_seq.publish(msg)
            elif joint_name == "swing":
                self.pub_sw_seq.publish(msg)
            elif joint_name == "extend":
                self.pub_tel_seq.publish(msg)
            else:
                rospy.logerr(f"未知关节类型 {joint_name}")
                return

            rospy.loginfo(f"[微调] 🎯 Arm{arm_idx+1} {joint_name} -> {msg.position[0]:.2f}")
            self._schedule_pressure(module_id)
        except Exception as e:
            rospy.logerr(f"前端调节异常: {e}")

if __name__ == "__main__":
    try:
        controller = ArmSequenceController()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass