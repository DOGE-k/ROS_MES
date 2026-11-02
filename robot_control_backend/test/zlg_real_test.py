#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""真机 CAN 联通性测试工具（ZLG USBCAN-II 直连，不依赖 ROS）

执行顺序（已按「先确认模块、真机锁定 ID 后再下发命令」调整）：

    1. 急停解除      ID=0x00000004  DLC=1  DATA=01
    2. 模块确认      监听 UID 宣告(0x15BC0080+槽×4)
                     → 下发绑定 0x15BC0020  UID56(7B) + (SEG<<3)|(ARM-1)
                     → 等组号确认 0x15BC0050（Result=0）+ 臂位确认 0x15BC0060
                     → 可选状态复核 0x00000020 查询 / 0x00002060+(SEG<<18) 应答
    3. 下发命令      运动帧按协商到的 SEG 寻址，AXIS = (ARM-1)*3 + 本地轴号

未完成模块确认时默认拒绝下发运动指令；如确需跳过，显式加 --skip-confirm。

用法示例：
    # 只做模块确认，看真机是否锁定 ID
    python3 zlg_real_test.py confirm --seg 0 --arm 1

    # 摆动轴(本地2 → 全局2) 相对 +1.00°
    python3 zlg_real_test.py move 2 100 --seg 0 --arm 1

    # 伸缩轴(本地3 → 全局3) 相对 +2.00mm
    python3 zlg_real_test.py move 3 200 --seg 0 --arm 1

    # 上电后回零
    python3 zlg_real_test.py home 2 --seg 0 --arm 1

    # 单轴停止（安全，不锁系统）
    python3 zlg_real_test.py stop 2

    # 超位故障复位（Result=4 时用；省略轴号则复位本臂三轴）
    python3 zlg_real_test.py reset 2
    python3 zlg_real_test.py reset

    # 模块级急停（只停本组三电机，可用 0x00000004 解除）
    python3 zlg_real_test.py modstop

    # 确认后依次探测本地 1~3 轴
    python3 zlg_real_test.py probe --axes 3 --delta 100

    # 只监听总线（不做确认，不发命令）
    python3 zlg_real_test.py listen 5

安全说明：
    * 急停广播 0x00000000 会锁死下位机，只能重新上电恢复，
      因此本工具默认不发送；确实需要时必须显式加 --i-know-risk。
    * 连续下发运动指令会触发下位机 result=1(忙)，指令之间请间隔 2~3 秒，
      或用 --wait 增大等待。
    * 下位机重新上电后绑定失效（绑定仅存 RAM），必须重新执行模块确认。
