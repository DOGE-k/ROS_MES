#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import rospy
import serial
import threading
import traceback
import sqlite3
import os
import struct

from std_msgs.msg import Header
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

        # ================== 话题发布者 ==================
        TOPIC_ALL_FEEDBACK = os.environ.get('ROS_TOPIC_ALL_FEEDBACK', '/hardware/all_feedback')
        TOPIC_ARM_CMD_VEL = os.environ.get('ROS_TOPIC_ARM_CMD_VEL', '/arm/cmd_vel')
        
        self.pub_all_feedback = rospy.Publisher(TOPIC_ALL_FEEDBACK, Feedback, queue_size=10)
        self.pub_gyro = rospy.Publisher("/hardware/gyroscope_feedback", GyroFeedback, queue_size=10)
        
        rospy.Subscriber(TOPIC_ARM_CMD_VEL, IntCmd, self.on_cmd_received)

        self.last_sent_data = None
        self.serial_buffer = b""
        self.stop_frame = b"\x11\x00\x00\x00"
        self.receive_stopped = False
        self.last_raw_data = b""
        self.last_parsed_msg = None

        # ================== 【关键：和你数据库严格对应】设备ID映射 ==================
        # 一号机械臂 Unit_ID=32
        self.UNIT_ID = 32
        self.CREATER_ID = 1    # 创建者ID固定为1（你数据库里创建者都是1）
        self.WORK_ID = 1       # 固定绑定初始工作 Work_ID=1
        self.TARGET_MODULE_ID = int(os.environ.get('MODULE_ID', '17'))  # Model_ID=17（一号型号）

        # 和你sensors表完全对应
        self.DEV_ROTATE = 33    # 一号机械臂旋转电机 sensor_ID=33
        self.DEV_SWING  = 34    # 摆动电机 34
        self.DEV_TELES  = 35    # 伸缩电机 35
        self.DEV_ROTATE_ENC = 41# 旋转编码器 41
        self.DEV_SWING_ENC  = 42# 偏转编码器 42
        self.DEV_TELES_ENC  = 43# 伸缩编码器 43
        self.DEV_PRESSURE   = 49# 压力传感器 49
        self.DEV_GYRO       = 50# 陀螺仪传感器 50

        # 实时数据缓存字典
        self.realtime_data = {}

        # 数据库初始化（直接连接你已建好的库）
        self.db_lock = threading.Lock()
        self.db_path = os.path.join(os.path.expanduser('~'), "yang/sqlite/main.db") # 改成你实际sqlite路径
        self.db_conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.db_cursor = self.db_conn.cursor()
        rospy.loginfo(f"✅ 数据库已连接，路径: {self.db_path}")

        self.try_serial_connect()
        self.start_read_thread()
        self.parse_timer = rospy.Timer(rospy.Duration(0.01), self.parse_frames)

    # -------------------------------------------------------------------------
    def init_database(self):
        """不再新建表，直接使用你已经设计好的表"""
        pass

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
                self.serial_buffer = b""
                return

            while len(buf) >= 2:
                module_id = buf[0]
                sensor_id = buf[1] # 这里直接对应 sensors表的 sensor_ID

                if module_id != self.TARGET_MODULE_ID:
                    buf = buf[1:]
                    continue

                # ================= 动态长度判定 =================
                if sensor_id in [self.DEV_ROTATE, self.DEV_SWING, self.DEV_TELES]:
                    frame_len = 4
                elif sensor_id in [self.DEV_ROTATE_ENC, self.DEV_SWING_ENC, self.DEV_TELES_ENC, self.DEV_PRESSURE]:
                    frame_len = 6
                elif sensor_id == self.DEV_GYRO:
                    frame_len = 26  # 2+6*4
                else:
                    buf = buf[1:]
                    continue

                if len(buf) < frame_len:
                    break

                frame = buf[:frame_len]
                buf = buf[frame_len:]

                timestamp_now = rospy.Time.now().to_sec()
                dt_str = rospy.Time.now().to_str() # 数据库Createtime格式

                # ================= 陀螺仪解析 =================
                if sensor_id == self.DEV_GYRO:
                    try:
                        ax, ay, az, gx, gy, gz = struct.unpack('<ffffff', frame[2:26])
                    except struct.error:
                        rospy.logwarn("陀螺仪数据解包失败！")
                        continue

                    val_tuple = (ax, ay, az, gx, gy, gz)
                    
                    if self.realtime_data.get(sensor_id) != val_tuple:
                        self.realtime_data[sensor_id] = val_tuple
                        json_data = f'{{"acc_x":{ax:.4f},"acc_y":{ay:.4f},"acc_z":{az:.4f},"gyro_x":{gx:.4f},"gyro_y":{gy:.4f},"gyro_z":{gz:.4f}}}'

                        # 写入 sensor_log 日志表（完全贴合你的表结构）
                        with self.db_lock:
                            try:
                                self.db_cursor.execute('''
                                    INSERT INTO sensor_log (Createtime, creater_id, Work_ID, sensor_ID, isread, data, del_flag, Notes)
                                    VALUES (?, ?, ?, ?, ?, ?, 0, ?)
                                ''', (dt_str, self.CREATER_ID, self.WORK_ID, sensor_id, 1, json_data, "陀螺仪实时数据"))
                                self.db_conn.commit()
                            except Exception as e:
                                rospy.logerr(f"陀螺仪数据库写入失败: {e}")

                        # 发布ROS消息
                        msg = GyroFeedback()
                        msg.header = Header(stamp=rospy.Time.now())
                        msg.module_id = module_id
                        msg.device_id = sensor_id
                        msg.accel_x = ax
                        msg.accel_y = ay
                        msg.accel_z = az
                        msg.gyro_x = gx
                        msg.gyro_y = gy
                        msg.gyro_z = gz
                        
                        self.pub_gyro.publish(msg)
                        self.last_parsed_msg = msg

                # ================= 普通传感器解析 =================
                else:
                    if frame_len == 4:
                        value = (frame[2] << 8) | frame[3]
                    elif frame_len == 6:
                        value = (frame[2] << 24) | (frame[3] << 16) | (frame[4] << 8) | frame[5]

                    if self.realtime_data.get(sensor_id) != value:
                        self.realtime_data[sensor_id] = value
                        json_data = f'{{"value":{value}}}'

                        # 写入 sensor_log 日志表
                        with self.db_lock:
                            try:
                                self.db_cursor.execute('''
                                    INSERT INTO sensor_log (Createtime, creater_id, Work_ID, sensor_ID, isread, data, del_flag, Notes)
                                    VALUES (?, ?, ?, ?, ?, ?, 0, ?)
                                ''', (dt_str, self.CREATER_ID, self.WORK_ID, sensor_id, 1, json_data, "传感器实时数据"))
                                self.db_conn.commit()
                            except Exception as e:
                                rospy.logerr(f"传感器数据库写入失败: {e}")

                        # 发布ROS消息
                        msg = Feedback()
                        msg.header = Header(stamp=rospy.Time.now())
                        msg.module_id = module_id
                        msg.device_id = sensor_id
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
    bridge = STM32Bridge()
    rospy.loginfo("硬件桥接节点启动")
    rospy.spin()
    bridge.close()