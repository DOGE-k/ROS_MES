#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""轴状态聚合节点（固件不发 MSG=3 状态字时的状态/位置转发）

背景：
    下位机固件不会周期性上报轴状态字帧，后端微调批次的执行前预检又要求
    /hardware/axis_status（状态 + base_valid）与三轴位置反馈都保持新鲜。
    本节点订阅真实指令/反馈/事件，推导每轴状态并统一发布状态字；
    空闲时按“最后一次真实位置”补发位置帧，让预检在无固件周期帧时也能工作。

数据来源：
    - /control/seg_assign、/control/seg_bind、/hardware/seg_confirm：SEG/ARM 绑定
    - /hardware/{rotation,swing,telescope}_output：指令发出 → RUNNING
    - /hardware/{rotation,swing,telescope}_feedback：真实位置
    - /hardware/cmd_ack：指令应答（result != 0 时回退空闲）
    - /hardware/arrive_notification：到位（用 angle 覆盖缓存位置）
    - /hardware/stop_notification、axis_fault、limit_event：停止/故障/限位/急停

发布：
    - /hardware/axis_status：5Hz，三轴状态字
    - /hardware/{rotation,swing,telescope}_feedback：空闲时 2Hz 补发缓存位置

注意：
    1. 位置补发只在 IDLE_ASSUMED / IDLE_CONFIRMED / ARRIVED 状态进行，
       RUNNING 或故障/限位/急停时绝不补发，避免把旧值当成新测量。
    2. 基准按“上电/人工调零后为 0”的现有约定建立；故障、限位、急停、
       看门狗停止、重新绑定都会使基准失效。
    3. 固件后续若开始主动上报 MSG=3，应停用本节点，避免双发布者混流。
