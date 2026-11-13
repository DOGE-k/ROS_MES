#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模块确认节点 V2.2 —— 组号+臂位会话式绑定（UID 宣告 + SEG/ARM 双确认 + 状态复核）

方案来源：《机械臂模块确认命令》（STM32F407 三电机机械臂模块）
核心规则：
  - 1 块 F407 = 1 个机械臂 = 3 个电机；5 个机械臂 = 1 组（SEG 0~14，组内臂位 ARM 1~5）
  - 组号+臂位共同决定本臂负责的 3 个全局 AXIS：起始AXIS = (ARM-1)*3+1
  - F407 上电即未绑定（绑定仅存 RAM），周期发送 UID 宣告；每次上电必须重新绑定
  - 绑定帧 0x15BC0020：UID56 + (SEG<<3)|(ARM-1)
  - 绑定成功后模块回两帧：0x15BC0050 组号确认（Result=0）+ 0x15BC0060 臂位确认，
    两帧均核对通过才判定握手成功
  - 可选状态复核：发 0x00000020 查询，收 0x00002060+(SEG<<18) 应答，
    核对电机存在/就绪掩码（0x07）与模块状态位

接口（与后端原契约保持一致）：
  输入：/control/module_cmd (IntCmd)
        module_id 原样透传（后端业务模块号，用于回执匹配）
        device_id 固定 0
        position = [100, seg, arm]：100=触发握手，seg=组号 0~14，arm=组内臂位 1~5
  输出：/hardware/module_confirm_success（position=[100]）
        /hardware/web_module_cmd（position=[1]，失败，后端回 HTTP 502）

状态机（同一时间只确认一台，新指令会取消进行中的握手）：
  IDLE → WAIT_ANNOUNCE →(收到宣告，发绑定帧)→ WAIT_CONFIRM
       →(组号+臂位双确认通过)→ [STATUS_VERIFY] → IDLE + (SEG,ARM) READY
  等待宣告超时 / 双确认重试 max_retry 次无应答 / 复核电机不就绪 → 失败回执 → IDLE
