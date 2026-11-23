import platform
from ctypes import *
import threading
import time
lib = cdll.LoadLibrary("./libusbcan.so")

USBCAN_I = c_uint32(3)   # USBCAN-I/I+ 3
USBCAN_II = c_uint32(4)  # USBCAN-II/II+ 4
MAX_CHANNELS = 2         # 通道最大数量
g_thd_run = 1            # 线程运行标志


class ZCAN_CAN_BOARD_INFO(Structure):
    _fields_ = [("hw_Version", c_ushort),
                ("fw_Version", c_ushort),
                ("dr_Version", c_ushort),
                ("in_Version", c_ushort),
                ("irq_Num", c_ushort),
                ("can_Num", c_ubyte),
                ("str_Serial_Num", c_ubyte*20),
                ("str_hw_Type", c_ubyte*40),
                ("Reserved", c_ubyte*4)]

    def __str__(self):
        return "Hardware Version:%s\nFirmware Version:%s\nDriver Version:%s\nInterface:%s\nInterrupt Number:%s\nCAN_number:%d" % (
            self.hw_Version,  self.fw_Version,  self.dr_Version,  self.in_Version,  self.irq_Num,  self.can_Num)

    def serial(self):
        serial = ''
        for c in self.str_Serial_Num:
            if c > 0:
                serial += chr(c)
            else:
                break
        return serial

    def hw_Type(self):
        hw_Type = ''
        for c in self.str_hw_Type:
            if c > 0:
                hw_Type += chr(c)
            else:
                break
        return hw_Type


class ZCAN_CAN_INIT_CONFIG(Structure):
    _fields_ = [("AccCode", c_int),
                ("AccMask", c_int),
                ("Reserved", c_int),
                ("Filter", c_ubyte),
                ("Timing0", c_ubyte),
                ("Timing1", c_ubyte),
                ("Mode", c_ubyte)]


class ZCAN_CAN_OBJ(Structure):
    _fields_ = [("ID", c_uint32),
                ("TimeStamp", c_uint32),
                ("TimeFlag", c_uint8),
                ("SendType", c_byte),
                ("RemoteFlag", c_byte),
                ("ExternFlag", c_byte),
                ("DataLen", c_byte),
                ("Data", c_ubyte*8),
                ("Reserved", c_ubyte*3)]


def GetDeviceInf(DeviceType, DeviceIndex):
    try:
        info = ZCAN_CAN_BOARD_INFO()
        ret = lib.VCI_ReadBoardInfo(DeviceType, DeviceIndex, byref(info))
        return info if ret == 1 else None
    except:
        print("Exception on readboardinfo")
        raise


def rx_thread(DEVCIE_TYPE, DevIdx, chn_idx):
    global g_thd_run
    while g_thd_run == 1:
        time.sleep(0.1)
        count = lib.VCI_GetReceiveNum(DEVCIE_TYPE, DevIdx, chn_idx) # 获取缓冲区报文数量
        if count > 0:
            print("缓冲区报文数量: %d" % count)
            can = (ZCAN_CAN_OBJ * count)()
            rcount = lib.VCI_Receive(DEVCIE_TYPE, DevIdx, chn_idx, byref(can), count, 100) # 读报文
            for i in range(rcount):
                print("[%d] %d ID: 0x%x " %(can[i].TimeStamp, chn_idx, can[i].ID), end='')
                print("%s " %("扩展帧" if can[i].ExternFlag == 1 else "标准帧"), end='')
                if can[i].RemoteFlag == 0:
                    print(" Data: ", end='')
                    for j in range(can[i].DataLen):
                        print("%02x "% can[i].Data[j], end='')
                else:
                    print(" 远程帧", end='')
                print("")


if __name__ == "__main__":
    threads = []
    # 波特率这里的十六进制数字，可以由“zcanpro 波特率计算器”计算得出
    gBaud = 0x1c00          # 波特率 0x1400-1M(75%), 0x1c00-500k(87.5%), 0x1c01-250k(87.5%), 0x1c03-125k(87.5%)
    DevType = USBCAN_II     # 设备类型号
    DevIdx = 0              # 设备索引号

    # 打开设备
    ret = lib.VCI_OpenDevice(DevType, DevIdx, 0)   # 设备类型，设备索引，保留参数
    if ret == 0:
        print("Open device fail")
        exit(0)
    else:
        print("Opendevice success")

    # # 获取设备信息
    # info = GetDeviceInf(USBCAN_II, 0)
    # print("Devcie Infomation:\n%s" % (info))

    # 初始化，启动通道
    for i in range(MAX_CHANNELS):
        init_config = ZCAN_CAN_INIT_CONFIG()
        init_config.AccCode = 0
        init_config.AccMask = 0xFFFFFFFF
        init_config.Reserved = 0
        init_config.Filter = 1
        init_config.Timing0 = gBaud & 0xff
        init_config.Timing1 = gBaud >> 8
        init_config.Mode = 0
        ret = lib.VCI_InitCAN(DevType, 0, i, byref(init_config))
        if ret == 0:
            print("InitCAN(%d) fail" % i)
        else:
            print("InitCAN(%d) success" % i)

        ret = lib.VCI_StartCAN(DevType, 0, i)
        if ret == 0:
            print("StartCAN(%d) fail" % i)
        else:
            print("StartCAN(%d) success" % i)
            
        thread = threading.Thread(target=rx_thread, args=(DevType, DevIdx, i,))
        threads.append(thread) # 独立接收线程
        thread.start()

    # 测试发送
    send_len = 10  # 发送帧数量
    msgs = (ZCAN_CAN_OBJ * send_len)()
    for i in range(send_len):
        msgs[i].ID = 0x100
        msgs[i].SendType = 0    # 发送方式 0-正常, 1-单次, 2-自发自收
        msgs[i].RemoteFlag = 0  # 0-数据帧 1-远程帧
        msgs[i].ExternFlag = 0  # 0-标准帧 1-扩展帧
        msgs[i].DataLen = 8     # 数据长度 1~8
        for j in range(msgs[i].DataLen):
            msgs[i].Data[j] = j
    send_ret = lib.VCI_Transmit(DevType, 0, 0, byref(msgs), send_len)

    if send_len == send_ret:
        print("Transmit success, sendcount is: %d " % send_ret)
    else:
        print("Transmit fail, sendcounet is: %d " % send_ret)

    # 阻塞等待
    input()
    g_thd_run = 0

    # 等待所有线程完成
    for thread in threads:
        thread.join()

    # 复位通道
    for i in range(MAX_CHANNELS):
        ret = lib.VCI_ResetCAN(DevType, DevIdx, i)
        if ret == 0:
            print("ResetCAN(%d) fail" % i)
        else:
            print("ResetCAN(%d) success" % i)

    # 关闭设备
    ret = lib.VCI_CloseDevice(DevType, DevIdx)
    if ret == 0:
        print("Closedevice fail")
    else:
        print("Closedevice success")
    del lib