"""

import os
import threading

import rospy
from std_msgs.msg import Header

from robot_control_backend.msg import (
    AxisStatus,
    ArriveNotification,
    StopNotification,
    CmdAck,
    AxisFault,
    LimitEvent,
    IntCmd,
    SegAssign,
    SegConfirm,
    RotationCmd,
    SwingCmd,
    TelescopicCmd,
)


def load_env_config():
    """从 ../rob_arm.env 加载配置（与其余节点保持一致）"""
    env_path = os.path.join(os.path.dirname(__file__), '../rob_arm.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value
        rospy.loginfo("✅ axis_status_aggregator 已从 rob_arm.env 加载配置")


# 状态字位定义（与 AxisStatus.msg 注释一致）
BIT_ENABLE = 1 << 0
BIT_RUN = 1 << 1
BIT_ARRIVE = 1 << 2
BIT_LIMIT_UP = 1 << 3
BIT_LIMIT_DOWN = 1 << 4
BIT_FAULT = 1 << 5
BIT_BUSY = 1 << 6
BIT_ESTOP = 1 << 7
BIT_BASE = 1 << 8

STATE_IDLE_ASSUMED = "IDLE_ASSUMED"
STATE_RUNNING = "RUNNING"
STATE_ARRIVED = "ARRIVED"
STATE_IDLE_CONFIRMED = "IDLE_CONFIRMED"
STATE_FAULT = "FAULT"
STATE_LIMIT = "LIMIT"
STATE_ESTOP = "ESTOP"

IDLE_STATES = (STATE_IDLE_ASSUMED, STATE_IDLE_CONFIRMED, STATE_ARRIVED)
LOCKED_STATES = (STATE_FAULT, STATE_LIMIT, STATE_ESTOP)


class AxisRuntime(object):
    """单轴运行状态与缓存"""

    def __init__(self, local_index):
        self.local = local_index
        self.reset()

    def reset(self):
        # 按现有“上电/人工调零后为 0”约定初始化；用户已确认沿用该假设
        self.cache = 0.0
        self.last_real = 0.0
        self.state = STATE_IDLE_ASSUMED
        self.pre_run_state = STATE_IDLE_ASSUMED
        self.arrive_until = 0.0
        self.arrive_latched = False
        self.motion_seen = False
        self.base_valid = True
        self.fault = False
        self.limit_up = False
        self.limit_down = False
        self.estop = False

    def bits(self):
        bits = 0
        if self.state not in (STATE_FAULT, STATE_ESTOP):
            bits |= BIT_ENABLE
        if self.state == STATE_RUNNING:
            bits |= BIT_RUN | BIT_BUSY
        if self.arrive_latched:
            bits |= BIT_ARRIVE
        if self.limit_up:
            bits |= BIT_LIMIT_UP
        if self.limit_down:
            bits |= BIT_LIMIT_DOWN
        if self.fault:
            bits |= BIT_FAULT
        if self.estop:
            bits |= BIT_ESTOP
        if self.base_valid:
            bits |= BIT_BASE
        return bits

    def axis_state_code(self):
        if self.state == STATE_RUNNING:
            return 1
        if self.state == STATE_ARRIVED:
            return 2
        if self.state in LOCKED_STATES:
            return 3
        return 0


class AxisStatusAggregator(object):

    def __init__(self):
        load_env_config()
        rospy.init_node("axis_status_aggregator")

        self.publish_hz = float(os.environ.get('AXIS_STATUS_PUBLISH_HZ', 5.0))
        self.cache_hz = float(os.environ.get('AXIS_CACHE_POSITION_HZ', 2.0))
        self.idle_confirm_s = float(os.environ.get('AXIS_IDLE_CONFIRM_S', 0.3))
        self.cache_hold_off_s = float(os.environ.get('AXIS_CACHE_HOLD_OFF_S', 0.5))
        self.motion_eps_deg = float(os.environ.get('AXIS_MOTION_EPS_DEG', 0.2))
        self.motion_eps_mm = float(os.environ.get('AXIS_MOTION_EPS_MM', 0.1))

        self._lock = threading.RLock()
        self.bound_seg = None
        self.bound_arm = None
        self._pending_seg = None
        self._assign_arm = {}
        self._last_arm_confirm = None
        self._last_arm_confirm_time = 0.0
        self.axes = {1: AxisRuntime(1), 2: AxisRuntime(2), 3: AxisRuntime(3)}
        self._last_unbound_warn = 0.0

        # ---------- 话题（只读 env，无硬编码默认值） ----------
        topic_status = os.environ['ROS_TOPIC_AXIS_STATUS']
        topic_rot_fb = os.environ['ROS_TOPIC_ROTATION_FEEDBACK']
        topic_sw_fb = os.environ['ROS_TOPIC_SWING_FEEDBACK']
        topic_tel_fb = os.environ['ROS_TOPIC_TELESCOPE_FEEDBACK']
        topic_rot_out = os.environ['ROS_TOPIC_ROTATION_OUTPUT']
        topic_sw_out = os.environ['ROS_TOPIC_SWING_OUTPUT']
        topic_tel_out = os.environ['ROS_TOPIC_TELESCOPE_OUTPUT']
        topic_ack = os.environ['ROS_TOPIC_CMD_ACK']
        topic_arrive = os.environ['ROS_TOPIC_ARRIVE_NOTIFICATION']
        topic_stop = os.environ['ROS_TOPIC_STOP_NOTIFICATION']
        topic_fault = os.environ['ROS_TOPIC_AXIS_FAULT']
        topic_limit = os.environ['ROS_TOPIC_LIMIT_EVENT']
        topic_seg_assign = os.environ['ROS_TOPIC_SEG_ASSIGN']
        topic_seg_bind = os.environ['ROS_TOPIC_SEG_BIND']
        topic_seg_confirm = os.environ['ROS_TOPIC_SEG_CONFIRM']

        # ---------- 发布 ----------
        self.pub_status = rospy.Publisher(topic_status, AxisStatus, queue_size=30)
        self.pub_rot_fb = rospy.Publisher(topic_rot_fb, RotationCmd, queue_size=10)
        self.pub_sw_fb = rospy.Publisher(topic_sw_fb, SwingCmd, queue_size=10)
        self.pub_tel_fb = rospy.Publisher(topic_tel_fb, TelescopicCmd, queue_size=10)

        # ---------- 订阅 ----------
        rospy.Subscriber(topic_seg_assign, SegAssign, self._on_seg_assign)
        rospy.Subscriber(topic_seg_bind, IntCmd, self._on_seg_bind)
        rospy.Subscriber(topic_seg_confirm, SegConfirm, self._on_seg_confirm)

        rospy.Subscriber(topic_rot_out, IntCmd, self._on_output)
        rospy.Subscriber(topic_sw_out, IntCmd, self._on_output)
        rospy.Subscriber(topic_tel_out, IntCmd, self._on_output)

        rospy.Subscriber(topic_rot_fb, RotationCmd, self._on_rotation_feedback)
        rospy.Subscriber(topic_sw_fb, SwingCmd, self._on_swing_feedback)
        rospy.Subscriber(topic_tel_fb, TelescopicCmd, self._on_telescopic_feedback)

        rospy.Subscriber(topic_ack, CmdAck, self._on_cmd_ack)
        rospy.Subscriber(topic_arrive, ArriveNotification, self._on_arrive)
        rospy.Subscriber(topic_stop, StopNotification, self._on_stop)
        rospy.Subscriber(topic_fault, AxisFault, self._on_fault)
        rospy.Subscriber(topic_limit, LimitEvent, self._on_limit)

        rospy.Timer(rospy.Duration(1.0 / self.publish_hz), self._publish_status)
        rospy.Timer(rospy.Duration(1.0 / self.cache_hz), self._publish_cached_positions)

        rospy.loginfo(
            "✅ 轴状态聚合节点启动：状态 %.1fHz，缓存位置 %.1fHz，到位保持 %.2fs",
            self.publish_hz, self.cache_hz, self.idle_confirm_s)
        self._warn_other_publishers()

    # ===================== 绑定 =====================
    def _warn_other_publishers(self):
        """启动时提示同话题的其他发布者，避免与模拟节点/真实状态字混流"""
        try:
            state = rospy.get_master().getSystemState()
            # MasterProxy 可能返回 (code, msg, value)，也可能已解包
            if isinstance(state, (list, tuple)) and len(state) == 3 \
                    and isinstance(state[0], int):
                state = state[2]
            target = os.environ['ROS_TOPIC_AXIS_STATUS'].strip('/')
            for entry in state[0]:
                topic, nodes = entry[0], entry[1]
                if str(topic).strip('/') == target:
                    names = [n for n in nodes if n != rospy.get_name()]
                    if names:
                        rospy.logwarn(
                            "⚠️ %s 已有其他发布者：%s；若固件不发状态字可共存，"
                            "但禁止再运行模拟状态节点", topic, ','.join(names))
        except Exception as exc:
            rospy.logdebug("发布者检查跳过：%s", exc)

    def _bind(self, seg, arm, source):
        """绑定 SEG/ARM 并初始化三轴状态（调用方需持锁或处于回调内）"""
        if not (0 <= seg <= 14) or not (1 <= arm <= 5):
            rospy.logwarn("⚠️ 非法绑定 SEG=%s ARM=%s，已忽略", seg, arm)
            return
        if self.bound_seg == seg and self.bound_arm == arm:
            return
        with self._lock:
            self.bound_seg, self.bound_arm = seg, arm
            self._pending_seg = None
            for axis in self.axes.values():
                axis.reset()
        rospy.logwarn(
            "🔗 轴状态绑定 SEG=%d ARM=%d（来源=%s）：按上电/人工调零约定"
            "初始化三轴基准=0、状态=假定空闲", seg, arm, source)

    def _device_id(self, local):
        return (self.bound_arm - 1) * 3 + local

    def _ensure_bound(self, module_id, device_id):
        """按消息中的 SEG/轴号补齐绑定；返回本臂局部轴号 1~3 或 None"""
        module_id = int(module_id)
        device_id = int(device_id)
        if self.bound_seg is None:
            if not (0 <= module_id <= 14 and 1 <= device_id <= 15):
                return None
            if self._pending_seg is not None and module_id != self._pending_seg:
                return None
            self._bind(module_id, (device_id - 1) // 3 + 1, "反馈推断")
        if module_id != self.bound_seg:
            return None
        local = device_id - (self.bound_arm - 1) * 3
        return local if 1 <= local <= 3 else None

    def _axis_from_msg(self, msg):
        return self._ensure_bound(msg.module_id, msg.device_id)

    def _set_state(self, axis, new_state, reason):
        if axis.state == new_state:
            return
        rospy.loginfo("[轴状态] 轴%d %s → %s（%s）",
                      self._device_id(axis.local), axis.state, new_state, reason)
        axis.state = new_state

    # ===================== 绑定回调 =====================
    def _on_seg_assign(self, msg):
        seg, arm = int(msg.seg), int(msg.arm)
        if 0 <= seg <= 14 and 1 <= arm <= 5:
            with self._lock:
                self._assign_arm[seg] = (arm, rospy.Time.now().to_sec())

    def _on_seg_confirm(self, msg):
        # 臂位确认帧（seg=15）携带 ARM，作为绑定成功时的兜底来源
        if int(msg.seg) == 15 and int(msg.result) == 0 and 1 <= int(msg.arm) <= 5:
            with self._lock:
                self._last_arm_confirm = int(msg.arm)
                self._last_arm_confirm_time = rospy.Time.now().to_sec()

    def _on_seg_bind(self, msg):
        seg = int(msg.position[0]) if msg.position else -1
        if seg < 0:
            with self._lock:
                self.bound_seg = None
                self.bound_arm = None
            rospy.logwarn("🔓 收到 SEG 解绑通知，暂停轴状态发布")
            return
        with self._lock:
            now = rospy.Time.now().to_sec()
            assigned = self._assign_arm.get(seg)
            arm = assigned[0] if assigned and now - assigned[1] <= 60.0 else None
            if arm is None and now - self._last_arm_confirm_time <= 60.0:
                arm = self._last_arm_confirm
            self._pending_seg = seg
        if arm:
            self._bind(seg, arm, "SEG绑定成功")
        else:
            rospy.logwarn("⚠️ 收到 SEG=%d 绑定但缺少 ARM，等待反馈推断", seg)

    # ===================== 指令/反馈回调 =====================
    def _mark_running(self, local, reason):
        axis = self.axes.get(local)
        if axis is None or axis.state in LOCKED_STATES:
            return
        if axis.state != STATE_RUNNING:
            axis.pre_run_state = axis.state if axis.state in IDLE_STATES else STATE_IDLE_CONFIRMED
            axis.motion_seen = False
            axis.arrive_latched = False
            self._set_state(axis, STATE_RUNNING, reason)

    def _on_output(self, msg):
        with self._lock:
            local = self._axis_from_msg(msg)
            if local:
                self._mark_running(local, "收到指令输出")

    def _on_cmd_ack(self, msg):
        with self._lock:
            local = self._axis_from_msg(msg)
            if not local:
                return
            axis = self.axes[local]
            if int(msg.result) == 0:
                self._mark_running(local, "命令应答接受")
            elif axis.state == STATE_RUNNING and not axis.motion_seen:
                self._set_state(axis, axis.pre_run_state,
                                "命令应答拒绝 result=%d" % int(msg.result))
                axis.arrive_latched = False

    def _update_position(self, local, position, source):
        axis = self.axes[local]
        now = rospy.Time.now().to_sec()
        old = axis.cache
        had_real = axis.last_real > 0.0
        axis.cache = float(position)
        axis.last_real = now
        if axis.state == STATE_RUNNING:
            axis.motion_seen = True
            return
        # 绑定后的第一帧只用于同步缓存，不据此判运动
        eps = self.motion_eps_mm if local == 3 else self.motion_eps_deg
        if had_real and axis.state in (STATE_IDLE_ASSUMED, STATE_IDLE_CONFIRMED) \
                and abs(axis.cache - old) > eps:
            self._mark_running(local, "位置变化(%s)" % source)

    def _on_rotation_feedback(self, msg):
        with self._lock:
            local = self._axis_from_msg(msg)
            if local == 1 and msg.position:
                self._update_position(local, msg.position[0], "rot")

    def _on_swing_feedback(self, msg):
        with self._lock:
            local = self._axis_from_msg(msg)
            if local == 2 and msg.position:
                self._update_position(local, msg.position[0], "swing")

    def _on_telescopic_feedback(self, msg):
        with self._lock:
            local = self._axis_from_msg(msg)
            if local == 3 and msg.position:
                self._update_position(local, msg.position[0], "tel")

    def _on_arrive(self, msg):
        with self._lock:
            local = self._axis_from_msg(msg)
            if not local:
                return
            axis = self.axes[local]
            now = rospy.Time.now().to_sec()
            axis.cache = float(msg.angle) / 100.0
            axis.last_real = now
            axis.motion_seen = True
            axis.arrive_latched = True
            axis.arrive_until = now + self.idle_confirm_s
            self._set_state(axis, STATE_ARRIVED,
                            "到位 angle=%.2f pos_error=%d" % (axis.cache, int(msg.pos_error)))

    def _on_stop(self, msg):
        with self._lock:
            local = self._axis_from_msg(msg)
            if not local:
                return
            axis = self.axes[local]
            now = rospy.Time.now().to_sec()
            reason = int(msg.stop_reason)
            if reason == 1:  # 到位
                axis.arrive_latched = True
                axis.arrive_until = now + self.idle_confirm_s
                self._set_state(axis, STATE_ARRIVED, "停止原因=到位")
            elif reason == 3:  # 指令停止
                axis.arrive_latched = False
                self._set_state(axis, STATE_IDLE_CONFIRMED, "停止原因=指令停止")
            elif reason == 2:  # 急停
                axis.estop = True
                axis.base_valid = False
                axis.arrive_latched = False
                self._set_state(axis, STATE_ESTOP, "停止原因=急停")
            elif reason == 4:  # 限位（方向由 limit_event 补充）
                axis.base_valid = False
                axis.arrive_latched = False
                self._set_state(axis, STATE_LIMIT, "停止原因=限位")
            elif reason in (5, 6):  # 故障 / 看门狗
                axis.fault = True
                axis.base_valid = False
                axis.arrive_latched = False
                self._set_state(axis, STATE_FAULT, "停止原因=%d" % reason)
            else:
                axis.arrive_latched = False
                self._set_state(axis, STATE_IDLE_CONFIRMED, "停止原因=%d" % reason)

    def _on_fault(self, msg):
        with self._lock:
            local = self._axis_from_msg(msg)
            if not local:
                return
            axis = self.axes[local]
            axis.fault = True
            axis.base_valid = False
            axis.arrive_latched = False
            self._set_state(axis, STATE_FAULT,
                            "故障 fault_bits=0x%04X detail=%d"
                            % (int(msg.fault_bits), int(msg.detail)))

    def _on_limit(self, msg):
        with self._lock:
            local = self._axis_from_msg(msg)
            if not local:
                return
            axis = self.axes[local]
            if int(msg.limit_type) == 1:
                axis.limit_up = True
            elif int(msg.limit_type) == 2:
                axis.limit_down = True
            axis.base_valid = False
            axis.arrive_latched = False
            self._set_state(axis, STATE_LIMIT,
                            "限位类型=%d" % int(msg.limit_type))

    # ===================== 发布 =====================
    def _publish_status(self, _event):
        now = rospy.Time.now()
        out = []
        with self._lock:
            if self.bound_seg is None:
                if now.to_sec() - self._last_unbound_warn > 10.0:
                    self._last_unbound_warn = now.to_sec()
                    rospy.logwarn("⚠️ 轴状态未绑定 SEG/ARM，暂不发布")
                return
            for local in (1, 2, 3):
                axis = self.axes[local]
                if axis.state == STATE_ARRIVED and now.to_sec() >= axis.arrive_until:
                    self._set_state(axis, STATE_IDLE_CONFIRMED, "到位保持结束")
                msg = AxisStatus()
                msg.header = Header(stamp=now)
                msg.module_id = self.bound_seg
                msg.device_id = self._device_id(local)
                msg.status_bits = axis.bits()
                msg.axis_state = axis.axis_state_code()
                msg.base_valid = 1 if axis.base_valid else 0
                out.append(msg)
        for msg in out:
            self.pub_status.publish(msg)

    def _publish_cached_positions(self, _event):
        now = rospy.Time.now()
        batch = []
        with self._lock:
            if self.bound_seg is None:
                return
            for local in (1, 2, 3):
                axis = self.axes[local]
                if axis.state not in IDLE_STATES:
                    continue
                if now.to_sec() - axis.last_real < self.cache_hold_off_s:
                    continue
                batch.append((local, self._device_id(local), float(axis.cache)))
        if not batch:
            return
        for local, device_id, value in batch:
            header = Header(stamp=now)
            if local == 1:
                self.pub_rot_fb.publish(RotationCmd(
                    header=header, module_id=self.bound_seg,
                    device_id=device_id, position=[value]))
            elif local == 2:
                self.pub_sw_fb.publish(SwingCmd(
                    header=header, module_id=self.bound_seg,
                    device_id=device_id, position=[value]))
            else:
                self.pub_tel_fb.publish(TelescopicCmd(
                    header=header, module_id=self.bound_seg,
                    device_id=device_id, position=[value]))


if __name__ == "__main__":
    try:
        AxisStatusAggregator()
        rospy.spin()
    except rospy.ROSInterruptException:
        rospy.loginfo("❌ 轴状态聚合节点已停止")
    except Exception as exc:
        rospy.logerr("❌ 轴状态聚合节点异常：%s", exc)
        raise
