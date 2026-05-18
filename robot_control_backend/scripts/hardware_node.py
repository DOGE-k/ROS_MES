#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import rospy
import serial
import threading
import traceback
import sqlite3
import os
import struct  #  新增：用于解析 4字节 float 或 int

from std_msgs.msg import Header
# 导入原有的消息和新建的陀螺仪消息
from robot_control_backend.msg import Feedback, IntCmd, GyroFeedback 

def load_env_config():
    """从 .env 文件加载配置"""
    env_path = os.path.join(os.path.dirname(__file__), '../rob_arm.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    os.environ[key] = value
        rospy.loginfo("✅ 已从 rob_arm.env 加载配置")

class STM32Bridge:
    def __init__(self, port=None, baud=None):
        load_env_config()
        self.port = port or os.environ.get('SERIAL_PORT', '/dev/ttyUSB0')
        self.baud = baud or int(os.environ.get('SERIAL_BAUD', '115200'))
        self.ser = None
        self.serial_lock = threading.Lock()
        self.running = True
        self.connected = True

        # ================== 话题发布者（从环境变量读取） ==================
        TOPIC_ALL_FEEDBACK = os.environ.get('ROS_TOPIC_ALL_FEEDBACK', '/hardware/all_feedback')
        TOPIC_ARM_CMD_VEL = os.environ.get('ROS_TOPIC_ARM_CMD_VEL', '/arm/cmd_vel')
        
        self.pub_all_feedback = rospy.Publisher(TOPIC_ALL_FEEDBACK, Feedback, queue_size=10)
        self.pub_gyro = rospy.Publisher("/hardware/gyroscope_feedback", GyroFeedback, queue_size=10) # <--- 新增
        
        rospy.Subscriber(TOPIC_ARM_CMD_VEL, IntCmd, self.on_cmd_received)

        self.last_sent_data = None
        self.serial_buffer = b""
        self.stop_frame = b"\x11\x00\x00\x00"
        self.receive_stopped = False
        self.last_raw_data = b""
        self.last_parsed_msg = None

        # ================== 设备 ID 定义（从环境变量读取） ==================
        self.TARGET_MODULE_ID = int(os.environ.get('MODULE_ID', '17'))
        self.DEV_ROTATE = int(os.environ.get('DEV_ROTATE', '41'))
        self.DEV_SWING  = int(os.environ.get('DEV_SWING', '42'))
        self.DEV_TELES  = int(os.environ.get('DEV_TELES', '43'))
        self.DEV_SENSOR = int(os.environ.get('DEV_SENSOR', '49'))
        self.DEV_GYRO   = 50  # 新增：假设陀螺仪的 device_id 是 50，根据实际下位机程序修改

        # 实时数据缓存字典
        self.realtime_data = {}

        # 数据库初始化
        self.db_lock = threading.Lock()
        self.db_path = os.path.join(os.path.expanduser('~'), "robot_hardware_data.db")
        self.db_conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.db_cursor = self.db_conn.cursor()
        self.init_database()
        rospy.loginfo(f"✅ 数据库已连接，路径: {self.db_path}")

        self.try_serial_connect()
        self.start_read_thread()
        self.parse_timer = rospy.Timer(rospy.Duration(0.01), self.parse_frames)

    # -------------------------------------------------------------------------
    def init_database(self):
        """初始化数据库表"""
        with self.db_lock:
            # 基础单值传感器表
            self.db_cursor.execute('''
                CREATE TABLE IF NOT EXISTS sensor_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL,
                    module_id INTEGER,
                    device_id INTEGER,
                    value REAL
                )
            ''')
            # 陀螺仪多维数据专属表 (新增)
            self.db_cursor.execute('''
                CREATE TABLE IF NOT EXISTS gyro_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL,
                    module_id INTEGER,
                    device_id INTEGER,
                    acc_x REAL,
                    acc_y REAL,
                    acc_z REAL,
                    gyro_x REAL,
                    gyro_y REAL,
                    gyro_z REAL
                )
            ''')
            self.db_conn.commit()

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
    def on_cmd_received(self, msg):
        # 此处省略下发代码，与原版保持一致
        mid = msg.module_id
        did = msg.device_id
        pos = int(msg.position[0])
        key = (mid, did, pos)
        if key == self.last_sent_data: return
        try:
            h = (pos >> 8) & 0xFF
            l = pos & 0xFF
            buf = bytes([mid, did, h, l])
            with self.serial_lock:
                if self.ser is None or not self.ser.is_open: return
                self.ser.write(buf)
                self.ser.flush()
            self.last_sent_data = key
        except Exception as e:
            self.connected = False

    # -------------------------------------------------------------------------
    def read_serial_thread(self):
        # 串口读取逻辑
        while self.running and not rospy.is_shutdown():
            if self.receive_stopped: break
            if not self.connected:
                rospy.sleep(1)
                self.try_serial_connect()
                continue
            try:
                with self.serial_lock:
                    if self.ser.in_waiting > 0:
                        raw_data = self.ser.read(self.ser.in_waiting)
                        if self.stop_frame in raw_data:
                            self.receive_stopped = True
                            valid_data, _ = raw_data.split(self.stop_frame, 1)
                            if valid_data: self.serial_buffer += valid_data
                        else:
                            self.serial_buffer += raw_data
            except Exception as e:
                self.connected = False
            rospy.sleep(0.001)

    # -------------------------------------------------------------------------
    def parse_frames(self, event):
        with self.serial_lock:
            buf = self.serial_buffer

            if len(buf) == 1 and buf[0] == 0x11:
                # 单字节特判逻辑保持不变
                self.serial_buffer = b""
                return

            while len(buf) >= 2:
                module_id = buf[0]
                device_id = buf[1]

                if module_id != self.TARGET_MODULE_ID:
                    buf = buf[1:]
                    continue

                # ================= 动态长度判定 =================
                if device_id in [self.DEV_ROTATE, self.DEV_SWING, self.DEV_TELES]:
                    frame_len = 4
                elif device_id == self.DEV_SENSOR:
                    frame_len = 6
                elif device_id == self.DEV_GYRO:  # 新增分支
                    frame_len = 26  # 头2字节 + 6个float*4字节 = 26字节
                else:
                    buf = buf[1:]
                    continue

                if len(buf) < frame_len:
                    break

                frame = buf[:frame_len]
                buf = buf[frame_len:]

                timestamp_now = rospy.Time.now().to_sec()

                # ================= 陀螺仪解析处理 =================
                if device_id == self.DEV_GYRO:
                    # 关键点：使用 struct.unpack 拆包
                    # '<ffffff' 表示按照小端序(Little-Endian)解析6个单精度浮点数 (C语言中的 float)
                    # 如果下位机发的是 32位整形(int32_t)，请改成 '<iiiiii'
                    try:
                        ax, ay, az, gx, gy, gz = struct.unpack('<ffffff', frame[2:26])
                    except struct.error:
                        rospy.logwarn("陀螺仪数据解包失败！")
                        continue

                    # 组成元组用于字典比对去重
                    val_tuple = (ax, ay, az, gx, gy, gz)
                    
                    if self.realtime_data.get(device_id) != val_tuple:
                        self.realtime_data[device_id] = val_tuple

                        # 1. 存入新数据库表
                        with self.db_lock:
                            try:
                                self.db_cursor.execute('''
                                    INSERT INTO gyro_data (timestamp, module_id, device_id, acc_x, acc_y, acc_z, gyro_x, gyro_y, gyro_z)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                                ''', (timestamp_now, module_id, device_id, ax, ay, az, gx, gy, gz))
                                self.db_conn.commit()
                            except Exception as e:
                                rospy.logerr(f" 陀螺仪数据库写入失败: {e}")

                        # 2. 发布 ROS 消息
                        msg = GyroFeedback()
                        msg.header = Header(stamp=rospy.Time.now())
                        msg.module_id = module_id
                        msg.device_id = device_id
                        msg.accel_x = ax
                        msg.accel_y = ay
                        msg.accel_z = az
                        msg.gyro_x = gx
                        msg.gyro_y = gy
                        msg.gyro_z = gz
                        
                        self.pub_gyro.publish(msg)
                        self.last_parsed_msg = msg
                        # 不刷屏日志：rospy.loginfo(f"[陀螺仪更新] Acc:({ax:.2f},{ay:.2f},{az:.2f})")

                # ================= 普通传感器解析 =================
                else:
                    if frame_len == 4:
                        value = (frame[2] << 8) | frame[3]
                    elif frame_len == 6:
                        value = (frame[2] << 24) | (frame[3] << 16) | (frame[4] << 8) | frame[5]

                    if self.realtime_data.get(device_id) != value:
                        self.realtime_data[device_id] = value
                        
                        with self.db_lock:
                            try:
                                self.db_cursor.execute('''
                                    INSERT INTO sensor_data (timestamp, module_id, device_id, value)
                                    VALUES (?, ?, ?, ?)
                                ''', (timestamp_now, module_id, device_id, float(value)))
                                self.db_conn.commit()
                            except Exception as e:
                                rospy.logerr(f" 传感器数据库写入失败: {e}")

                        msg = Feedback()
                        msg.header = Header(stamp=rospy.Time.now())
                        msg.module_id = module_id
                        msg.device_id = device_id
                        msg.position = [float(value)]
                        self.pub_all_feedback.publish(msg)
                        self.last_parsed_msg = msg

            self.serial_buffer = buf

    # -------------------------------------------------------------------------
    def close(self):
        self.running = False
        if self.ser and self.ser.is_open:
            self.ser.close()
        if hasattr(self, 'db_conn'):
            with self.db_lock:
                self.db_conn.close()

if __name__ == "__main__":
    rospy.init_node("stm32_bridge")
    bridge = STM32Bridge()  # 参数从环境变量读取
    rospy.loginfo("硬件桥接节点启动")
    rospy.spin()
    bridge.close()