"""
import os
import threading

import rospy
from std_msgs.msg import Header
from robot_control_backend.msg import IntCmd, UidAnnounce, SegAssign, SegConfirm, ModuleStatus

# 握手状态
IDLE, WAIT_ANNOUNCE, WAIT_CONFIRM, WAIT_STATUS = 0, 1, 2, 3

# 三电机机械臂正常掩码：电机1~3 存在且就绪
MOTOR_MASK_OK = 0x07


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
        rospy.loginfo("✅ 模块确认节点已从 rob_arm.env 加载配置")


class ModuleSessionConfirmer:
    """组号+臂位会话式绑定：宣告 → 绑定 → 双确认核对 → 状态复核 → READY"""

    RESULT_SUCCESS = 100   # 后端契约：position[0]==100 成功
    RESULT_FAILED = 1      # 后端契约：position[0]==1 失败（HTTP 502）

    def __init__(self):
        load_env_config()
        rospy.init_node("module_confirme_node")

        # 参数全部只读 rob_arm.env，无硬编码默认值
        self.wait_announce_s = float(os.environ['MODULE_CONFIRM_WAIT_ANNOUNCE_S'])
        self.ack_timeout_s = float(os.environ['MODULE_CONFIRM_ACK_TIMEOUT_S'])
        self.max_retry = int(os.environ['MODULE_CONFIRM_MAX_RETRY'])
        # 状态复核：绑定双确认通过后发状态查询，核对电机掩码；查询仅复核不替代绑定
        self.status_verify = os.environ['MODULE_CONFIRM_STATUS_VERIFY'].lower() == 'true'
        self.status_timeout_s = float(os.environ['MODULE_CONFIRM_STATUS_TIMEOUT_S'])

        # 话题全部只读 rob_arm.env
        self.pub_assign = rospy.Publisher(
            os.environ['ROS_TOPIC_SEG_ASSIGN'], SegAssign, queue_size=10)
        self.pub_success = rospy.Publisher(
            os.environ['ROS_TOPIC_MODULE_CONFIRM_SUCCESS'], IntCmd, queue_size=10)
        self.pub_failed = rospy.Publisher(
            os.environ['ROS_TOPIC_MODULE_CONFIRM_FAILED'], IntCmd, queue_size=10)
        # 握手成功/失效后向 hardware_node 同步 SEG 绑定，用于运动帧动态寻址
        self.pub_seg_bind = rospy.Publisher(
            os.environ['ROS_TOPIC_SEG_BIND'], IntCmd, queue_size=10)
        # 状态复核查询（hardware_node 桥接为 CAN 帧 0x00000020）
        self.pub_status_query = rospy.Publisher(
            os.environ['ROS_TOPIC_MODULE_STATUS_QUERY'], IntCmd, queue_size=10)
        rospy.Subscriber(os.environ['ROS_TOPIC_MODULE_CMD'], IntCmd, self.cb_module_cmd)
        rospy.Subscriber(os.environ['ROS_TOPIC_UID_ANNOUNCE'], UidAnnounce, self.cb_announce)
        rospy.Subscriber(os.environ['ROS_TOPIC_SEG_CONFIRM'], SegConfirm, self.cb_confirm)
        rospy.Subscriber(os.environ['ROS_TOPIC_MODULE_STATUS'], ModuleStatus, self.cb_status)

        self.lock = threading.Lock()
        self.state = IDLE
        # 当前握手上下文：{req_module_id, seg, arm, uid56, retries, deadline,
        #                  seg_ok, arm_ok, status_token}
        self.current = None
        # 会话表：(seg, arm) -> {"uid56", "module_id", "ts"}；仅本次运行有效，断电需重新握手
        self.session = {}
        self.status_token_seq = 0

        rospy.Timer(rospy.Duration(0.05), self._check_timeout)
        rospy.loginfo("✅ 模块确认节点已启动（组号+臂位绑定：等宣告 %.1fs / 双确认 %.2fs × %d 次 / 复核=%s）",
                      self.wait_announce_s, self.ack_timeout_s, self.max_retry,
                      "开 %.2fs" % self.status_timeout_s if self.status_verify else "关")

    # ================= 入口：后端模块确认指令 =================
    def cb_module_cmd(self, msg):
        """/control/module_cmd：position=[100, seg, arm]，seg=组号 0~14，arm=组内臂位 1~5"""
        if not msg.position or int(msg.position[0]) != 100:
            rospy.logwarn("⚠️ 模块确认指令 position[0] 应为 100（握手触发），收到 %s，已忽略",
                          list(msg.position))
            return
        if len(msg.position) < 3:
            self._publish_result(self.pub_failed, int(msg.module_id),
                                 self.RESULT_FAILED, "缺少组号/臂位：position 需为 [100, seg(0~14), arm(1~5)]")
            return
        seg, arm = int(msg.position[1]), int(msg.position[2])
        if not (0 <= seg <= 14):
            self._publish_result(self.pub_failed, int(msg.module_id),
                                 self.RESULT_FAILED, f"组号 {seg} 非法（0~14）")
            return
        if not (1 <= arm <= 5):
            self._publish_result(self.pub_failed, int(msg.module_id),
                                 self.RESULT_FAILED, f"臂位 {arm} 非法（1~5）")
            return

        with self.lock:
            if self.state != IDLE:
                rospy.logwarn("↪️ 取消 SEG%d/臂%d 进行中的握手，切换至 SEG%d/臂%d",
                              self.current["seg"] if self.current else -1,
                              self.current["arm"] if self.current else -1, seg, arm)
            # 进入等待宣告（操作员此时给目标臂上电；同一时间只给一台未绑定臂上电）
            self.current = {
                "req_module_id": int(msg.module_id),   # 后端业务模块号，回执原样返回
                "seg": seg,
                "arm": arm,
                "uid56": None,
                "retries": 0,
                "deadline": rospy.Time.now() + rospy.Duration(self.wait_announce_s),
                "seg_ok": False,
                "arm_ok": False,
                "status_token": 0,
                # 等待宣告期间的状态探测 Token：模块已绑定时不会再广播宣告，
                # 用状态查询确认可避免每次都空等 wait_announce_s
                "probe_token": 0,
            }
            self.status_token_seq = (self.status_token_seq + 1) & 0xFFFF
            self.current["probe_token"] = self.status_token_seq
            probe_token = self.status_token_seq
            self.state = WAIT_ANNOUNCE
        rospy.loginfo("🔌 开始确认 SEG%d 臂%d（占用全局AXIS %d~%d），请给该臂上电，等待 UID 宣告（%.1fs）",
                      seg, arm, (arm - 1) * 3 + 1, (arm - 1) * 3 + 3, self.wait_announce_s)
        # 同时探测：已绑定模块（绑定仅存 RAM，只有断电重启才重新宣告）直接走状态复核
        self._send_status_query(probe_token)

    # ================= 宣告处理 =================
    def cb_announce(self, msg):
        """收到 UID 宣告：握手中则立即绑定；否则检测"已 READY 臂重新上电" """
        with self.lock:
            if self.state == WAIT_ANNOUNCE:
                self.current["uid56"] = int(msg.uid56)
                self._send_assign_locked()
                self.current["retries"] = 1
                self.current["deadline"] = rospy.Time.now() + rospy.Duration(self.ack_timeout_s)
                self.state = WAIT_CONFIRM
                rospy.loginfo("📢 收到宣告：UID56=%X（槽%d）→ 绑定 SEG=%d ARM=%d",
                              msg.uid56, msg.slot, self.current["seg"], self.current["arm"])
                return
            # 非握手期间收到宣告：若为已 READY 臂的 UID，说明该臂断电重启（绑定仅存 RAM），会话失效
            stale = [k for k, rec in self.session.items() if rec["uid56"] == int(msg.uid56)]
            for k in stale:
                rec = self.session.pop(k)
                rospy.logwarn("🔌 SEG%d 臂%d 重新上电，绑定已失效，需重新确认", k[0], k[1])
                # 解绑该业务模块的 SEG 路由，避免运动帧继续发往已重启（未绑定）的臂
                self._publish_seg_bind(rec.get("module_id", -1), -1)
            if not stale:
                rospy.loginfo("📢 收到未请求宣告：UID56=%X（槽%d），如需启用请下发模块确认指令",
                              msg.uid56, msg.slot)

    # ================= 绑定双确认处理 =================
    def cb_confirm(self, msg):
        """绑定确认帧（组号 0x15BC0050 / 臂位 0x15BC0060）：两帧均核对通过才算绑定成功"""
        with self.lock:
            if self.state != WAIT_CONFIRM or self.current is None:
                return
            cur = self.current
            if int(msg.uid56) != cur["uid56"]:
                rospy.logwarn("⚠️ 确认帧 UID56=%X 与期望 %X 不符，忽略", msg.uid56, cur["uid56"])
                return
            if int(msg.arm) == 0:
                # 组号确认：核对 SEG、Result=0
                if int(msg.seg) != cur["seg"]:
                    rospy.logwarn("⚠️ 组号确认 SEG=%d 与期望 %d 不符，忽略", msg.seg, cur["seg"])
                    return
                if int(msg.result) != 0:
                    rospy.logwarn("⚠️ 设备绑定失败 Result=%d，按重试处理", msg.result)
                    self._retry_or_fail_locked("设备返回 Result=%d" % msg.result)
                    return
                cur["seg_ok"] = True
                rospy.loginfo("🤝 组号确认通过：UID56=%X SEG=%d", msg.uid56, msg.seg)
            else:
                # 臂位确认：核对 ARM 与起始AXIS=(ARM-1)*3+1
                if int(msg.arm) != cur["arm"]:
                    rospy.logwarn("⚠️ 臂位确认 ARM=%d 与期望 %d 不符，忽略", msg.arm, cur["arm"])
                    return
                expect_base = (cur["arm"] - 1) * 3 + 1
                if int(msg.axis_base) != expect_base:
                    rospy.logwarn("⚠️ 臂位确认 AxisBase=%d 与期望 %d 不符，忽略",
                                  msg.axis_base, expect_base)
                    return
                cur["arm_ok"] = True
                rospy.loginfo("🤝 臂位确认通过：UID56=%X ARM=%d AxisBase=%d",
                              msg.uid56, msg.arm, msg.axis_base)
            if not (cur["seg_ok"] and cur["arm_ok"]):
                return
            # 双确认通过：可选状态复核
            if self.status_verify:
                self.status_token_seq = (self.status_token_seq + 1) & 0xFFFF
                cur["status_token"] = self.status_token_seq
                cur["deadline"] = rospy.Time.now() + rospy.Duration(self.status_timeout_s)
                self.state = WAIT_STATUS
                token = cur["status_token"]
            else:
                self._handshake_done_locked()
                return
        if self.status_verify:
            self._send_status_query(token)
            rospy.loginfo("🔎 双确认通过，发状态查询复核（Token=0x%04X，%.2fs）",
                          token, self.status_timeout_s)

    # ================= 状态复核 =================
    def cb_status(self, msg):
        """状态应答：核对 Token、SEG/ARM/AxisBase、电机存在/就绪掩码与模块状态位"""
        with self.lock:
            if self.current is None:
                return
            cur = self.current
            # 快速通道：等待宣告期间若状态应答表明该臂已绑定且就绪，直接判定握手成功
            if self.state == WAIT_ANNOUNCE:
                if int(msg.module_id) != cur["seg"] or int(msg.token) != cur["probe_token"]:
                    return
                if int(msg.seg) != cur["seg"] or int(msg.arm) != cur["arm"] \
                        or int(msg.axis_base) != (cur["arm"] - 1) * 3 + 1:
                    return
                if int(msg.exist_mask) != MOTOR_MASK_OK or int(msg.ready_mask) != MOTOR_MASK_OK:
                    return
                if (int(msg.module_state) & 0x03) != 0x03:
                    return
                rospy.loginfo("⚡ SEG%d 臂%d 已绑定且电机就绪（状态应答 Token=0x%04X），跳过 UID 宣告等待",
                              cur["seg"], cur["arm"], cur["probe_token"])
                self._handshake_done_locked()
                return
            if self.state != WAIT_STATUS:
                return
            cur = self.current
            if int(msg.module_id) != cur["seg"] or int(msg.token) != cur["status_token"]:
                return
            if int(msg.seg) != cur["seg"] or int(msg.arm) != cur["arm"] \
                    or int(msg.axis_base) != (cur["arm"] - 1) * 3 + 1:
                reason = ("状态应答绑定信息不符（SEG=%d ARM=%d AxisBase=%d，期望 SEG=%d ARM=%d AxisBase=%d）"
                          % (msg.seg, msg.arm, msg.axis_base,
                             cur["seg"], cur["arm"], (cur["arm"] - 1) * 3 + 1))
            elif int(msg.exist_mask) != MOTOR_MASK_OK or int(msg.ready_mask) != MOTOR_MASK_OK:
                reason = ("电机未全部就绪（存在=0x%02X 就绪=0x%02X，期望均为 0x07）"
                          % (msg.exist_mask, msg.ready_mask))
            elif not (int(msg.module_state) & 0x03) == 0x03:
                reason = "模块状态异常（state=0x%02X，bit0已绑定/bit1允许运动应均为1）" % msg.module_state
            else:
                reason = None
            if reason is None:
                self._handshake_done_locked()
                return
            cur = self.current
            self.current = None
            self.state = IDLE
            seg, arm = cur["seg"], cur["arm"]
        self._publish_result(self.pub_failed, cur["req_module_id"], self.RESULT_FAILED,
                             "SEG%d 臂%d 状态复核失败：%s" % (seg, arm, reason))

    def _send_status_query(self, token):
        """发状态查询（position=[token]，hardware_node 桥接为 0x00000020）"""
        m = IntCmd()
        m.header = Header(stamp=rospy.Time.now())
        m.module_id = 0
        m.device_id = 0
        m.position = [int(token)]
        self.pub_status_query.publish(m)

    # ================= 超时与重试 =================
    def _check_timeout(self, _event):
        with self.lock:
            if self.state == IDLE or self.current is None:
                return
            if rospy.Time.now() < self.current["deadline"]:
                return
            if self.state == WAIT_ANNOUNCE:
                cur = self.current
                self.current = None
                self.state = IDLE
                text = "等待 UID 宣告超时（%.1fs）：请检查该臂电源、CAN 接线" % self.wait_announce_s
            elif self.state == WAIT_CONFIRM:
                # 双确认超时：重发绑定帧，最多 max_retry 次
                if self.current["retries"] < self.max_retry:
                    rospy.logwarn("⏳ 绑定双确认超时（组号=%s 臂位=%s），重发第 %d/%d 次",
                                  "✓" if self.current["seg_ok"] else "✗",
                                  "✓" if self.current["arm_ok"] else "✗",
                                  self.current["retries"] + 1, self.max_retry)
                    self.current["retries"] += 1
                    self.current["seg_ok"] = False
                    self.current["arm_ok"] = False
                    self._send_assign_locked()
                    self.current["deadline"] = rospy.Time.now() + rospy.Duration(self.ack_timeout_s)
                    return
                cur = self.current
                self.current = None
                self.state = IDLE
                text = "绑定确认 %d 次无应答：请检查该臂电源、CAN 接线、UID 是否变化" % self.max_retry
            else:  # WAIT_STATUS 超时：查询仅复核不替代绑定，绑定已成立，记警告按成功处理
                cur = self.current
                reason = "状态查询超时（%.2fs），绑定双确认已通过，按成功处理（状态未复核）" % self.status_timeout_s
                rospy.logwarn("⏰ SEG%d 臂%d %s", cur["seg"], cur["arm"], reason)
                self._handshake_done_locked()
                return
        self._publish_result(self.pub_failed, cur["req_module_id"], self.RESULT_FAILED,
                             "SEG%d 臂%d 握手失败：%s" % (cur["seg"], cur["arm"], text))

    def _retry_or_fail_locked(self, reason):
        """设备回了非 0 组号确认：按一次失败重试处理（持锁调用）"""
        if self.current["retries"] < self.max_retry:
            self.current["retries"] += 1
            self.current["seg_ok"] = False
            self.current["arm_ok"] = False
            self._send_assign_locked()
            self.current["deadline"] = rospy.Time.now() + rospy.Duration(self.ack_timeout_s)
        else:
            cur = self.current
            self.current = None
            self.state = IDLE
            self._publish_result(self.pub_failed, cur["req_module_id"], self.RESULT_FAILED,
                                 "SEG%d 臂%d 握手失败：%s（重试 %d 次）"
                                 % (cur["seg"], cur["arm"], reason, self.max_retry))

    def _send_assign_locked(self):
        """发绑定请求（持锁调用）：hardware_node 桥接为 CAN 帧 0x15BC0020"""
        m = SegAssign()
        m.header = Header(stamp=rospy.Time.now())
        m.target_uid56 = self.current["uid56"]
        m.seg = self.current["seg"]
        m.arm = self.current["arm"]
        self.pub_assign.publish(m)

    def _handshake_done_locked(self):
        """握手成功收尾（持锁调用）：登记会话表、回执成功、同步 SEG 绑定"""
        cur = self.current
        self.session[(cur["seg"], cur["arm"])] = {
            "uid56": cur["uid56"], "module_id": cur["req_module_id"],
            "ts": rospy.Time.now().to_sec(),
        }
        seg, arm, req_mid, uid56 = cur["seg"], cur["arm"], cur["req_module_id"], cur["uid56"]
        self.current = None
        self.state = IDLE
        uid_desc = "UID56=%X" % uid56 if uid56 is not None else "状态复核确认（无 UID 宣告）"
        self._publish_result(self.pub_success, req_mid, self.RESULT_SUCCESS,
                             "SEG%d 臂%d（AXIS %d~%d）握手成功 %s"
                             % (seg, arm, (arm - 1) * 3 + 1, (arm - 1) * 3 + 3, uid_desc))
        # 通知 hardware_node：该业务模块的运动帧改用 SEG 寻址
        self._publish_seg_bind(req_mid, seg)

    # ================= 回执（保持后端契约） =================
    def _publish_seg_bind(self, module_id, seg):
        """SEG 绑定通知：position=[seg] 绑定，position=[-1] 解绑（hardware_node 订阅）"""
        if int(module_id) < 0:
            return
        m = IntCmd()
        m.header = Header(stamp=rospy.Time.now())
        m.module_id = int(module_id)
        m.device_id = 0
        m.position = [int(seg)]
        self.pub_seg_bind.publish(m)

    def _publish_result(self, publisher, req_module_id, result_code, log_text):
        """成功/失败回执：module_id 原样返回请求值，device_id=0，position=[100|1]"""
        m = IntCmd()
        m.header = Header(stamp=rospy.Time.now())
        m.module_id = req_module_id
        m.device_id = 0
        m.position = [result_code]
        publisher.publish(m)
        if result_code == self.RESULT_SUCCESS:
            rospy.loginfo("[模块确认成功] %s", log_text)
        else:
            rospy.logwarn("[模块确认失败] %s", log_text)


if __name__ == "__main__":
    try:
        node = ModuleSessionConfirmer()
        rospy.spin()
    except rospy.ROSInterruptException:
        rospy.loginfo("❌ 模块确认节点停止")
    except Exception as e:
        rospy.logerr("❌ 模块确认节点异常: %s" % str(e))