"""
import argparse
import ctypes
import os
import struct
import sys
import time

# ==================== 配置 ====================
LIB_PATH = os.environ.get("ZLG_LIBUSB_PATH", "/home/yang/.local/lib/usbcan/libusbcan.so")
DEV_TYPE = 4  # USBCAN-II
DEV_IND, CAN_IND = 0, 0

# ==================== 急停相关固定帧 ====================
EMERGENCY_STOP_ID = 0x00000000       # ⚠️ 广播急停：锁死全系统，需重新上电
EMERGENCY_RELEASE_ID = 0x00000004    # 急停解除（清全局 + 各轴急停锁存，不清超位故障）
EMERGENCY_RELEASE_DATA = bytes([0x01])
MODULE_STOP_BASE = 0x00000008        # 模块级急停：ID = 0x00000008 + (SEG<<18)，只停本组三电机

# ==================== 超位故障复位 ====================
FAULT_RESET_BASE = 0x04402114        # ID = 0x04402114 + (SEG<<18) + ((AXIS-1)<<8)，DLC=1 DATA=01
FAULT_RESET_ACK_PREFIX = 0x04802154  # 复位应答 = 0x04802154 + (SEG<<18) + ((AXIS-1)<<8)，DATA=05 00 00

# ==================== 模块确认（领号段）协议 ====================
UID_FRAME_BASE = 0x15BC0000          # 领号段基址（掩码匹配 0x15BC00xx）
UID_ASSIGN_ID = 0x15BC0020           # 下行：绑定 SEG+ARM，payload=UID56(7B)+(SEG<<3)|(ARM-1)
UID_CONFIRM_ID = 0x15BC0050          # 上行：组号确认，data[7]=(SEG<<4)|Result
UID_ARM_CONFIRM_ID = 0x15BC0060      # 上行：臂位确认，data[7]=(ARM<<4)|AxisBase
UID_ANNOUNCE_BASE = 0x15BC0080       # 上行：未编号宣告基址，16 槽步长 4
UID_ANNOUNCE_MAX = 0x15BC00BC
UID_FRAME_MASK = 0x1FFFFF00

STATUS_QUERY_ID = 0x00000020         # 下行：广播状态查询，DLC=4 Token 大端
STATUS_RESP_BASE = 0x00002060        # 上行：状态应答 = 0x00002060 + (SEG<<18)
STATUS_RESP_MASK = 0x1FC3FFFF
MOTOR_MASK_OK = 0x07                 # 三电机全部存在/就绪

# ==================== 29 位 ID 位域 ====================
PRI_MOTION, PRI_EVENT = 1, 2
GRP_MOTION_CMD, GRP_MOTION_FB, GRP_EVENT = 1, 2, 3
DIR_DOWN, DIR_PERIODIC, DIR_EVENT = 0, 1, 2
MSG_MOTION, MSG_STOP, MSG_HOME = 1, 3, 4

RESULT_TEXT = {
    0: "OK 接受",
    1: "轴忙（等当前电机停止）",
    2: "组号/臂位未绑定（需重新绑定）",
    3: "参数越界（检查目标值）",
    4: "轴超位故障锁存（需 0x0440xx14 复位）",
    5: "急停锁存（先发 0x00000004 解除）",
}

STOP_REASON_TEXT = {1: "正常到位", 2: "急停", 4: "限位/超位"}
LIMIT_TEXT = {1: "上限位", 2: "下限位"}


def build_id(pri, grp, seg=0, node=1, axis=0, direction=0, msg=0):
    """拼 29 位扩展帧 ID：PRI(3)|GRP(4)|SEG(4)|NODE(5)|AXIS(5)|DIR(2)|MSG(4)|RSV(2)"""
    return (((pri & 0x7) << 26) | ((grp & 0xF) << 22) | ((seg & 0xF) << 18) |
            ((node & 0x1F) << 13) | ((axis & 0x1F) << 8) |
            ((direction & 0x3) << 6) | ((msg & 0xF) << 2))


def parse_id(can_id):
    aid = can_id & 0x1FFFFFFF
    return {
        "pri": (aid >> 26) & 0x7,
        "grp": (aid >> 22) & 0xF,
        "seg": (aid >> 18) & 0xF,
        "node": (aid >> 13) & 0x1F,
        "axis": (aid >> 8) & 0x1F,
        "dir": (aid >> 6) & 0x3,
        "msg": (aid >> 2) & 0xF,
    }


# ==================== ZLG 驱动 ctypes 定义 ====================
class _INIT_CONFIG(ctypes.Structure):
    _fields_ = [("AccCode", ctypes.c_uint32), ("AccMask", ctypes.c_uint32),
                ("Reserved", ctypes.c_uint32), ("Filter", ctypes.c_ubyte),
                ("Timing0", ctypes.c_ubyte), ("Timing1", ctypes.c_ubyte),
                ("Mode", ctypes.c_ubyte)]


class _CAN_OBJ(ctypes.Structure):
    _fields_ = [("ID", ctypes.c_uint32), ("TimeStamp", ctypes.c_uint32),
                ("TimeFlag", ctypes.c_ubyte), ("SendType", ctypes.c_ubyte),
                ("RemoteFlag", ctypes.c_ubyte), ("ExternFlag", ctypes.c_ubyte),
                ("DataLen", ctypes.c_ubyte), ("Data", ctypes.c_ubyte * 8),
                ("Reserved", ctypes.c_ubyte * 3)]


_BAUD_TIMING = {
    1000000: 0x1400, 500000: 0x1C00, 250000: 0x1C01,
    125000: 0x1C03, 100000: 0x1C07, 50000: 0x1C0F,
}


class ZLG:
    """ZLG USBCAN-II 最小封装，负责 open/send/recv/close"""

    def __init__(self, channel=CAN_IND, bitrate=500000):
        self.channel = channel
        self.bitrate = bitrate
        if not os.path.exists(LIB_PATH):
            sys.exit(f"❌ 找不到驱动库：{LIB_PATH}")
        self.lib = ctypes.CDLL(LIB_PATH)
        self._open()

    def _open(self):
        if self.lib.VCI_OpenDevice(DEV_TYPE, DEV_IND, 0) != 1:
            sys.exit("❌ VCI_OpenDevice 失败：检查 USB 是否插好、udev 权限是否配置"
                     "（0471:1200 MODE=0666），必要时在物理宿主机重新插拔")
        timing = _BAUD_TIMING.get(self.bitrate, 0x1C00)
        cfg = _INIT_CONFIG()
        cfg.AccCode, cfg.AccMask, cfg.Reserved = 0, 0xFFFFFFFF, 0
        cfg.Filter, cfg.Mode = 1, 0
        cfg.Timing0, cfg.Timing1 = timing & 0xFF, timing >> 8
        # 部分固件首次 InitCAN 会失败，重试一次
        self.lib.VCI_InitCAN(DEV_TYPE, DEV_IND, self.channel, ctypes.byref(cfg))
        if self.lib.VCI_InitCAN(DEV_TYPE, DEV_IND, self.channel, ctypes.byref(cfg)) != 1:
            sys.exit("❌ VCI_InitCAN 失败")
        if self.lib.VCI_StartCAN(DEV_TYPE, DEV_IND, self.channel) != 1:
            sys.exit("❌ VCI_StartCAN 失败")
        print(f"✅ CAN 已启动  channel={self.channel}  bitrate={self.bitrate}")

    def send(self, can_id, data):
        obj = _CAN_OBJ()
        obj.ID = can_id & 0x1FFFFFFF
        obj.SendType, obj.RemoteFlag, obj.ExternFlag = 0, 0, 1
        obj.DataLen = len(data)
        for i, b in enumerate(data):
            obj.Data[i] = b
        ret = self.lib.VCI_Transmit(DEV_TYPE, DEV_IND, self.channel, ctypes.byref(obj), 1)
        if ret != 1:
            print(f"  ❌ 发送失败 ret={ret} id=0x{can_id:08X}")
            print("     常见原因：① 下位机未上电，总线无 ACK；② CAN_H/CAN_L 接反或断开；"
                  "③ 缺少 120Ω 终端电阻；④ 适配器 USB 卡死（需在物理宿主机重新插拔）")
            return False
        print(f"  → TX  0x{can_id:08X}  DLC={len(data)}  {data.hex(' ')}")
        return True

    def drain(self):
        """清空接收缓冲，避免历史帧干扰"""
        arr = (_CAN_OBJ * 100)()
        while self.lib.VCI_GetReceiveNum(DEV_TYPE, DEV_IND, self.channel) > 0:
            self.lib.VCI_Receive(DEV_TYPE, DEV_IND, self.channel, ctypes.byref(arr), 100, 20)

    def collect(self, seconds=1.0, quiet=False):
        """收集 seconds 秒内的所有帧，返回 [(id, data), ...]"""
        frames = []
        deadline = time.time() + seconds
        arr = (_CAN_OBJ * 100)()
        while time.time() < deadline:
            n = self.lib.VCI_GetReceiveNum(DEV_TYPE, DEV_IND, self.channel)
            if n > 0:
                got = self.lib.VCI_Receive(DEV_TYPE, DEV_IND, self.channel,
                                           ctypes.byref(arr), min(n, 100), 50)
                for i in range(got):
                    m = arr[i]
                    frames.append((m.ID & 0x1FFFFFFF, bytes(m.Data[:m.DataLen])))
            time.sleep(0.01)
        if not quiet:
            for cid, data in frames:
                print_frame(cid, data)
        return frames

    def close(self):
        try:
            self.lib.VCI_ResetCAN(DEV_TYPE, DEV_IND, self.channel)
        except Exception:
            pass
        try:
            self.lib.VCI_CloseDevice(DEV_TYPE, DEV_IND)
        except Exception:
            pass


# ==================== 帧解析与打印 ====================
_LAST_ANGLE = {}


def print_frame(can_id, data):
    info = parse_id(can_id)
    grp, msg, axis, direction = info["grp"], info["msg"], info["axis"], info["dir"]
    tail = f"  ← RX  0x{can_id:08X}  {data.hex(' ')}"

    # 领号段：模块确认相关帧
    if (can_id & UID_FRAME_MASK) == UID_FRAME_BASE and len(data) >= 8:
        if UID_ANNOUNCE_BASE <= can_id <= UID_ANNOUNCE_MAX:
            print(f"{tail}   [UID宣告] 槽{(can_id - UID_ANNOUNCE_BASE) // 4} "
                  f"类型=0x{data[0]:02X} UID56=0x{int.from_bytes(data[1:8], 'big'):014X}")
            return
        if can_id == UID_CONFIRM_ID:
            print(f"{tail}   [组号确认] UID56=0x{int.from_bytes(data[0:7], 'big'):014X} "
                  f"SEG={data[7] >> 4} Result={data[7] & 0xF}")
            return
        if can_id == UID_ARM_CONFIRM_ID:
            print(f"{tail}   [臂位确认] UID56=0x{int.from_bytes(data[0:7], 'big'):014X} "
                  f"ARM={data[7] >> 4} AxisBase={data[7] & 0xF}")
            return
    # 系统帧（GRP=0）：急停/解除/模块急停
    if grp == 0 and len(data) >= 1:
        label = {0: "全局急停", 1: "急停解除", 2: "模块急停", 3: "单轴停止"}.get(msg, "系统帧")
        print(f"{tail}   [{label}] SEG={info['seg']} DATA={data.hex(' ')}")
        return
    # 运动反馈：CmdAck（data[0]=5 为超位故障复位应答）
    if grp == GRP_MOTION_FB and msg == 5 and len(data) >= 3:
        if data[0] == 5:
            print(f"{tail}   [故障复位应答] axis={axis} Result={data[1]} Detail={data[2]}")
            return
        result = data[1]
        print(f"{tail}   [CmdAck] axis={axis} result={result} "
              f"({RESULT_TEXT.get(result, '未知')}) detail={data[2]}")
        return
    # 运动反馈：周期角度（只在数值变化时打印，避免刷屏）
    if grp == GRP_MOTION_FB and msg == 0 and direction == DIR_PERIODIC and len(data) >= 4:
        angle = struct.unpack_from(">i", data, 0)[0] / 100.0
        if _LAST_ANGLE.get(axis) == angle:
            return
        _LAST_ANGLE[axis] = angle
        unit = "mm" if local_axis_is_telescopic(axis) else "°"
        print(f"{tail}   [角度] axis={axis} {angle:.2f}{unit}")
        return
    # 事件：到位通知 DLC=8
    if grp == GRP_EVENT and msg == 0 and direction == DIR_EVENT and len(data) >= 8:
        angle, pos_err = struct.unpack_from(">ih", data, 0)
        print(f"{tail}   [到位] axis={axis} angle={angle / 100.0:.2f} "
              f"pos_err={pos_err} status={data[6]} flags={data[7]}")
        return
    # 事件：停止通知 DLC=2（0x08C0xx84）
    if grp == GRP_EVENT and msg == 1 and len(data) >= 2:
        reason = data[0]
        print(f"{tail}   [停止] axis={axis} StopReason={reason}"
              f"({STOP_REASON_TEXT.get(reason, '未知')}) 档位={data[1]}")
        return
    # 事件：限位事件 DLC=2（0x08C0xx90）
    if grp == GRP_EVENT and msg == 4 and len(data) >= 2:
        print(f"{tail}   [限位] axis={axis} {LIMIT_TEXT.get(data[0], f'0x{data[0]:02X}')}")
        return
    print(f"{tail}   [其他] pri={info['pri']} grp={grp} seg={info['seg']} "
          f"node={info['node']} axis={axis} dir={direction} msg={msg}")


def summarize(frames):
    """统计各轴 CmdAck 与角度帧数，给结论"""
    acks, angles = {}, {}
    for cid, data in frames:
        info = parse_id(cid)
        if info["grp"] != GRP_MOTION_FB:
            continue
        if info["msg"] == 5 and len(data) >= 3:
            acks.setdefault(info["axis"], []).append(data[1])
        elif info["msg"] == 0 and len(data) >= 4:
            angles[info["axis"]] = struct.unpack_from(">i", data, 0)[0] / 100.0
    return acks, angles


# ==================== 动作封装 ====================
def release_estop(bus, wait=1.0):
    print("\n[急停解除] ID=0x00000004  DLC=1  DATA=01")
    bus.send(EMERGENCY_RELEASE_ID, EMERGENCY_RELEASE_DATA)
    time.sleep(wait)


# ==================== 模块确认（领号段） ====================
def discover_announce(bus, seconds=5.0):
    """监听未编号宣告帧，返回 [{'slot','device_type','uid56'}, ...]"""
    print(f"\n[模块确认] 监听 UID 宣告 {seconds:.1f}s（0x15BC0080 ~ 0x15BC00BC）...")
    found = {}
    deadline = time.time() + seconds
    arr = (_CAN_OBJ * 100)()
    while time.time() < deadline:
        n = bus.lib.VCI_GetReceiveNum(DEV_TYPE, DEV_IND, bus.channel)
        if n > 0:
            got = bus.lib.VCI_Receive(DEV_TYPE, DEV_IND, bus.channel,
                                      ctypes.byref(arr), min(n, 100), 50)
            for i in range(got):
                m = arr[i]
                cid = m.ID & 0x1FFFFFFF
                data = bytes(m.Data[:m.DataLen])
                if (cid & UID_FRAME_MASK) != UID_FRAME_BASE:
                    continue
                if not (UID_ANNOUNCE_BASE <= cid <= UID_ANNOUNCE_MAX):
                    continue
                if (cid - UID_ANNOUNCE_BASE) % 4 != 0 or len(data) < 8:
                    continue
                slot = (cid - UID_ANNOUNCE_BASE) // 4
                uid56 = int.from_bytes(data[1:8], "big")
                found[(slot, uid56)] = {"slot": slot, "device_type": data[0], "uid56": uid56}
        time.sleep(0.01)

    announce = sorted(found.values(), key=lambda x: x["slot"])
    if not announce:
        print("  ⚠️ 未收到任何 UID 宣告")
    for a in announce:
        print(f"  📢 槽{a['slot']}  类型=0x{a['device_type']:02X}  UID56=0x{a['uid56']:014X}")
    return announce


def do_confirm(bus, seg, arm, announce_wait=5.0, ack_timeout=1.5, retries=3,
               verify=False, want_uid=None):
    """完整模块确认：宣告 → 绑定 → 组号确认 + 臂位确认 →（可选）状态复核

    返回 dict(ok, uid56, seg, arm, axis_base) 或 dict(ok=False, reason=...)
    """
    print("\n" + "=" * 58)
    print(f"[模块确认] 目标 SEG={seg} ARM={arm}（起始AXIS={(arm - 1) * 3 + 1}）")
    print("=" * 58)

    # --- 1) 收宣告 ---
    announce = discover_announce(bus, announce_wait)
    if not announce:
        return {"ok": False,
                "reason": "未收到 UID 宣告：模块可能已绑定（重新上电才会再宣告）、未上电或 CAN 断开"}

    target = None
    if want_uid is not None:
        target = next((a for a in announce if a["uid56"] == want_uid), None)
        if target is None:
            return {"ok": False, "reason": f"总线上没有 UID56=0x{want_uid:014X} 的模块"}
    else:
        target = announce[0]
        if len(announce) > 1:
            print(f"  ℹ️ 发现 {len(announce)} 个未绑定模块，默认选槽{target['slot']}，"
                  f"可用 --uid 0x{target['uid56']:014X} 指定")

    uid56 = target["uid56"]
    expect_axis_base = (arm - 1) * 3 + 1
    assign_payload = uid56.to_bytes(7, "big") + bytes([((seg & 0xF) << 3) | ((arm - 1) & 0x7)])

    # --- 2) 发绑定 + 等双确认（超时重发）---
    for attempt in range(1, max(1, retries) + 1):
        print(f"\n[绑定] 第 {attempt}/{retries} 次  ID=0x{UID_ASSIGN_ID:08X}  "
              f"DLC=8  {assign_payload.hex(' ')}")
        if not bus.send(UID_ASSIGN_ID, assign_payload):
            return {"ok": False, "reason": "绑定帧发送失败（总线无应答）"}

        seg_ok = arm_ok = False
        deadline = time.time() + ack_timeout
        arr = (_CAN_OBJ * 100)()
        while time.time() < deadline:
            n = bus.lib.VCI_GetReceiveNum(DEV_TYPE, DEV_IND, bus.channel)
            if n > 0:
                got = bus.lib.VCI_Receive(DEV_TYPE, DEV_IND, bus.channel,
                                          ctypes.byref(arr), min(n, 100), 50)
                for i in range(got):
                    m = arr[i]
                    cid = m.ID & 0x1FFFFFFF
                    data = bytes(m.Data[:m.DataLen])
                    if cid == UID_CONFIRM_ID and len(data) >= 8:
                        r_uid = int.from_bytes(data[0:7], "big")
                        r_seg, r_res = data[7] >> 4, data[7] & 0xF
                        if r_uid == uid56 and r_seg == seg and r_res == 0:
                            seg_ok = True
                            print(f"  ✅ 组号确认  SEG={r_seg}  Result={r_res}")
                        else:
                            print(f"  ⚠️ 组号确认不符  UID=0x{r_uid:014X} SEG={r_seg} Result={r_res}")
                    elif cid == UID_ARM_CONFIRM_ID and len(data) >= 8:
                        r_uid = int.from_bytes(data[0:7], "big")
                        r_arm, r_base = data[7] >> 4, data[7] & 0xF
                        if r_uid == uid56 and r_arm == arm and r_base == expect_axis_base:
                            arm_ok = True
                            print(f"  ✅ 臂位确认  ARM={r_arm}  AxisBase={r_base}")
                        else:
                            print(f"  ⚠️ 臂位确认不符  ARM={r_arm} AxisBase={r_base}"
                                  f"（期望 ARM={arm} AxisBase={expect_axis_base}）")
            if seg_ok and arm_ok:
                break
            time.sleep(0.01)

        if seg_ok and arm_ok:
            break
        print(f"  ⏳ 双确认超时（组号={seg_ok} 臂位={arm_ok}），重试...")

    if not (seg_ok and arm_ok):
        return {"ok": False,
                "reason": f"双确认失败（组号={seg_ok} 臂位={arm_ok}），{retries} 次后放弃"}

    print(f"\n  🔒 模块已锁定 ID：UID56=0x{uid56:014X}  SEG={seg} ARM={arm} "
          f"AXIS={expect_axis_base}~{expect_axis_base + 2}")

    # --- 3) 可选状态复核 ---
    if verify:
        vr = verify_status(bus, seg, arm)
        if not vr["ok"]:
            print(f"  ⚠️ 状态复核未通过：{vr['reason']}（绑定已生效，可继续下发命令）")
        else:
            print("  ✅ 状态复核通过：三电机存在且就绪")

    return {"ok": True, "uid56": uid56, "seg": seg, "arm": arm,
            "axis_base": expect_axis_base}


def verify_status(bus, seg, arm, timeout=1.5):
    """状态复核：发 0x00000020（DLC=4 Token 大端），等 0x00002060+(SEG<<18) 应答"""
    token = int(time.time() * 1000) & 0xFFFF
    print(f"\n[状态复核] ID=0x{STATUS_QUERY_ID:08X}  DLC=4  Token=0x{token:04X}")
    if not bus.send(STATUS_QUERY_ID, token.to_bytes(4, "big")):
        return {"ok": False, "reason": "状态查询发送失败"}

    expect_base = (arm - 1) * 3 + 1
    deadline = time.time() + timeout
    arr = (_CAN_OBJ * 100)()
    while time.time() < deadline:
        n = bus.lib.VCI_GetReceiveNum(DEV_TYPE, DEV_IND, bus.channel)
        if n > 0:
            got = bus.lib.VCI_Receive(DEV_TYPE, DEV_IND, bus.channel,
                                      ctypes.byref(arr), min(n, 100), 50)
            for i in range(got):
                m = arr[i]
                cid = m.ID & 0x1FFFFFFF
                data = bytes(m.Data[:m.DataLen])
                if (cid & STATUS_RESP_MASK) != STATUS_RESP_BASE or len(data) < 8:
                    continue
                frame_seg = (cid >> 18) & 0xF
                r_token = struct.unpack_from(">H", data, 6)[0]
                if r_token != token:
                    continue
                r_seg, r_arm, r_base = data[1], data[2] >> 4, data[2] & 0xF
                exist, ready, state = data[3], data[4], data[5]
                print(f"  📋 状态应答 SEG={frame_seg}（数据段 SEG={r_seg} ARM={r_arm} "
                      f"AxisBase={r_base}）存在=0x{exist:02X} 就绪=0x{ready:02X} 状态=0x{state:02X}")
                if frame_seg != seg or r_seg != seg or r_arm != arm or r_base != expect_base:
                    return {"ok": False, "reason": "应答绑定信息与期望不符"}
                if exist != MOTOR_MASK_OK or ready != MOTOR_MASK_OK:
                    return {"ok": False, "reason": f"电机未全部就绪（存在=0x{exist:02X} 就绪=0x{ready:02X}）"}
                if (state & 0x03) != 0x03:
                    return {"ok": False, "reason": f"模块状态异常 state=0x{state:02X}"}
                return {"ok": True}
        time.sleep(0.01)
    return {"ok": False, "reason": "状态应答超时"}


def ensure_module_ready(bus, args):
    """下发命令前的统一前置：模块确认 → 返回 (seg, arm, axis_base)；失败返回 None"""
    if args.skip_confirm:
        print(f"\n[跳过模块确认] 按命令行参数下发：SEG={args.seg} ARM={args.arm}")
        return args.seg, args.arm, (args.arm - 1) * 3 + 1

    r = do_confirm(bus, args.seg, args.arm,
                   announce_wait=args.announce_wait, ack_timeout=args.ack_timeout,
                   retries=args.retries, verify=args.verify,
                   want_uid=args.uid)
    if not r["ok"]:
        print(f"\n❌ 模块确认失败：{r['reason']}")
        print("   运动指令已拒绝下发。排查方向：")
        print("     ① 下位机是否刚上电（绑定只存 RAM，重新上电必须重新确认）")
        print("     ② 该臂是否已被其它上位机绑定（已绑定则不再发宣告）")
        print("     ③ 若确认绑定仍然有效，可加 --skip-confirm 直接下发")
        return None
    return r["seg"], r["arm"], r["axis_base"]


def to_global_axis(local_axis, arm):
    """本地轴号(1~3) → 全局 AXIS：起始AXIS=(ARM-1)*3+1"""
    return (arm - 1) * 3 + int(local_axis)


def do_home(bus, axis, node, seg, wait=2.0):
    cid = build_id(PRI_MOTION, GRP_MOTION_CMD, seg, node, axis, DIR_DOWN, MSG_HOME)
    print(f"\n[回零] axis={axis}  SEG={seg}")
    bus.send(cid, bytes([0x01]))
    return bus.collect(wait)


def do_stop(bus, axis, node, seg, wait=1.0):
    cid = build_id(PRI_MOTION, GRP_MOTION_CMD, seg, node, axis, DIR_DOWN, MSG_STOP)
    print(f"\n[单轴停止] axis={axis}  SEG={seg}（不锁系统）")
    bus.send(cid, bytes([0x00]))
    return bus.collect(wait)


def do_move(bus, axis, delta, speed, node, seg, wait=3.0):
    """delta 单位 0.01（旋转/摆动 0.01°，伸缩 0.01mm）"""
    cid = build_id(PRI_MOTION, GRP_MOTION_CMD, seg, node, axis, DIR_DOWN, MSG_MOTION)
    unit = "mm" if local_axis_is_telescopic(axis) else "°"
    print(f"\n[运动] axis={axis}  SEG={seg}  delta={delta / 100.0:.2f}{unit}  speed={speed}")
    bus.send(cid, struct.pack(">hH", delta, speed))
    return bus.collect(wait)


def do_fault_reset(bus, axis, seg, wait=2.0):
    """超位故障复位：ID=0x04402114+(SEG<<18)+((AXIS-1)<<8)，DLC=1 DATA=01"""
    cid = FAULT_RESET_BASE | ((seg & 0xF) << 18) | (((int(axis) - 1) & 0x1F) << 8)
    print(f"\n[超位故障复位] axis={axis}  ID=0x{cid:08X}  DLC=1  DATA=01")
    bus.send(cid, bytes([0x01]))
    return bus.collect(wait)


def do_module_stop(bus, seg, wait=1.5):
    """模块级急停：ID=0x00000008+(SEG<<18)，只停本组三电机（比全局急停安全）"""
    cid = MODULE_STOP_BASE | ((seg & 0xF) << 18)
    print(f"\n[模块级急停] SEG={seg}  ID=0x{cid:08X}  DLC=1  DATA=01")
    print("   （只停本组三电机，可再用 0x00000004 解除）")
    bus.send(cid, bytes([0x01]))
    return bus.collect(wait)


def maybe_auto_reset(bus, frames, axes, seg):
    """运动被 Result=4 拒绝时自动复位对应轴超位故障"""
    acks, _ = summarize(frames)
    faulted = [ax for ax in axes if acks.get(ax) and acks[ax][-1] == 4]
    if not faulted:
        return
    for ax in faulted:
        print(f"  ⚠️ axis={ax} 处于超位故障锁存（Result=4），自动复位...")
        do_fault_reset(bus, ax, seg, wait=1.0)


def local_axis_is_telescopic(axis):
    """按 3 轴机械臂约定：组内第 3 轴为伸缩轴（只有它按 mm 显示）"""
    return (int(axis) - 1) % 3 == 2


def print_verdict(acks, angles, axis=None):
    print("\n--- 判定 ---")
    if not acks and not angles:
        print("  ⚠️ 未收到任何反馈帧：检查下位机是否上电、CAN_H/CAN_L 接线、终端电阻")
        return
    for ax in sorted(set(list(acks.keys()) + list(angles.keys()))):
        if axis is not None and ax != axis:
            continue
        results = acks.get(ax, [])
        last = results[-1] if results else None
        txt = RESULT_TEXT.get(last, f"未知({last})") if last is not None else "无 CmdAck"
        ang = f"{angles[ax]:.2f}" if ax in angles else "无角度帧"
        print(f"  axis={ax}  CmdAck={txt}  当前角度={ang}")


# ==================== 子命令 ====================
def cmd_probe(bus, args, seg, axis_base):
    """确认成功后依次探测本地 1..N 轴：回零 + 小幅增量，判断每轴能否动作"""
    for local in range(1, args.axes + 1):
        axis = axis_base + (local - 1)
        print("\n" + "=" * 50)
        print(f"探测 本地轴{local} → 全局 AXIS={axis}")
        print("=" * 50)
        do_home(bus, axis, args.node, seg, args.wait)
        time.sleep(1.0)
        do_move(bus, axis, args.delta, args.speed, args.node, seg, args.wait)


def cmd_confirm(bus, args):
    """只做模块确认，验证真机是否成功锁定 ID"""
    if args.skip_confirm:
        print(f"\n[跳过绑定] 按命令行假定已绑定：SEG={args.seg} ARM={args.arm}")
        r = verify_status(bus, args.seg, args.arm)
        print("\n" + "=" * 58)
        if r["ok"]:
            print(f"✅ 模块已绑定且状态正常：SEG={args.seg} ARM={args.arm}")
        else:
            print(f"❌ 状态复核失败：{r['reason']}")
        print("=" * 58)
        return

    r = do_confirm(bus, args.seg, args.arm,
                   announce_wait=args.announce_wait, ack_timeout=args.ack_timeout,
                   retries=args.retries, verify=args.verify, want_uid=args.uid)
    print("\n" + "=" * 58)
    if r["ok"]:
        print(f"✅ 模块确认成功：UID56=0x{r['uid56']:014X}  SEG={r['seg']} ARM={r['arm']}  "
              f"AXIS={r['axis_base']}~{r['axis_base'] + 2}")
        print("   → 真机已锁定 ID，可以下发运动命令")
    else:
        print(f"❌ 模块确认失败：{r['reason']}")
    print("=" * 58)


def cmd_estop(bus, args):
    if not args.i_know_risk:
        print("❌ 急停广播 0x00000000 会锁死下位机，只能重新上电恢复。\n"
              "   如确认要发，请追加 --i-know-risk")
        return
    print("\n[⚠️ 广播急停] ID=0x00000000  DLC=1  DATA=01")
    bus.send(EMERGENCY_STOP_ID, bytes([0x01]))
    bus.collect(1.0)


def add_common_args(parser, suppress=False):
    """公共参数。suppress=True 时用于子命令，避免覆盖主命令已解析的值"""
    def d(v):
        return argparse.SUPPRESS if suppress else v

    parser.add_argument("--channel", type=int, default=d(int(os.environ.get("CAN_CHANNEL", 0))))
    parser.add_argument("--bitrate", type=int, default=d(int(os.environ.get("CAN_BITRATE", 500000))))
    parser.add_argument("--node", type=int,
                        default=d(int(os.environ.get("CAN_MASTER_NODE_ID", 1))),
                        help="下行帧 NODE 段，默认主控节点号 1")
    parser.add_argument("--seg", type=int,
                        default=d(int(os.environ.get("CAN_DEFAULT_SEG", 0))),
                        help="组号 SEG 0~14，模块确认时写死到真机")
    parser.add_argument("--arm", type=int, default=d(1),
                        help="组内臂位 ARM 1~5，起始AXIS=(ARM-1)*3+1（默认 1 → 轴 1~3）")
    parser.add_argument("--speed", type=int,
                        default=d(int(os.environ.get("CAN_DEFAULT_SPEED_LIMIT", 500))))
    parser.add_argument("--wait", type=float, default=d(3.0),
                        help="每条指令后等待反馈的秒数")
    parser.add_argument("--skip-confirm", action="store_true", default=d(False),
                        help="跳过模块确认，直接按 --seg/--arm 下发（真机已绑定过时用）")
    parser.add_argument("--announce-wait", type=float, default=d(5.0),
                        help="等待 UID 宣告的秒数")
    parser.add_argument("--ack-timeout", type=float, default=d(1.5),
                        help="等待双确认的超时秒数")
    parser.add_argument("--retries", type=int, default=d(3), help="绑定帧重发次数")
    parser.add_argument("--verify", action="store_true", default=d(False),
                        help="确认后追加状态复核（0x00000020）")
    parser.add_argument("--uid", type=lambda s: int(s, 0), default=d(None),
                        help="指定目标模块 UID56（十进制或 0x 前缀），多臂时用")
    parser.add_argument("--auto-reset", action="store_true", default=d(False),
                        help="运动返回 Result=4（超位锁存）时自动发 0x0440xx14 复位")
    parser.add_argument("--no-release", action="store_true", default=d(False),
                        help="跳过自动急停解除")


def main():
    p = argparse.ArgumentParser(
        description="真机 CAN 联通性测试（急停解除 → 模块确认锁定 ID → 下发命令）",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    add_common_args(p)

    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("confirm", help="只做模块确认，验证真机锁定 ID")
    add_common_args(sp, suppress=True)

    sp = sub.add_parser("release", help="只发急停解除并监听")
    sp.add_argument("--listen", type=float, default=2.0)
    add_common_args(sp, suppress=True)

    sp = sub.add_parser("home", help="单轴回零")
    sp.add_argument("axis", type=int, help="本地轴号 1~3")
    add_common_args(sp, suppress=True)

    sp = sub.add_parser("stop", help="单轴停止（安全，不锁系统）")
    sp.add_argument("axis", type=int, help="本地轴号 1~3")
    add_common_args(sp, suppress=True)

    sp = sub.add_parser("move", help="单轴相对增量运动，单位 0.01")
    sp.add_argument("axis", type=int, help="本地轴号 1~3")
    sp.add_argument("delta", type=int, help="增量：旋转/摆动 0.01°；伸缩 0.01mm")
    add_common_args(sp, suppress=True)

    sp = sub.add_parser("status", help="只监听不发送")
    sp.add_argument("--listen", type=float, default=3.0)
    add_common_args(sp, suppress=True)

    sp = sub.add_parser("listen", help="监听总线")
    sp.add_argument("seconds", type=float, nargs="?", default=3.0)
    add_common_args(sp, suppress=True)

    sp = sub.add_parser("probe", help="确认后依次探测各轴")
    sp.add_argument("--axes", type=int, default=3, help="探测本地 1..N 轴，默认 3")
    sp.add_argument("--delta", type=int, default=100, help="每轴增量，默认 100 (1.00)")
    add_common_args(sp, suppress=True)

    sp = sub.add_parser("reset", help="超位故障复位（0x0440xx14）")
    sp.add_argument("axis", type=int, nargs="?", default=0,
                    help="本地轴号 1~3；省略则复位本臂全部 3 轴")
    add_common_args(sp, suppress=True)

    sp = sub.add_parser("modstop", help="模块级急停（只停本组三电机，可解除）")
    add_common_args(sp, suppress=True)

    sp = sub.add_parser("estop", help="⚠️ 广播急停（锁死全系统）")
    sp.add_argument("--i-know-risk", action="store_true")
    add_common_args(sp, suppress=True)

    args = p.parse_args()
    if not (1 <= args.arm <= 5):
        p.error("--arm 必须在 1~5 之间")
    if not (0 <= args.seg <= 14):
        p.error("--seg 必须在 0~14 之间")

    bus = ZLG(args.channel, args.bitrate)
    try:
        bus.drain()
        if not args.no_release:
            release_estop(bus)
            bus.collect(0.5)

        # 只监听/查询类命令：不做模块确认
        if args.cmd == "release":
            bus.collect(args.listen)
            return
        if args.cmd == "status":
            verify_status(bus, args.seg, args.arm)
            bus.collect(args.listen)
            return
        if args.cmd == "listen":
            bus.collect(getattr(args, "seconds", 5.0))
            return
        if args.cmd == "estop":
            cmd_estop(bus, args)
            return

        # confirm 子命令：只握手
        if args.cmd == "confirm":
            cmd_confirm(bus, args)
            return

        # 运动类命令：必须先锁定 ID
        ready = ensure_module_ready(bus, args)
        if ready is None:
            print("\n⛔ 已中止：未完成模块确认，不下发任何运动指令")
            return
        seg, arm, axis_base = ready
        print(f"\n→ 本次下发使用 SEG={seg} ARM={arm} AXIS 基准={axis_base}")

        frames = []
        if args.cmd == "home":
            axis = to_global_axis(args.axis, arm)
            frames = do_home(bus, axis, args.node, seg, args.wait)
        elif args.cmd == "stop":
            axis = to_global_axis(args.axis, arm)
            frames = do_stop(bus, axis, args.node, seg, args.wait)
        elif args.cmd == "move":
            axis = to_global_axis(args.axis, arm)
            frames = do_move(bus, axis, args.delta, args.speed,
                             args.node, seg, args.wait)
        elif args.cmd == "reset":
            axes = ([to_global_axis(args.axis, arm)] if args.axis
                    else [axis_base + i for i in range(3)])
            for ax in axes:
                frames += do_fault_reset(bus, ax, seg, args.wait)
        elif args.cmd == "modstop":
            frames = do_module_stop(bus, seg, args.wait)
        elif args.cmd == "probe":
            cmd_probe(bus, args, seg, axis_base)
            return

        if frames:
            if args.auto_reset and args.cmd in ("move", "home"):
                maybe_auto_reset(bus, frames, [to_global_axis(args.axis, arm)], seg)
                frames += bus.collect(1.0)
            acks, angles = summarize(frames)
            target_axis = to_global_axis(args.axis, arm) if args.cmd in ("move", "home", "stop") else None
            print_verdict(acks, angles, target_axis)
    finally:
        bus.close()
        print("\n✅ CAN 已释放")


if __name__ == "__main__":
    main()
