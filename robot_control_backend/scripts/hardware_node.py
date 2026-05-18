#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import rospy
import serial
import threading
import traceback
import sqlite3
import os
import struct
import json
import datetime  # 新增：用于生成带毫秒的时间戳防主键冲突

from std_msgs.msg import Header
from robot_control_backend.msg import Feedback, IntCmd, GyroFeedback 

class STM32Bridge:
    def __init__(self, port="/dev/ttyUSB0", baud=115200):
        self.port = port
        self.baud = baud
        self.ser = None
        self.serial_lock = threading.Lock()
        self.running = True
        self.connected = False
        self.last_sent_data = None

        # 话题发布者
        self.pub_all_feedback = rospy.Publisher("/hardware/all_feedback", Feedback, queue_size=10)
        self.pub_gyro = rospy.Publisher("/hardware/gyroscope_feedback", GyroFeedback, queue_size=10)
        rospy.Subscriber("/arm/cmd_vel", IntCmd, self.on_cmd_received)

        self.serial_buffer = b""
        self.stop_frame = b"\x11\x00\x00\x00"
        self.receive_stopped = False

        # 设备 ID 定义 
        self.TARGET_MODULE_ID = 0x11
        self.DEV_ROTATE = 41
        self.DEV_SWING  = 42
        self.DEV_TELES  = 43
        self.DEV_SENSOR = 49
        self.DEV_GYRO   = 50

        self.realtime_data = {}

        # ================== 新版数据库连接 ==================
        self.db_lock = threading.Lock()
        # 指向生成的 ros_database.db
        self.db_path = os.path.join(os.path.dirname(__file__), "ros_database.db")
        self.db_conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.db_cursor = self.db_conn.cursor()
        
        # 开启 WAL 模式，提升 SQLite 并发写入性能
        self.db_cursor.execute("PRAGMA journal_mode=WAL;")
        
        # 批量提交机制，防止高频 IO 锁死磁盘
        self.uncommitted_changes = False
        self.db_commit_timer = rospy.Timer(rospy.Duration(1.0), self.sync_database)
        rospy.loginfo(f" 数据库已挂载: {self.db_path}")

        self.try_serial_connect()
        self.start_read_thread()
        self.parse_timer = rospy.Timer(rospy.Duration(0.01), self.parse_frames)

    # -------------------------------------------------------------------------
    def try_serial_connect(self):
        with self.serial_lock:
            try:
                if self.ser is not None and self.ser.is_open:
                    self.ser.close()
                self.ser = serial.Serial(
                    port=self.port, baudrate=self.baud, 
                    bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE, 
                    stopbits=serial.STOPBITS_ONE, timeout=0.1
                )
                self.connected = True
                rospy.loginfo(f"串口已连接: {self.port}")
            except Exception as e:
                self.connected = False

    # -------------------------------------------------------------------------
    def sync_database(self, event):
        """定时器：每秒将缓冲区的数据统一刷入磁盘 (解决高频写入卡顿)"""
        if self.uncommitted_changes:
            with self.db_lock:
                try:
                    self.db_conn.commit()
                    self.uncommitted_changes = False
                except Exception as e:
                    self.db_conn.rollback()
                    rospy.logerr(f"数据库批量提交失败，已回滚: {e}")

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
            self.last_sent_data = None # 异常后释放锁，允许下次重发

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
                device_id = buf[1] # 这个直接对应你数据库的 sensor_ID

                if module_id != self.TARGET_MODULE_ID:
                    buf = buf[1:]
                    continue

                if device_id in [self.DEV_ROTATE, self.DEV_SWING, self.DEV_TELES]:
                    frame_len = 4
                elif device_id == self.DEV_SENSOR:
                    frame_len = 6
                elif device_id == self.DEV_GYRO:
                    frame_len = 26 
                else:
                    buf = buf[1:]
                    continue

                if len(buf) < frame_len: break

                frame = buf[:frame_len]
                buf = buf[frame_len:]

                # 生成带毫秒的时间戳，防止 100Hz 写入时主键冲突
                now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

                # ================= 陀螺仪多维数据写入 =================
                if device_id == self.DEV_GYRO:
                    try:
                        ax, ay, az, gx, gy, gz = struct.unpack('<ffffff', frame[2:26])
                    except struct.error:
                        continue

                    val_tuple = (ax, ay, az, gx, gy, gz)
                    
                    if self.realtime_data.get(device_id) != val_tuple:
                        self.realtime_data[device_id] = val_tuple
                        
                        # 转换成 JSON 文本存入 TEXT 字段
                        gyro_json_data = json.dumps({
                            "acc": [ax, ay, az],
                            "gyro": [gx, gy, gz]
                        })

                        with self.db_lock:
                            try:
                                # creater_id=1(admin), Work_ID=1(初始工作), isread=1
                                self.db_cursor.execute('''
                                    INSERT INTO sensor_log (Createtime, creater_id, Work_ID, sensor_ID, isread, data)
                                    VALUES (?, 1, 1, ?, 1, ?)
                                ''', (now_str, device_id, gyro_json_data))
                                self.uncommitted_changes = True
                            except Exception as e:
                                pass

                        msg = GyroFeedback()
                        msg.header = Header(stamp=rospy.Time.now())
                        msg.module_id = module_id
                        msg.device_id = device_id
                        msg.accel_x, msg.accel_y, msg.accel_z = ax, ay, az
                        msg.gyro_x, msg.gyro_y, msg.gyro_z = gx, gy, gz
                        self.pub_gyro.publish(msg)

                # ================= 普通单维传感器写入 =================
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
                                    INSERT INTO sensor_log (Createtime, creater_id, Work_ID, sensor_ID, isread, data)
                                    VALUES (?, 1, 1, ?, 1, ?)
                                ''', (now_str, device_id, str(float(value))))
                                self.uncommitted_changes = True
                            except Exception as e:
                                pass

                        msg = Feedback()
                        msg.header = Header(stamp=rospy.Time.now())
                        msg.module_id = module_id
                        msg.device_id = device_id
                        msg.position = [float(value)]
                        self.pub_all_feedback.publish(msg)

            self.serial_buffer = buf

    # -------------------------------------------------------------------------
    def close(self):
        self.running = False
        if self.ser and self.ser.is_open:
            self.ser.close()
        # 退出前强制提交最后的数据
        if self.uncommitted_changes:
            with self.db_lock:
                self.db_conn.commit()
        if hasattr(self, 'db_conn'):
            with self.db_lock:
                self.db_conn.close()

if __name__ == "__main__":
    rospy.init_node("stm32_bridge")
    bridge = STM32Bridge("/dev/ttyUSB0", 115200)
    rospy.loginfo("已挂载数据库）")
    rospy.spin()
    bridge.close()