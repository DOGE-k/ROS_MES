#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ZLG USBCAN-II python-can 兼容 Bus 封装

用法（替代 socketcan）：
    from zlg_bus import ZLGBus
    bus = ZLGBus(channel=0, bitrate=500000)
    bus.send(can.Message(...))
    msg = bus.recv(timeout=0.5)
"""
import ctypes
import os
import threading
import time
from collections import deque

try:
    import can
    from can import Message
except ImportError:
    can = None
    Message = None

LIB_PATH = os.environ.get(
    "ZLG_LIBUSB_PATH",
    "/home/yang/.local/lib/usbcan/libusbcan.so",
)
DEV_TYPE = 4  # USBCAN-II

# 适配器 USB 标识（USBCAN-II：vendor-specific 类 0xDC、全速、单接口、无字符串描述符）
ZLG_USB_VID = int(os.environ.get("ZLG_USB_VID", "0x0471"), 0)
ZLG_USB_PID = int(os.environ.get("ZLG_USB_PID", "0x1200"), 0)


def _sysfs_node():
    """扫描 sysfs，返回适配器当前对应的 /dev/bus/usb/BBB/DDD；未找到返回空串"""
    base = "/sys/bus/usb/devices"
    try:
        names = sorted(os.listdir(base))
    except Exception:
        return ""
    for name in names:
        devdir = os.path.join(base, name)
        try:
            if not os.path.exists(os.path.join(devdir, "idVendor")):
                continue
            with open(os.path.join(devdir, "idVendor")) as f:
                vid = int(f.read().strip(), 16)
            with open(os.path.join(devdir, "idProduct")) as f:
                pid = int(f.read().strip(), 16)
            if vid != ZLG_USB_VID or pid != ZLG_USB_PID:
                continue
            with open(os.path.join(devdir, "busnum")) as f:
                busnum = int(f.read().strip())
            with open(os.path.join(devdir, "devnum")) as f:
                devnum = int(f.read().strip())
            return "/dev/bus/usb/%03d/%03d" % (busnum, devnum)
        except Exception:
            continue
    return ""


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
    1000000: 0x1400,
    500000:  0x1C00,
    250000:  0x1C01,
    125000:  0x1C03,
    100000:  0x1C07,
    50000:   0x1C0F,
}


class ZLGBus:
    """ZLG USBCAN-II Bus，接口与 python-can Bus 兼容（send/recv/shutdown）"""

    def __init__(self, channel=0, bitrate=500000, **kwargs):
        self.channel = int(channel)
        self.bitrate = int(bitrate)
        self._lib = ctypes.CDLL(LIB_PATH)
        self._rx_queue = deque()
        # ZLG libusbcan 的 VCI_* 调用非线程安全：ROS 节点里发送线程与接收线程
        # 并发调用会让 VCI_Transmit 返回 1 但帧实际未上总线（发送"假成功"）。
        # 所有 ctypes 调用都用这把锁串行化（单次调用粒度，不覆盖整个 recv 超时循环）。
        self._io_lock = threading.Lock()
        # 接收缓存上限：下位机位置反馈实测可达 ~5.5kHz，若生产快于消费，
        # 无界队列会让命令应答(CmdAck)排在数万帧之后，表现为"下发无应答"。
        # 超过上限时丢弃最旧帧，保证队列延迟有界（512 帧 ≈ 90ms）。
        self._rx_limit = 512
        self.dev_node = ""      # 打开时该适配器对应的 /dev/bus/usb/BBB/DDD
        self._closed = False
        self._open()

    def _open(self):
        # 记录 open 时刻的设备节点，供断线检测比较（USB 重新枚举后节点路径会变）
        self.dev_node = _sysfs_node()
        if self._lib.VCI_OpenDevice(DEV_TYPE, 0, 0) != 1:
            raise RuntimeError("ZLG VCI_OpenDevice 失败")
        # 关键：Init/Start 失败必须先把设备关掉再抛异常。
        # 否则句柄仍被本进程占用，上层每秒重试 VCI_OpenDevice 只会一直返回 0，
        # 反复对同一设备打开还会让适配器固件卡死（内核报 cannot reset err=-110）。
        try:
            timing = _BAUD_TIMING.get(self.bitrate, 0x1C00)
            cfg = _INIT_CONFIG()
            cfg.AccCode, cfg.AccMask, cfg.Reserved = 0, 0xFFFFFFFF, 0
            cfg.Filter, cfg.Mode = 1, 0
            cfg.Timing0, cfg.Timing1 = timing & 0xFF, timing >> 8
            # 首次 InitCAN 在某些固件上会失败，重试一次
            self._lib.VCI_InitCAN(DEV_TYPE, 0, self.channel, ctypes.byref(cfg))
            if self._lib.VCI_InitCAN(DEV_TYPE, 0, self.channel, ctypes.byref(cfg)) != 1:
                raise RuntimeError("ZLG VCI_InitCAN 失败")
            if self._lib.VCI_StartCAN(DEV_TYPE, 0, self.channel) != 1:
                raise RuntimeError("ZLG VCI_StartCAN 失败")
        except Exception:
            try:
                self._lib.VCI_CloseDevice(DEV_TYPE, 0)
            except Exception:
                pass
            raise

    def is_alive(self):
        """句柄是否仍对应在场的设备

        USB 掉线/重新枚举后，旧句柄不会报错，recv() 只会一直返回 None，
        因此用 sysfs 里适配器当前的设备节点路径与打开时记录的比较。
        """
        if self._closed:
            return False
        if not self.dev_node:
            return True
        cur = _sysfs_node()
        if cur:
            return cur == self.dev_node
        # 扫描不到时退化为节点文件是否存在（防止 sysfs 偶发读取失败误判掉线）
        return os.path.exists(self.dev_node)

    def send(self, msg, timeout=0.2):
        obj = _CAN_OBJ()
        obj.ID = msg.arbitration_id & 0x1FFFFFFF
        obj.SendType = 0
        obj.RemoteFlag = 0
        obj.ExternFlag = 1 if msg.is_extended_id else 0
        obj.DataLen = len(msg.data)
        for i, b in enumerate(msg.data):
            obj.Data[i] = b
        with self._io_lock:
            ret = self._lib.VCI_Transmit(DEV_TYPE, 0, self.channel, ctypes.byref(obj), 1)
        if ret != 1:
            raise can.CanError(f"ZLG VCI_Transmit 失败 ret={ret}")

    def recv(self, timeout=0.5):
        deadline = time.time() + timeout
        while time.time() < deadline:
            # 先取已缓存的
            if self._rx_queue:
                return self._rx_queue.popleft()
            with self._io_lock:
                # 单次最多取 200 帧，避免反馈高频时一次性分配超大数组拖慢接收线程
                n = min(self._lib.VCI_GetReceiveNum(DEV_TYPE, 0, self.channel), 200)
                if n <= 0:
                    got = 0
                else:
                    arr = (_CAN_OBJ * n)()
                    got = self._lib.VCI_Receive(
                        DEV_TYPE, 0, self.channel, ctypes.byref(arr), n, 20)
                    for i in range(got):
                        m = arr[i]
                        data = bytes(m.Data[:m.DataLen])
                        if Message is not None:
                            self._rx_queue.append(Message(
                                arbitration_id=m.ID & 0x1FFFFFFF,
                                data=data,
                                is_extended_id=bool(m.ExternFlag),
                                is_remote_frame=bool(m.RemoteFlag),
                            ))
                    while len(self._rx_queue) > self._rx_limit:
                        self._rx_queue.popleft()
            if got and self._rx_queue:
                return self._rx_queue.popleft()
            time.sleep(0.01)
        return None

    def shutdown(self):
        if self._closed:
            return
        self._closed = True
        # 只关闭设备，不发 VCI_ResetCAN：对 USBCAN-II 复位请求会把固件留在半死状态，
        # 导致下一次 OpenDevice 失败并引发 USB 超时（内核报 cannot reset err=-110）
        with self._io_lock:
            try:
                self._lib.VCI_CloseDevice(DEV_TYPE, 0)
            except Exception:
                pass
