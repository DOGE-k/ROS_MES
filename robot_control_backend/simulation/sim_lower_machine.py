#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
下位机（STM32 + CAN）模拟节点 —— 仅用于无硬件联调

替代 hardware_node.py 的 CAN 桥接层，在 ROS 话题层模拟下位机行为：
  订阅 /arm/cmd_vel (IntCmd)            ← feedback_node/softstop/sensor 汇聚后的下行指令
  订阅 /control/seg_assign (SegAssign)  ← 模块确认节点分配 SEG
  发布 /hardware/can/rotation_raw       ← 旋转轴 0.01° 绝对位置（Feedback）
  发布 /hardware/can/swing_raw          ← 摆动轴 0.01° 绝对位置（Feedback）
  发布 /hardware/can/telescopic_raw     ← 伸缩轴 0.01mm 绝对位置（Feedback）
  发布 /hardware/can/pressure_raw       ← 压力原始值（克，SensorCmd）
  发布 /hardware/gyroscope_feedback     ← IMU 原始数据（GyroFeedback）
  发布 /hardware/uid_announce           ← 未编号宣告（UidAnnounce）
  发布 /hardware/seg_confirm            ← 分配确认（SegConfirm）

不依赖 python-can / CAN 设备，可在纯 ROS 环境直接运行。
用法：python3 sim_lower_machine.py [--vacuum-loss]
"""

import os
import random
import sys
import threading

import rospy
from std_msgs.msg import Header, String

from robot_control_backend.msg import (
    CmdAck,
    Feedback,
    GyroFeedback,
    IntCmd,
    ModuleStatus,
    SegAssign,
    SegConfirm,
    SensorCmd,
    UidAnnounce,
    VacuumLoss,
)

ROTATION_AXES = (1, 4, 7, 10, 13)          # J1
SWING_AXES = (2, 5, 8, 11, 14)             # J2
TELESCOPIC_AXES = (3, 6, 9, 12, 15)        # J3
ARM_SENSOR_AXES = (21, 22, 23, 24, 25)     # 臂级压力/IMU

UID56 = 0x1234567890ABCD
ANNOUNCE_SLOT = 0
EVT_CMD_ACK = 6


def load_env_config():
    env_path = os.path.join(os.path.dirname(__file__), '../rob_arm.env')
    if not os.path.exists(env_path):
        raise FileNotFoundError(env_path)
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value
    rospy.loginfo("✅ sim_lower_machine 已从 rob_arm.env 加载配置")


class LowerMachineSimulator:
    def __init__(self, emit_vacuum_loss=False):
        load_env_config()
        rospy.init_node("sim_lower_machine")

        self._lock = threading.Lock()

        # 轴绝对位置，单位与 CAN 字段一致：旋转/摆动 0.01°，伸缩 0.01mm
        self.position = {}
        for axis in ROTATION_AXES:
            self.position[axis] = random.randint(-2000, 2000)       # ±20°
        for axis in SWING_AXES:
            self.position[axis] = 500                               # 5°
        for axis in TELESCOPIC_AXES:
            self.position[axis] = 1000                              # 10mm

        # 会话状态
        self.assigned_seg = None
        self.assigned_arm = None
        self.announced = False
        self.module_id = int(os.environ.get("CAN_DEFAULT_SEG", "0"))
        self.pressure_enabled = {axis: False for axis in ARM_SENSOR_AXES}
        self.pressure_seq = 0
        self.estop_latched = False
        self.emit_vacuum_loss = emit_vacuum_loss
        self.command_log = []

        # ---- 发布 ----
        self.pub_rot = rospy.Publisher(
            os.environ['ROS_TOPIC_CAN_ROTATION_RAW'], Feedback, queue_size=50)
        self.pub_swing = rospy.Publisher(
            os.environ['ROS_TOPIC_CAN_SWING_RAW'], Feedback, queue_size=50)
        self.pub_tel = rospy.Publisher(
            os.environ['ROS_TOPIC_CAN_TELESCOPIC_RAW'], Feedback, queue_size=50)
        self.pub_pressure = rospy.Publisher(
            os.environ['ROS_TOPIC_CAN_PRESSURE_RAW'], SensorCmd, queue_size=50)
        self.pub_gyro = rospy.Publisher(
            os.environ['ROS_TOPIC_GYROSCOPE_FEEDBACK'], GyroFeedback, queue_size=50)
        self.pub_announce = rospy.Publisher(
            os.environ['ROS_TOPIC_UID_ANNOUNCE'], UidAnnounce, queue_size=10)
        self.pub_confirm = rospy.Publisher(
            os.environ['ROS_TOPIC_SEG_CONFIRM'], SegConfirm, queue_size=10)
        self.pub_vacuum = rospy.Publisher(
            os.environ['ROS_TOPIC_VACUUM_LOSS'], VacuumLoss, queue_size=10)
        self.pub_cmd_ack = rospy.Publisher(
            os.environ['ROS_TOPIC_CMD_ACK'], CmdAck, queue_size=10)
        self.pub_module_status = rospy.Publisher(
            os.environ['ROS_TOPIC_MODULE_STATUS'], ModuleStatus, queue_size=10)

        # ---- 订阅 ----
        rospy.Subscriber(os.environ['ROS_TOPIC_ARM_CMD_VEL'], IntCmd, self.on_arm_cmd)
        rospy.Subscriber(os.environ['ROS_TOPIC_SEG_ASSIGN'], SegAssign, self.on_seg_assign)
        rospy.Subscriber(os.environ['ROS_TOPIC_SEG_BIND'], IntCmd, self.on_seg_bind)
        # 收到新的模块确认请求时，模拟该臂重新上电，恢复未编号宣告
        rospy.Subscriber(os.environ['ROS_TOPIC_MODULE_CMD'], IntCmd, self.on_module_cmd)
        # 状态查询：回复电机掩码/模块状态（模拟三电机全部存在且就绪）
        rospy.Subscriber(os.environ['ROS_TOPIC_MODULE_STATUS_QUERY'], IntCmd, self.on_status_query)
        rospy.Subscriber(os.environ['ROS_TOPIC_FRONTEND_POINTCLOUD'], String,
                         self.on_drawing_path)

        rospy.loginfo("🧪 下位机模拟节点已启动：15 轴反馈 + 压力 + IMU + 会话握手")
        rospy.loginfo("   初始位置（0.01 单位）：%s", self.position)

    # ===================== 下行指令 =====================
    def on_arm_cmd(self, msg):
        position = list(msg.position)
        device_id = int(msg.device_id)
        with self._lock:
            if device_id == 0 and position:
                sub = int(position[0])
                if sub == 0x01:
                    self.estop_latched = True
                    rospy.logwarn("🛑 模拟下位机：收到全局急停 [0x01]，已锁存")
                elif sub == 0x04:
                    self.estop_latched = False
                    rospy.loginfo("✅ 模拟下位机：收到急停解除 [0x04]")
                else:
                    rospy.loginfo("📥 系统级指令：module=%d position=%s",
                                  msg.module_id, position)
                self.command_log.append(("system", device_id, position))
                return

            if 1 <= device_id <= 15 and position:
                if self.estop_latched:
                    self._ack(device_id, msg.module_id, result=5)
                    rospy.logwarn("⛔ 轴 %d 指令被急停锁存拒绝", device_id)
                    return
                delta = int(position[0])
                old = self.position.get(device_id, 0)
                self.position[device_id] = old + delta
                self.command_log.append(("axis", device_id, delta))
                rospy.loginfo("⚙️ 轴 %d 增量 %+d → 位置 %+d（0.01 单位）",
                              device_id, delta, self.position[device_id])
                # 命令生效后立即回一帧，前端无需等待周期反馈
                self._publish_axis(device_id)
                return

            if 21 <= device_id <= 25 and len(position) >= 2:
                cmd_type, cmd_value = int(position[0]), int(position[1])
                if cmd_type == 1:
                    self.pressure_enabled[device_id] = (cmd_value == 1)
                    rospy.loginfo("🫧 压力传感器臂%d：%s（rate_idx=%s）",
                                  device_id - 20,
                                  "开启" if cmd_value else "停止",
                                  position[2] if len(position) > 2 else "-")
                return

            rospy.logwarn("⚠️ 模拟下位机收到未识别指令：device_id=%d position=%s",
                          device_id, position)

    def _ack(self, device_id, module_id, result, detail=0, ack_msg=1):
        m = CmdAck()
        m.header = Header(stamp=rospy.Time.now())
        m.module_id = module_id
        m.device_id = device_id
        m.ack_msg = ack_msg
        m.result = result
        m.detail = detail
        self.pub_cmd_ack.publish(m)

    # ===================== 会话握手 =====================
    def on_seg_assign(self, msg):
        # 新固件：绑定成功后回两帧——组号确认（arm=0 标记）+ 臂位确认（arm/axis_base 有效）
        seg_confirm = SegConfirm()
        seg_confirm.header = Header(stamp=rospy.Time.now())
        seg_confirm.uid56 = msg.target_uid56
        seg_confirm.seg = msg.seg
        seg_confirm.result = 0
        seg_confirm.arm = 0
        seg_confirm.axis_base = 0
        arm_confirm = SegConfirm()
        arm_confirm.header = seg_confirm.header
        arm_confirm.uid56 = msg.target_uid56
        arm_confirm.seg = 15            # 无效占位
        arm_confirm.result = 0
        arm_confirm.arm = msg.arm
        arm_confirm.axis_base = (int(msg.arm) - 1) * 3 + 1
        self.pub_confirm.publish(seg_confirm)
        self.pub_confirm.publish(arm_confirm)
        with self._lock:
            self.assigned_seg = int(msg.seg)
            self.assigned_arm = int(msg.arm)
            self.module_id = int(msg.seg)
        rospy.loginfo("🤝 模拟下位机：收到绑定 SEG=%d ARM=%d，已回组号+臂位双确认",
                      msg.seg, msg.arm)

    def on_status_query(self, msg):
        if self.assigned_seg is None:
            return
        m = ModuleStatus()
        m.header = Header(stamp=rospy.Time.now())
        m.module_id = self.assigned_seg & 0xFF
        m.seg = self.assigned_seg & 0xFF
        m.arm = self.assigned_arm & 0xFF
        m.axis_base = (self.assigned_arm - 1) * 3 + 1
        m.exist_mask = 0x07
        m.ready_mask = 0x07
        m.module_state = 0x03           # 已绑定 + 允许运动
        m.token = int(msg.position[0]) & 0xFFFF if msg.position else 0
        self.pub_module_status.publish(m)
        rospy.loginfo("📋 模拟下位机：回复状态查询 Token=0x%04X", m.token)

    def on_module_cmd(self, msg):
        with self._lock:
            self.assigned_seg = None
            self.assigned_arm = None
        rospy.loginfo("🔌 模拟下位机：收到模块确认请求 position=%s → 模拟重新上电，恢复宣告",
                      list(msg.position))

    def on_seg_bind(self, msg):
        if int(msg.module_id) < 0:
            rospy.loginfo("🔗 解绑 SEG 路由：module=%d", msg.module_id)
            return
        with self._lock:
            self.module_id = int(msg.position[0]) if msg.position else self.module_id
        rospy.loginfo("🔗 绑定 SEG 路由：业务模块 %d → SEG %s",
                      msg.module_id, msg.position)

    def on_drawing_path(self, msg):
        rospy.loginfo("📂 模拟下位机收到图纸路径：%s", msg.data)

    # ===================== 周期上行 =====================
    def _publish_axis(self, axis):
        m = Feedback()
        m.header = Header(stamp=rospy.Time.now())
        m.module_id = self.module_id & 0xFF
        m.device_id = axis
        m.position = [float(self.position[axis])]
        if axis in ROTATION_AXES:
            self.pub_rot.publish(m)
        elif axis in SWING_AXES:
            self.pub_swing.publish(m)
        elif axis in TELESCOPIC_AXES:
            self.pub_tel.publish(m)

    def _publish_pressure(self):
        for axis in ARM_SENSOR_AXES:
            m = SensorCmd()
            m.header = Header(stamp=rospy.Time.now())
            m.id = self.pressure_seq & 0xFF
            m.module_id = self.module_id & 0xFF
            m.device_id = axis
            base = 5200.0 if self.pressure_enabled[axis] else 120.0
            m.position = [base + random.uniform(-40.0, 40.0)]   # 克
            self.pub_pressure.publish(m)
        self.pressure_seq += 1

    def _publish_imu(self):
        # 仿真只提供水平静止的 IMU 原始数据，用于打通 Mahony→正运动学→前端链路；
        # 姿态精度需用真实 IMU 验证，仿真器不对姿态解算精度负责。
        gravity = float(os.environ.get("IMU_GRAVITY", "9.81"))
        for axis in ARM_SENSOR_AXES:
            m = GyroFeedback()
            m.header = Header(stamp=rospy.Time.now())
            m.module_id = self.module_id & 0xFF
            m.device_id = axis
            m.accel_x = 0.0
            m.accel_y = 0.0
            m.accel_z = gravity
            m.gyro_x = 0.0
            m.gyro_y = 0.0
            m.gyro_z = 0.0
            self.pub_gyro.publish(m)

    def _publish_announce(self):
        m = UidAnnounce()
        m.header = Header(stamp=rospy.Time.now())
        m.device_type = 1
        m.uid56 = UID56
        m.slot = ANNOUNCE_SLOT
        self.pub_announce.publish(m)

    def _publish_vacuum_loss(self):
        for axis in ARM_SENSOR_AXES:
            m = VacuumLoss()
            m.header = Header(stamp=rospy.Time.now())
            m.module_id = self.module_id & 0xFF
            m.device_id = axis
            m.pressure_raw = 120
            m.loss_threshold = 1000
            self.pub_vacuum.publish(m)

    def run(self):
        rate = rospy.Rate(10)   # 10Hz 调度；轴/IMU 2Hz、压力 5Hz
        tick = 0
        while not rospy.is_shutdown():
            with self._lock:
                axes = list(self.position.items())
                assigned = self.assigned_seg
            for axis, _ in axes:
                self._publish_axis(axis)
            if tick % 2 == 0:
                self._publish_pressure()
            if tick % 5 == 0:
                self._publish_imu()
            if assigned is None and tick % 5 == 0:
                self._publish_announce()
            if self.emit_vacuum_loss and tick % 100 == 0:
                self._publish_vacuum_loss()
            tick += 1
            rate.sleep()


if __name__ == "__main__":
    try:
        sim = LowerMachineSimulator(emit_vacuum_loss="--vacuum-loss" in sys.argv)
        sim.run()
    except rospy.ROSInterruptException:
        pass
    except Exception as exc:
        rospy.logerr("模拟节点异常：%s", exc)
