#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import struct
import threading
import sqlite3
from datetime import datetime

import rospy
import can
from std_msgs.msg import Header

from robot_control_backend.msg import (
    IntCmd,
    Feedback,
    SensorCmd,
    GyroFeedback,
    Heartbeat,
    AxisStatus,
    ArriveNotification,
    StopNotification,
    CmdAck,
    HomeStatus,
    AxisFault,
    LimitEvent,
    VacuumLoss,
)


def load_env_config():
    """从 .env 文件加载配置"""
    env_path = os.path.join(os.path.dirname(__file__), '../rob_arm.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value
        rospy.loginfo("✅ hardware_node 已从 rob_arm.env 加载配置")


class CANBusBridge:
    """V2 CAN 总线 ↔ ROS 话题 唯一桥接节点"""

    # ===== 29 位 ID 位域常量 =====
    PRI_SAFETY, PRI_MOTION, PRI_EVENT, PRI_SENSOR, PRI_CONFIG, PRI_DIAG = 0, 1, 2, 3, 4, 5
    GRP_SYSTEM, GRP_MOTION_CMD, GRP_MOTION_FB, GRP_EVENT, GRP_SENSOR, GRP_CONFIG, GRP_DIAG = 0, 1, 2, 3, 4, 5, 6
    DIR_DOWN, DIR_PERIODIC, DIR_EVENT = 0, 1, 2

    # 急停/解除子命令
    SUB_EMERGENCY_STOP = 0x01
    SUB_RELEASE_STOP = 0x04
    SUB_MODULE_STOP = 0x08
    SUB_AXIS_STOP = 0x0C

    def __init__(self):
        load_env_config()
        rospy.init_node("can_bridge")

        # ---------- CAN 配置（全部只读 rob_arm.env，无硬编码默认值）----------
        self.channel = os.environ['CAN_CHANNEL']
        self.bitrate = int(os.environ['CAN_BITRATE'])
        self.node_count = int(os.environ['CAN_NODE_COUNT'])
        self.axis_count = int(os.environ['CAN_AXIS_COUNT'])
        self.seg = int(os.environ['CAN_MODULE_COUNT']) - 1  # SEG 从 0 开始
        # V2：ROS 层 device_id 即 AXIS（1~25），下行帧 CAN NODE 段恒填主控节点号
        self.master_node = int(os.environ['CAN_MASTER_NODE_ID'])
        self.default_speed = int(os.environ['CAN_DEFAULT_SPEED_LIMIT'])
        self.heartbeat_timeout = float(os.environ['CAN_HEARTBEAT_TIMEOUT'])
        self.gyro_scale = float(os.environ['IMU_GYRO_SCALE'])
        self.acc_scale = float(os.environ['IMU_ACC_SCALE'])
        # V2：上行 ROS 消息的 module_id 不做静态配置，一律取 CAN 帧 ID 的 SEG 位域（帧自带模块号）
        self.sensor_arm_base = int(os.environ['CAN_SENSOR_ARM_BASE'])

        # ---------- 运行状态 ----------
        self.bus = None
        self.running = True
        self.bus_lock = threading.Lock()
        self.last_sent = None
        # node -> {time, state, run_mask, base_mask}
        self.node_heartbeats = {}
        self.node_lost = set()
        # arm(1~5) -> {gyro, accel, ts}
        self.imu_cache = {}

        # ---------- 话题（发布；只读 rob_arm.env，无硬编码默认值）----------
        self.pub_rot_raw = rospy.Publisher(
            os.environ['ROS_TOPIC_CAN_ROTATION_RAW'], Feedback, queue_size=50)
        self.pub_swing_raw = rospy.Publisher(
            os.environ['ROS_TOPIC_CAN_SWING_RAW'], Feedback, queue_size=50)
        self.pub_tel_raw = rospy.Publisher(
            os.environ['ROS_TOPIC_CAN_TELESCOPIC_RAW'], Feedback, queue_size=50)
        self.pub_pressure_raw = rospy.Publisher(
            os.environ['ROS_TOPIC_CAN_PRESSURE_RAW'], SensorCmd, queue_size=50)
        self.pub_gyro = rospy.Publisher(
            os.environ['ROS_TOPIC_GYROSCOPE_FEEDBACK'], GyroFeedback, queue_size=50)
        self.pub_heartbeat = rospy.Publisher(
            os.environ['ROS_TOPIC_HEARTBEAT'], Heartbeat, queue_size=30)
        self.pub_axis_status = rospy.Publisher(
            os.environ['ROS_TOPIC_AXIS_STATUS'], AxisStatus, queue_size=30)
        self.pub_arrive = rospy.Publisher(
            os.environ['ROS_TOPIC_ARRIVE_NOTIFICATION'], ArriveNotification, queue_size=30)
        self.pub_stop = rospy.Publisher(
            os.environ['ROS_TOPIC_STOP_NOTIFICATION'], StopNotification, queue_size=30)
        # V2 新增话题
        self.pub_cmd_ack = rospy.Publisher(
            os.environ['ROS_TOPIC_CMD_ACK'], CmdAck, queue_size=30)
        self.pub_home_status = rospy.Publisher(
            os.environ['ROS_TOPIC_HOME_STATUS'], HomeStatus, queue_size=30)
        self.pub_axis_fault = rospy.Publisher(
            os.environ['ROS_TOPIC_AXIS_FAULT'], AxisFault, queue_size=30)
        self.pub_limit_event = rospy.Publisher(
            os.environ['ROS_TOPIC_LIMIT_EVENT'], LimitEvent, queue_size=30)
        self.pub_vacuum_loss = rospy.Publisher(
            os.environ['ROS_TOPIC_VACUUM_LOSS'], VacuumLoss, queue_size=30)

        # ---------- 订阅 ----------
        rospy.Subscriber(os.environ['ROS_TOPIC_ARM_CMD_VEL'], IntCmd, self.on_cmd_received)
        rospy.Subscriber(os.environ['ROS_TOPIC_HOME_CMD'], IntCmd, self.on_home_cmd)

        # ---------- 心跳看门狗 ----------
        rospy.Timer(rospy.Duration(0.1), self._heartbeat_watchdog)

        # ---------- 数据库归档 ----------
        self._init_archive_db()

        # ---------- 启动 CAN ----------
        self.read_thread = threading.Thread(target=self._read_can_loop)
        self.read_thread.daemon = True
        self.read_thread.start()

        rospy.on_shutdown(self.close)
        rospy.loginfo("✅ V2 CAN 桥接节点启动：%s @ %dbps（节点=%d, 轴=%d）",
                      self.channel, self.bitrate, self.node_count, self.axis_count)

    # ======================================================================
    # V2 29 位 ID 位域
    # ======================================================================
    def _build_id(self, pri, grp, node=0, axis=0, direction=0, msg=0):
        return ((pri & 0x7) << 26) | ((grp & 0xF) << 22) | ((self.seg & 0xF) << 18) | \
               ((node & 0x1F) << 13) | ((axis & 0x1F) << 8) | ((direction & 0x3) << 6) | ((msg & 0xF) << 2)

    @staticmethod
    def _parse_id(can_id):
        aid = can_id & 0x1FFFFFFF
        return {
            "pri":  (aid >> 26) & 0x7,
            "grp":  (aid >> 22) & 0xF,
            "seg":  (aid >> 18) & 0xF,
            "node": (aid >> 13) & 0x1F,
            "axis": (aid >> 8) & 0x1F,
            "dir":  (aid >> 6) & 0x3,
            "msg":  (aid >> 2) & 0xF,
        }

    # ======================================================================
    # CAN 连接 / 过滤器（V2 类级掩码 0x1FFFE000）
    # ======================================================================
    def _make_filters(self):
        rtr_mask = 0x20000000
        sys_mask = 0x1FC00000 | rtr_mask          # 安全/系统组：只看 PRI+GRP
        cls_mask = 0x1FFFE000 | rtr_mask          # 运动/事件/传感器：PRI+GRP+SEG+NODE
        def f(base, mask):
            return {"can_id": base, "can_mask": mask, "extended": True}
        return [
            f(self._build_id(self.PRI_SAFETY, self.GRP_SYSTEM), sys_mask),
            f(self._build_id(self.PRI_MOTION, self.GRP_MOTION_FB, node=self.master_node), cls_mask),
            f(self._build_id(self.PRI_EVENT, self.GRP_EVENT, node=self.master_node), cls_mask),
            f(self._build_id(self.PRI_SENSOR, self.GRP_SENSOR, node=self.master_node), cls_mask),
        ]

    def _connect_bus(self):
        return can.interface.Bus(
            channel=self.channel, bustype="socketcan", bitrate=self.bitrate,
            can_filters=self._make_filters())

    def _read_can_loop(self):
        while self.running and not rospy.is_shutdown():
            if self.bus is None:
                try:
                    with self.bus_lock:
                        self.bus = self._connect_bus()
                    rospy.loginfo("✅ CAN 总线已连接：%s", self.channel)
                except Exception as e:
                    rospy.logerr_throttle(5.0, "❌ CAN 连接失败（5s 后重试）：%s", e)
                    rospy.sleep(1.0)
                    continue
            try:
                msg = self.bus.recv(timeout=0.5)
                if msg is not None and msg.is_extended_id:
                    self._parse_can_frame(msg)
            except Exception as e:
                rospy.logerr_throttle(2.0, "❌ CAN 接收异常，准备重连：%s", e)
                with self.bus_lock:
                    try: self.bus.shutdown()
                    except Exception: pass
                    self.bus = None
                rospy.sleep(0.5)

    # ======================================================================
    # 发送
    # ======================================================================
    def _send_can_frame(self, can_id, data):
        if self.bus is None:
            rospy.logwarn("⚠️ CAN 未连接，丢弃帧 0x%08X", can_id)
            return False
        frame = can.Message(arbitration_id=can_id, data=data, is_extended_id=True)
        try:
            with self.bus_lock:
                self.bus.send(frame, timeout=0.2)
            return True
        except Exception as e:
            rospy.logerr("❌ CAN 发送失败 0x%08X: %s", can_id, e)
            return False

    def on_cmd_received(self, msg):
        """/arm/cmd_vel：ROS 指令 → CAN 帧"""
        device_id = int(msg.device_id)
        if not msg.position:
            return
        value = int(msg.position[0])

        # ---- 系统级指令（device_id=0）----
        if device_id == 0:
            sub = value & 0xFF
            if sub == self.SUB_EMERGENCY_STOP:
                self._send_can_frame(0x00000000, bytes([0x01]))
                rospy.logwarn("🚨 已发送 CAN 广播急停 0x00000000")
            elif sub == self.SUB_RELEASE_STOP:
                self._send_can_frame(0x00000004, bytes([0x01]))
                rospy.logwarn("✅ 已发送 CAN 急停解除 0x00000004")
            elif sub == self.SUB_MODULE_STOP:
                mod = int(msg.position[1]) if len(msg.position) > 1 else 0
                can_id = 0x00000008 | (mod << 18)
                self._send_can_frame(can_id, bytes([0x01]))
                rospy.logwarn("🚨 模块%d 安全停 0x%08X", mod, can_id)
            else:
                rospy.logwarn("⚠️ 未知系统子命令 0x%02X", sub)
            return

        # V2：ROS 层 device_id 即 AXIS 寻址单元（1~20轴/21~25臂级），CAN NODE 段恒为主控节点
        axis = device_id
        node = self.master_node
        if not (1 <= axis <= 25):
            rospy.logwarn("⚠️ device_id=%d 非法（允许 1~20 轴 / 21~25 臂级）", device_id)
            return

        # ---- 单轴急停：position=[0x0C] ----
        if value == self.SUB_AXIS_STOP and 1 <= axis <= 20:
            can_id = self._build_id(self.PRI_SAFETY, self.GRP_SYSTEM, node, axis, self.DIR_DOWN, 3)
            self._send_can_frame(can_id, bytes([0x01]))
            rospy.logwarn("🚨 轴%d 单轴急停 0x%08X", axis, can_id)
            return

        # ---- 臂级传感器启停：axis 21~25，position=[cmd_type, cmd_value, rate_idx] ----
        if 21 <= axis <= 25:
            if len(msg.position) < 3:
                rospy.logwarn("⚠️ 臂级传感器指令需要 position=[cmd_type, cmd_value, rate_idx]")
                return
            cmd_type = int(msg.position[0]) & 0xFF
            cmd_value = int(msg.position[1]) & 0xFF
            rate_idx = int(msg.position[2]) & 0xFF
            if cmd_type == 1:       # 压力通道 MSG=0
                can_id = self._build_id(self.PRI_SENSOR, self.GRP_SENSOR, node, axis, self.DIR_DOWN, 0)
            elif cmd_type == 2:     # IMU MSG=1
                can_id = self._build_id(self.PRI_SENSOR, self.GRP_SENSOR, node, axis, self.DIR_DOWN, 1)
            else:
                rospy.logwarn("⚠️ 未知传感器 cmd_type=%d", cmd_type)
                return
            self._send_can_frame(can_id, bytes([cmd_value, rate_idx]))
            rospy.loginfo("📶 臂级传感器 axis=%d type=%d cmd=0x%02X rate=%d → 0x%08X",
                          axis, cmd_type, cmd_value, rate_idx, can_id)
            return

        # ---- 单轴绝对角度命令：position=[target_angle_001deg] ----
        if 1 <= axis <= 20:
            # 去重签名含 header.stamp：仅抑制同一条指令的回声/重复投递（stamp 相同）。
            # 相对增量控制下，即使累加后的绝对目标与上次相同，新指令（新 stamp）也允许重新下发；
            # stamp 缺失（=0）时不做去重。
            stamp_nsec = msg.header.stamp.to_nsec() if msg.header and msg.header.stamp.to_nsec() > 0 else None
            sig = (device_id, value, stamp_nsec)
            if stamp_nsec is not None and sig == self.last_sent:
                rospy.loginfo("↪️ 轴%d 重复指令（stamp 相同，目标 %d/0.01°）已抑制", axis, value)
                return
            can_id = self._build_id(self.PRI_MOTION, self.GRP_MOTION_CMD, node, axis, self.DIR_DOWN, 0)
            payload = struct.pack('>iH', int(value), self.default_speed)
            if self._send_can_frame(can_id, payload):
                self.last_sent = sig
                rospy.loginfo("📤 轴%d 绝对角度 %d(0.01°) → 0x%08X", axis, value, can_id)
            return

        rospy.logwarn("⚠️ 无法识别 axis=%d（device_id=%d）", axis, device_id)

    def on_home_cmd(self, msg):
        """/control/home_cmd：回零命令，position=[home_mode]（0x01=回零, 0x02=清除基准）"""
        device_id = int(msg.device_id)
        if not msg.position:
            return
        axis = device_id
        if not (1 <= axis <= 20):
            rospy.logwarn("⚠️ 回零指令 device_id=%d 非法（允许轴号 1~20）", device_id)
            return
        home_mode = int(msg.position[0]) & 0xFF
        can_id = self._build_id(self.PRI_MOTION, self.GRP_MOTION_CMD,
                                self.master_node, axis, self.DIR_DOWN, 4)
        self._send_can_frame(can_id, bytes([home_mode]))
        rospy.loginfo("🏠 轴%d 回零命令 mode=0x%02X → 0x%08X", axis, home_mode, can_id)

    # ======================================================================
    # 接收：CAN 帧 → ROS 话题
    # ======================================================================
    def _header(self):
        return Header(stamp=rospy.Time.now())

    def _parse_can_frame(self, msg):
        f = self._parse_id(msg.arbitration_id)
        grp, seg, node, axis, direction, mnum, data = (
            f["grp"], f["seg"], f["node"], f["axis"], f["dir"], f["msg"], bytes(msg.data))
        # 轴级(1~20)/臂级(21~25)帧 device_id 即 AXIS；节点级帧(axis=0，心跳等) 用 node 号
        device_id = axis if axis != 0 else node
        # module_id 直接取 CAN 帧 SEG 位域（模块号由帧自带，不做静态配置）
        module_id = seg

        # ---------------- GRP=0 系统与安全 ----------------
        if grp == self.GRP_SYSTEM:
            if direction == self.DIR_PERIODIC:
                if mnum == 0:                                    # 心跳 DLC=8
                    state = data[0]
                    run_mask = struct.unpack_from('>I', b'\x00' + data[1:4])[0] if len(data) >= 4 else 0
                    base_mask = struct.unpack_from('>I', b'\x00' + data[4:7])[0] if len(data) >= 7 else 0
                    self.node_heartbeats[node] = {"time": rospy.Time.now().to_sec(),
                                                  "state": state, "run": run_mask, "base": base_mask}
                    self.node_lost.discard(node)
                    self.pub_heartbeat.publish(Heartbeat(
                        header=self._header(), module_id=module_id, node_id=node,
                        state=state, run_axis_mask=run_mask, base_valid_mask=base_mask))
                elif mnum == 1:                                  # 看门狗告警
                    rospy.logerr("🚨 节点%d 看门狗告警 Src=%d Action=%d", node, data[0], data[1])
                elif mnum == 2:                                  # 节点故障
                    rospy.logerr("❌ 节点%d 故障 Err=%d Sev=%d TEC=%d REC=%d",
                                 node, data[0], data[1], data[2], data[3])
                elif mnum == 3:                                  # 启动握手
                    rospy.loginfo("🤝 节点%d 上线 v%d.%d.%d type=%d",
                                  node, data[0], data[1], data[3], data[2])
            elif direction == self.DIR_EVENT and mnum == 0:      # 吸盘失压（PRI=0 臂级）
                pressure_raw = struct.unpack_from('>i', data, 0)[0] if len(data) >= 4 else 0
                loss_th = struct.unpack_from('>H', data, 4)[0] if len(data) >= 6 else 0
                self.pub_vacuum_loss.publish(VacuumLoss(
                    header=self._header(), module_id=module_id, device_id=device_id,
                    pressure_raw=pressure_raw, loss_threshold=loss_th))
                rospy.logerr("🌀 吸盘失压 臂=%d pressure=%d threshold=%d",
                             axis - self.sensor_arm_base + 1, pressure_raw, loss_th)
            return

        # ---------------- GRP=2 运动反馈 ----------------
        if grp == self.GRP_MOTION_FB and direction == self.DIR_PERIODIC:
            if mnum == 0:                                        # 单轴角度 int32 (0.01°)
                angle = struct.unpack_from('>i', data, 0)[0]
                self._dispatch_axis_feedback(module_id, device_id, axis, angle)
                self._archive_sensor(module_id, device_id, angle, "轴角度反馈(0.01°)")
            elif mnum == 3:                                      # 轴状态字 DLC=4
                status_bits = struct.unpack_from('>H', data, 0)[0] if len(data) >= 2 else 0
                axis_state = data[2] if len(data) >= 3 else 0
                base_valid = (status_bits >> 8) & 0x01
                self.pub_axis_status.publish(AxisStatus(
                    header=self._header(), module_id=module_id, device_id=device_id,
                    status_bits=status_bits, axis_state=axis_state, base_valid=base_valid))
            elif mnum == 4:                                      # 位置打包上报 DLC=8
                start_axis = data[0]
                axis_count = data[1]
                for i in range(min(axis_count, 3)):
                    off = 2 + i * 2
                    if off + 2 > len(data):
                        break
                    a = struct.unpack_from('>h', data, off)[0]
                    ax = start_axis + i
                    did = ax
                    self._dispatch_axis_feedback(module_id, did, ax, a)
            elif mnum == 5:                                      # 命令应答 DLC=3
                ack_msg = data[0] if len(data) >= 1 else 0
                result = data[1] if len(data) >= 2 else 0
                detail = data[2] if len(data) >= 3 else 0
                self.pub_cmd_ack.publish(CmdAck(
                    header=self._header(), module_id=module_id, device_id=device_id,
                    ack_msg=ack_msg, result=result, detail=detail))
                if result != 0:
                    rospy.logwarn("📝 轴%d 命令应答 result=%d(0=接受1忙2基准3越界4故障5急停锁存)",
                                  axis, result)
            return

        # ---------------- GRP=3 事件通知 ----------------
        if grp == self.GRP_EVENT and direction == self.DIR_EVENT:
            if mnum == 0:                                        # 到位通知 DLC=8
                angle = struct.unpack_from('>i', data, 0)[0] if len(data) >= 4 else 0
                pos_err = struct.unpack_from('>h', data, 4)[0] if len(data) >= 6 else 0
                sb = data[6] if len(data) >= 7 else 0
                fl = data[7] if len(data) >= 8 else 0
                self.pub_arrive.publish(ArriveNotification(
                    header=self._header(), module_id=module_id, device_id=device_id,
                    angle=angle, pos_error=pos_err, status_bits=sb, flags=fl))
            elif mnum == 1:                                      # 停止通知 DLC=2
                self.pub_stop.publish(StopNotification(
                    header=self._header(), module_id=module_id, device_id=device_id,
                    stop_reason=data[0], output_level=data[1]))
            elif mnum == 2:                                      # 轴故障事件 DLC=6
                fault_bits = struct.unpack_from('>H', data, 0)[0] if len(data) >= 2 else 0
                la = data[2] if len(data) >= 3 else 0
                det = data[3] if len(data) >= 4 else 0
                dur = struct.unpack_from('>H', data, 4)[0] if len(data) >= 6 else 0
                self.pub_axis_fault.publish(AxisFault(
                    header=self._header(), module_id=module_id, device_id=device_id,
                    fault_bits=fault_bits, local_action=la, detail=det, duration_ms=dur))
                rospy.logerr("❌ 轴%d 故障 bits=0x%04X", axis, fault_bits)
            elif mnum == 3:                                      # 回零状态 DLC=6
                hr = data[0]
                bv = data[1]
                angle = struct.unpack_from('>i', data, 2)[0] if len(data) >= 6 else 0
                self.pub_home_status.publish(HomeStatus(
                    header=self._header(), module_id=module_id, device_id=device_id,
                    home_result=hr, base_valid=bv, angle=angle))
                rospy.loginfo("🏠 轴%d 回零 result=%d base_valid=%d angle=%d", axis, hr, bv, angle)
            elif mnum == 4:                                      # 限位事件 DLC=2
                self.pub_limit_event.publish(LimitEvent(
                    header=self._header(), module_id=module_id, device_id=device_id,
                    limit_type=data[0], output_level=data[1]))
                rospy.logwarn("⚠️ 轴%d 限位 type=%d", axis, data[0])
            return

        # ---------------- GRP=4 传感器（臂级 axis 21~25）----------------
        if grp == self.GRP_SENSOR:
            if direction == self.DIR_PERIODIC:
                if mnum == 0:                                    # 压力上报 DLC=6
                    pressure_raw = struct.unpack_from('>i', data, 0)[0] if len(data) >= 4 else 0
                    self.pub_pressure_raw.publish(SensorCmd(
                        header=self._header(), id=0, module_id=module_id,
                        device_id=device_id, position=[float(pressure_raw)]))
                    self._archive_sensor(module_id, device_id, pressure_raw, "压力传感器数据")
                elif mnum == 1:                                  # 角速度 int16×3
                    if len(data) >= 6:
                        gx, gy, gz = struct.unpack_from('>hhh', data, 0)
                        self._cache_imu(axis, module_id, gyro=(gx, gy, gz))
                elif mnum == 2:                                  # 加速度 int16×3
                    if len(data) >= 6:
                        ax, ay, az = struct.unpack_from('>hhh', data, 0)
                        self._cache_imu(axis, module_id, accel=(ax, ay, az))
            elif direction == self.DIR_EVENT and mnum == 0:      # 通道停止通知
                rospy.loginfo("🔌 臂级传感器 axis=%d 停止 StopMask=0x%02X", axis, data[0])
            return

        # ---------------- GRP=6 诊断 ----------------
        if grp == self.GRP_DIAG and direction == self.DIR_PERIODIC and mnum == 1:
            rospy.logwarn_throttle(10.0, "🩺 CAN 链路 节点%d TEC=%d REC=%d", node, data[0], data[1])

    def _dispatch_axis_feedback(self, module_id, device_id, axis, angle):
        """按轴号分发到旋转/摆动/伸缩原始反馈话题（0.01°）；module_id 为帧 SEG 位域"""
        fb = Feedback(header=self._header(), module_id=module_id,
                      device_id=device_id, position=[float(angle)])
        joint_idx = (axis - 1) % 4
        if joint_idx == 0:          # J1 旋转：轴 1,5,9,13,17
            self.pub_rot_raw.publish(fb)
        elif joint_idx == 1:        # J2 摆动：轴 2,6,10,14,18
            self.pub_swing_raw.publish(fb)
        elif joint_idx == 3:        # J4 伸缩：轴 4,8,12,16,20
            self.pub_tel_raw.publish(fb)
        # joint_idx == 2 是 J3 空置，忽略

    # ---------- IMU 两帧合并（臂级）----------
    def _cache_imu(self, axis, module_id, gyro=None, accel=None):
        now = rospy.Time.now().to_sec()
        c = self.imu_cache.setdefault(axis, {"ts": now})
        c["ts"] = now
        c["module_id"] = module_id
        if gyro is not None:
            c["gyro"] = gyro
        if accel is not None:
            c["accel"] = accel
        if "gyro" in c and "accel" in c:
            gx, gy, gz = c.pop("gyro")
            ax, ay, az = c.pop("accel")
            # 臂级 device_id 即 AXIS（21~25）；module_id 取帧 SEG
            device_id = axis
            m = GyroFeedback(header=self._header(), module_id=c["module_id"], device_id=device_id)
            m.gyro_x, m.gyro_y, m.gyro_z = (v * self.gyro_scale for v in (gx, gy, gz))
            m.accel_x, m.accel_y, m.accel_z = (v * self.acc_scale for v in (ax, ay, az))
            self.pub_gyro.publish(m)
            self._archive_gyro(c["module_id"], device_id, m)

    # ======================================================================
    # 心跳看门狗
    # ======================================================================
    def _heartbeat_watchdog(self, event):
        now = rospy.Time.now().to_sec()
        for node in range(1, self.node_count + 1):
            hb = self.node_heartbeats.get(node)
            if hb is None:
                continue
            if now - hb["time"] > self.heartbeat_timeout and node not in self.node_lost:
                self.node_lost.add(node)
                rospy.logerr("🚨 节点%d 心跳超时 %.0fms，广播急停！", node, self.heartbeat_timeout * 1000)
                self._send_can_frame(0x00000000, bytes([0x01]))

    # ======================================================================
    # 数据库归档
    # ======================================================================
    def _init_archive_db(self):
        self.db_lock = threading.Lock()
        self.db_dirty = False
        db_path = os.environ['DB_PATH']
        self.db_conn = sqlite3.connect(db_path, check_same_thread=False)
        self.db_conn.execute("PRAGMA journal_mode=WAL;")
        # 统一归档到 sensor_log（传感器日志表，包括电机在内；与其余节点共用同一张表）
        self.db_conn.executescript("""
            CREATE TABLE IF NOT EXISTS sensor_log (
                Createtime DATETIME NOT NULL,
                creater_id INTEGER NOT NULL,
                Work_ID INTEGER NOT NULL,
                sensor_ID INTEGER NOT NULL,
                isread INTEGER NOT NULL,
                data TEXT NOT NULL,
                del_flag BOOL DEFAULT false,
                Notes TEXT,
                PRIMARY KEY (Createtime, sensor_ID)
            );
        """)
        self.db_conn.commit()
        rospy.Timer(rospy.Duration(1.0), self._sync_db)
        rospy.loginfo("🗄️ CAN 数据归档库已连接（sensor_log）")

    def _insert_sensor_log(self, module_id, device_id, payload, note):
        """写入 sensor_log：isread=1（上行），具体数据以 JSON 存入 data 字段"""
        createtime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data_json = json.dumps(payload, ensure_ascii=False)
        self.db_conn.execute(
            "INSERT INTO sensor_log (Createtime, creater_id, Work_ID, sensor_ID, isread, data, del_flag, Notes)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (createtime, 1, 1, device_id, 1, data_json, 0, note))
        self.db_dirty = True

    def _archive_sensor(self, module_id, device_id, value, note):
        """归档轴角度/压力等单值上行数据到 sensor_log；module_id 取 CAN 帧 SEG"""
        with self.db_lock:
            try:
                self._insert_sensor_log(module_id, device_id, {
                    "module_id": module_id,
                    "device_id": device_id,
                    "value": float(value)
                }, note)
            except Exception as e:
                rospy.logerr_throttle(10.0, "sensor_log 归档失败: %s", e)

    def _archive_gyro(self, module_id, device_id, m):
        """归档 IMU（加速度+角速度，已换算物理单位）上行数据到 sensor_log"""
        with self.db_lock:
            try:
                self._insert_sensor_log(module_id, device_id, {
                    "module_id": module_id,
                    "device_id": device_id,
                    "acc_x": m.accel_x, "acc_y": m.accel_y, "acc_z": m.accel_z,
                    "gyro_x": m.gyro_x, "gyro_y": m.gyro_y, "gyro_z": m.gyro_z
                }, "IMU惯性数据")
            except Exception as e:
                rospy.logerr_throttle(10.0, "sensor_log 归档失败: %s", e)

    def _sync_db(self, event):
        if self.db_dirty:
            with self.db_lock:
                try:
                    self.db_conn.commit()
                    self.db_dirty = False
                except Exception:
                    self.db_conn.rollback()

    def close(self):
        self.running = False
        try:
            with self.db_lock:
                if self.db_dirty:
                    self.db_conn.commit()
                self.db_conn.close()
        except Exception:
            pass
        with self.bus_lock:
            if self.bus is not None:
                try:
                    self.bus.shutdown()
                except Exception:
                    pass
        rospy.loginfo("🛑 V2 CAN 桥接节点已关闭")


if __name__ == "__main__":
    try:
        bridge = CANBusBridge()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass
