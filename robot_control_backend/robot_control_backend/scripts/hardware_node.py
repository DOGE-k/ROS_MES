#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import rospy
import serial
import threading
from std_msgs.msg import Header
from robot_control_backend.msg import Feedback, IntCmd

class STM32Bridge:
    def __init__(self, port="/dev/ttyUSB0", baud=115200):
        self.port = port
        self.baud = baud
        self.ser = None
        self.serial_lock = threading.Lock()

        self.running = True
        self.connected = True

        # 发布所有原始反馈
        self.pub_all_feedback = rospy.Publisher("/hardware/all_feedback", Feedback, queue_size=10)
        rospy.Subscriber("/arm/cmd_vel", IntCmd, self.on_cmd_received)
                
        self.last_sent_data = None
        self.serial_buffer = b""

        # ===================== 停止帧检测 + 最后一条数据缓存 =====================
        self.stop_frame = b"\x11\x00\x00\x00"  # 停止传输标识 11 00 00 00
        self.receive_stopped = False          # 标记是否收到停止帧
        self.last_raw_data = b""              # 缓存最后一条原始数据
        self.last_parsed_msg = None           # 缓存最后一条解析后的Feedback消息

        # ===================== 设备定义 =====================
        self.TARGET_MODULE_ID = 0x11
        
        self.DEV_ROTATE = 41      # 0x29 旋转轴  4字节
        self.DEV_SWING  = 42      # 0x2A 摆动轴  4字节 self.pub_all_feedback = rospy.Publisher("/hardware/all_feedback", Feedback, queue_size=10)
        
        rospy.Subscriber("/arm/cmd_vel", IntCmd, self.on_cmd_received)

        self.last_sent_data = None
        self.DEV_TELES  = 43      # 0x2B 伸缩轴  4字节
        self.DEV_SENSOR = 49      # 0x31 压力传感器 6字节

        # 启动
        self.try_serial_connect()
        self.start_read_thread()
        self.parse_timer = rospy.Timer(rospy.Duration(0.01), self.parse_frames)
        
        # ===================== 启动缓存数据实时打印定时器 =====================
        # 每100ms打印一次缓存状态（可根据需要调整频率，如0.05=50ms）
        # self.cache_print_timer = rospy.Timer(rospy.Duration(1), self.print_serial_cache)

    # -------------------------------------------------------------------------
    # 串口重连
    # -------------------------------------------------------------------------
    def try_serial_connect(self):
        with self.serial_lock:
            try:
                if self.ser is not None and self.ser.is_open:
                    self.ser.close()
                self.ser = serial.Serial(self.port, self.baud, timeout=0.1)
                self.connected = True
                rospy.loginfo(f"✅ 串口已连接: {self.port}")
            except Exception as e:
                self.connected = False
                rospy.logerr(f"❌ 串口失败: {e}")

    # -------------------------------------------------------------------------
    # 下发指令到 STM32
    # -------------------------------------------------------------------------
    def on_cmd_received(self, msg):
        mid = msg.module_id
        did = msg.device_id
        pos = int(msg.position[0])
        key = (mid, did, pos)
        if key == self.last_sent_data:
            return
        try:
            h = (pos >> 8) & 0xFF
            l = pos & 0xFF
            buf = bytes([mid, did, h, l])
            self.ser.write(buf)
            self.last_sent_data = key
            rospy.loginfo(f"[下发] %02X %02X %02X %02X", mid, did, h, l)
        except Exception as e:
            self.connected = False
            rospy.logerr(f"❌ 发送失败: {e}")

    # -------------------------------------------------------------------------
    # 串口读线程
    # -------------------------------------------------------------------------
    def read_serial_thread(self):
        while self.running and not rospy.is_shutdown():
            if self.receive_stopped:  # 收到停止帧，停止读取
                rospy.loginfo("✅ 收到停止帧 11 00 00 00，停止接收下位机数据")
                break
            if not self.connected:
                rospy.sleep(1)
                self.try_serial_connect()
                continue
            try:
                if self.ser.in_waiting > 0:
                    raw_data = self.ser.read(self.ser.in_waiting)
                    # 检测停止帧：若包含 11 00 00 00，截取之前的有效数据
                    if self.stop_frame in raw_data:
                        self.receive_stopped = True
                        # 拆分数据：停止帧前的有效数据 + 停止帧及之后的无效数据
                        valid_data, _ = raw_data.split(self.stop_frame, 1)
                        if valid_data:
                            self.last_raw_data = valid_data  # 缓存最后一条原始数据
                            rospy.loginfo(f"[下位机原始数据] {valid_data.hex()}")
                            self.serial_buffer += valid_data
                    else:
                        # 未收到停止帧，正常更新缓存和打印
                        self.last_raw_data = raw_data
                        rospy.loginfo(f"[下位机原始数据] {raw_data.hex()}")
                        self.serial_buffer += raw_data
            except:
                self.connected = False
            rospy.sleep(0.001)

    # -------------------------------------------------------------------------
    # 实时打印串口缓存数据（包含长度+十六进制内容）
    # -------------------------------------------------------------------------
    def print_serial_cache(self, event):
        if self.receive_stopped:  # 收到停止帧后仅打印一次缓存最终状态
            self.cache_print_timer.shutdown()  # 关闭定时器，避免重复打印
            rospy.loginfo(f"\n🔍 [缓存最终状态] 长度={len(self.serial_buffer)} 字节 | 内容={self.serial_buffer.hex() if self.serial_buffer else '空'}\n")
            return
        # 实时打印缓存状态（仅当缓存非空时打印，避免刷屏）
        if len(self.serial_buffer) > 0:
            rospy.loginfo(f"🔍 [缓存实时状态] 长度={len(self.serial_buffer)} 字节 | 内容={self.serial_buffer.hex()}")


    def parse_frames(self, event):
        if self.receive_stopped:  # 收到停止帧后不再解析新数据
            return
        buf = self.serial_buffer

        # ===================== 新增逻辑：检测仅收到单字节0x11 =====================
        # 先检查缓存中是否有单字节0x11的情况
        if len(buf) == 1 and buf[0] == 0x11:
            rospy.loginfo(f"[检测到单字节0x11] 下位机仅发送0x11，发布指定反馈话题")
            # 构造并发布指定的Feedback消息
            single_byte_msg = Feedback()
            single_byte_msg.header = Header(stamp=rospy.Time.now())
            single_byte_msg.module_id = 17  # 固定17（0x11）
            single_byte_msg.device_id = 0   # 固定0
            single_byte_msg.position = [0]  # 固定[0]
            self.pub_all_feedback.publish(single_byte_msg)
            self.last_parsed_msg = single_byte_msg  # 更新最后解析消息缓存
            buf = buf[1:]  # 移除已处理的单字节0x11
            self.serial_buffer = buf  # 更新缓存
            return  # 单字节处理完成，退出本次解析
        
        # ===================== 原有解析逻辑 =====================
        while len(buf) >= 2:
            module_id = buf[0]
            device_id = buf[1]

            if module_id != self.TARGET_MODULE_ID:
                buf = buf[1:]
                continue

            if device_id in [self.DEV_ROTATE, self.DEV_SWING, self.DEV_TELES]:
                frame_len = 4
            elif device_id == self.DEV_SENSOR:
                frame_len = 6
            else:
                buf = buf[1:]
                continue

            if len(buf) < frame_len:
                break

            frame = buf[:frame_len]
            buf = buf[frame_len:]

            if frame_len == 4:
                data_h = frame[2]
                data_l = frame[3]
                value = (data_h << 8) | data_l

            elif frame_len == 6:
                b2 = frame[2]
                b3 = frame[3]
                b4 = frame[4]
                b5 = frame[5]
                value = (b2 << 24) | (b3 << 16) | (b4 << 8) | b5

        msg = Feedback()
        msg.header = Header(stamp=rospy.Time.now())
        msg.module_id = module_id
        msg.device_id = device_id
        msg.position = [value]
        self.pub_all_feedback.publish(msg)
        self.last_parsed_msg = msg  # 缓存最后一条解析后的消息

        rospy.loginfo(f"[解析成功] module={module_id} device={device_id} value={value} 帧长={frame_len}")

        self.serial_buffer = buf

    # -------------------------------------------------------------------------
    # 打印最后一条有效数据（程序退出时调用）
    # -------------------------------------------------------------------------
    def print_last_data(self):
        rospy.loginfo("\n" + "="*60)
        rospy.loginfo("📌 最后一条有效数据汇总：")
        if self.last_raw_data:
            rospy.loginfo(f"   原始数据：{self.last_raw_data.hex()}")
        if self.last_parsed_msg:
            msg = self.last_parsed_msg
            rospy.loginfo(f"   解析结果：module={msg.module_id} device={msg.device_id} value={msg.position[0]}")
        rospy.loginfo("="*60 + "\n")

    # -------------------------------------------------------------------------
    # 启动/关闭
    # -------------------------------------------------------------------------
    def start_read_thread(self):
        t = threading.Thread(target=self.read_serial_thread, daemon=True)
        t.start()

    def close(self):
        self.running = False
        # 关闭缓存打印定时器
        if hasattr(self, 'cache_print_timer') and self.cache_print_timer.is_alive():
            self.cache_print_timer.shutdown()
        # 打印最后一条有效数据
        self.print_last_data()
        if self.ser and self.ser.is_open:
            self.ser.close()

if __name__ == "__main__":
    rospy.init_node("stm32_bridge")
    bridge = STM32Bridge("/dev/ttyUSB0", 115200)
    rospy.loginfo("✅ STM32 桥接节点已启动（支持4字节+6字节混合帧+单字节0x11处理）")
    rospy.spin()
    bridge.close()