#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import rospy
import serial
import threading
from std_msgs.msg import Header
from robot_control_backend.msg import Feedback, IntCmd

class STM32Bridge:
    def __init__(self, port="/dev/ttyUSB0", baud=115200):
        # 串口配置
        self.port = port
        self.baud = baud
        self.ser = None
        self.serial_lock = threading.Lock()

        self.running = True
        self.connected = False

        # 发布/订阅
        self.pub_feedback = rospy.Publisher("/hardware/all_feedback", Feedback, queue_size=10)
        rospy.Subscriber("/arm/cmd_vel", IntCmd, self.on_cmd_received)

        # 发送缓存
        self.last_sent_data = None

        # ===================== 核心配置 =====================
        self.START_MODULE_ID = 0x11
        self.PRESSURE_SENSOR_ID = 49
        self.ENCODER_IDS = [41, 42, 43]
        self.PRESSURE_DATA_LEN = 6
        self.ENCODER_DATA_LEN = 4
        self.IDLE_TIMEOUT = 1.0

        # 数据缓冲区
        self.serial_buffer = b""
        self.last_data_receive_time = rospy.Time.now()

        # 启动
        self.try_serial_connect()
        self.start_read_thread()
        self.timer = rospy.Timer(rospy.Duration(0.1), self.idle_detect_callback)

    # -------------------------------------------------------------------------
    # ✅ 修复问题4：串口自动重连机制
    # -------------------------------------------------------------------------
    def try_serial_connect(self):
        with self.serial_lock:
            try:
                if self.ser is not None and self.ser.is_open:
                    self.ser.close()
                self.ser = serial.Serial(self.port, self.baud, timeout=0.5)
                self.connected = True
                rospy.loginfo(f"✅ 串口已连接: {self.port} @ {self.baud}")
            except Exception as e:
                self.connected = False
                rospy.logerr(f"❌ 串口打开失败: {str(e)}，将自动重连")

    # -------------------------------------------------------------------------
    # 发送指令
    # -------------------------------------------------------------------------
    def on_cmd_received(self, msg):
        if not self.connected:
            rospy.logwarn("⚠️ 串口未连接，指令丢弃")
            return

        module_id = msg.module_id
        device_id = msg.device_id
        pos_val = int(msg.position[0])
        current_data = (module_id, device_id, pos_val)

        if current_data != self.last_sent_data:
            try:
                data_high = (pos_val >> 8) & 0xFF
                data_low = pos_val & 0xFF
                send_bytes = bytes([module_id, device_id, data_high, data_low])
                self.ser.write(send_bytes)
                self.last_sent_data = current_data
                rospy.loginfo(f"[下发指令] %02X %02X %02X %02X", module_id, device_id, data_high, data_low)
            except Exception as e:
                rospy.logerr(f"❌ 发送失败: {str(e)}")
                self.connected = False

    # -------------------------------------------------------------------------
    # 串口读取线程
    # -------------------------------------------------------------------------
    def read_serial_thread(self):
        while self.running and not rospy.is_shutdown():
            if not self.connected:
                rospy.sleep(1)
                self.try_serial_connect()
                continue

            try:
                if self.ser.in_waiting > 0:
                    new_data = self.serial.read(self.ser.in_waiting)
                    self.serial_buffer += new_data
                    self.last_data_receive_time = rospy.Time.now()
            except Exception as e:
                rospy.logerr(f"❌ 串口读取异常: {str(e)}")
                self.connected = False
                self.ser.close()

            rospy.sleep(0.001)

    # -------------------------------------------------------------------------
    # ✅ 修复问题1、2、3：空闲检测 + 安全解析
    # -------------------------------------------------------------------------
    def idle_detect_callback(self, event):
        idle_time = (rospy.Time.now() - self.last_data_receive_time).to_sec()
        if idle_time < self.IDLE_TIMEOUT:
            return

        buffer = self.serial_buffer
        if len(buffer) == 0:
            return

        rospy.loginfo(f"===== {self.IDLE_TIMEOUT}s 无数据，开始解析 =====")
        start_positions = [i for i, b in enumerate(buffer) if b == self.START_MODULE_ID]
        processed_pos = 0

        for start in start_positions:
            if start < processed_pos:
                continue

            if start + 1 >= len(buffer):
                break

            device_id = buffer[start + 1]
            data_len = self.ENCODER_DATA_LEN
            device_name = ""

            if device_id == self.PRESSURE_SENSOR_ID:
                data_len = self.PRESSURE_DATA_LEN
                device_name = "压力传感器"
            elif device_id in self.ENCODER_IDS:
                data_len = self.ENCODER_DATA_LEN
                device_name = f"编码器{device_id}"
            else:
                processed_pos = start + 1
                continue

            if start + data_len > len(buffer):
                break

            # 提取帧
            frame = buffer[start:start+data_len]
            processed_pos = start + data_len

            try:
                if device_id == self.PRESSURE_SENSOR_ID:
                    val = (frame[2] << 24) | (frame[3] << 16) | (frame[4] << 8) | frame[5]
                else:
                    val = (frame[2] << 8) | frame[3]

                msg = Feedback()
                msg.header = Header(stamp=rospy.Time.now())
                msg.module_id = frame[0]
                msg.device_id = device_id
                msg.position = [val]
                self.pub_feedback.publish(msg)
                rospy.loginfo(f"[解析发布] {device_name} ID:{device_id} 数值:{val}")

            except Exception as e:
                rospy.logerr(f"解析失败: {e}")
                continue

        # ✅ 修复问题1：不清空整个缓冲区，只移除已解析部分
        self.serial_buffer = buffer[processed_pos:]
        rospy.loginfo(f"===== 解析完成，保留未解析数据: {len(self.serial_buffer)} 字节 =====")

    # -------------------------------------------------------------------------
    # 线程启动/关闭
    # -------------------------------------------------------------------------
    def start_read_thread(self):
        t = threading.Thread(target=self.read_serial_thread, daemon=True)
        t.start()

    def close(self):
        self.running = False
        if self.ser is not None and self.ser.is_open:
            self.ser.close()

if __name__ == "__main__":
    rospy.init_node("stm32_bridge")
    bridge = STM32Bridge("/dev/ttyUSB0", 115200)
    # ✅ 修复问题3：使用变量，不写死1秒
    rospy.loginfo(f"STM32联通节点启动成功 → {bridge.IDLE_TIMEOUT}秒空闲判定传输结束")
    rospy.spin()
    bridge.close()