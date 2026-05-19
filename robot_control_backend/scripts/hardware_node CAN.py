#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import rospy
import threading
import sqlite3
import os
import struct
import json
import datetime
import can      # 新增：CAN 总线核心库
import queue    # 新增：网关异步队列

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
        rospy.loginfo("已从 rob_arm.env 加载配置")

class CANBusGateway:
    def __init__(self):
        load_env_config()
        
        # 从环境变量读取 CAN 配置，默认 can0, 1M 波特率
        self.channel = os.environ.get('CAN_CHANNEL', 'can0')
        self.bitrate = int(os.environ.get('CAN_BITRATE', '1000000'))
        
        self.bus = None
        self.running = True
        self.last_sent_data = None
        
        # ================== 网关核心：异步解耦队列 ==================
        self.rx_queue = queue.Queue(maxsize=2000)

        # ================== 话题发布者（从环境变量读取） ==================
        TOPIC_ALL_FEEDBACK = os.environ.get('ROS_TOPIC_ALL_FEEDBACK', '/hardware/all_feedback')
        TOPIC_ARM_CMD_VEL = os.environ.get('ROS_TOPIC_ARM_CMD_VEL', '/arm/cmd_vel')
        
        self.pub_all_feedback = rospy.Publisher(TOPIC_ALL_FEEDBACK, Feedback, queue_size=50)
        self.pub_gyro = rospy.Publisher("/hardware/gyroscope_feedback", GyroFeedback, queue_size=50)
        rospy.Subscriber(TOPIC_ARM_CMD_VEL, IntCmd, self.on_cmd_received)

        # ================== 动态路由表 (基于环境变量的 ID) ==================
        self.TARGET_MODULE_ID = int(os.environ.get('MODULE_ID', '17'))
        dev_rotate = int(os.environ.get('DEV_ROTATE', '41'))
        dev_swing  = int(os.environ.get('DEV_SWING', '42'))
        dev_teles  = int(os.environ.get('DEV_TELES', '43'))
        dev_sensor = int(os.environ.get('DEV_SENSOR', '49'))
        dev_gyro   = 50 # 陀螺仪基准 ID

        self.device_registry = {
            dev_rotate: {'type': 'motor'},
            dev_swing:  {'type': 'motor'},
            dev_teles:  {'type': 'motor'},
            dev_sensor: {'type': 'sensor'},
            dev_gyro:   {'type': 'imu_part1'}, # 陀螺仪分3帧发
            dev_gyro+1: {'type': 'imu_part2'},
            dev_gyro+2: {'type': 'imu_part3'},
        }

        self.gyro_cache = {}
        self.realtime_data = {}

        # ================== MES 数据库连接 ==================
        self.db_lock = threading.Lock()
        self.db_path = os.path.join(os.path.dirname(__file__), "ros_database.db")
        self.db_conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.db_cursor = self.db_conn.cursor()
        self.db_cursor.execute("PRAGMA journal_mode=WAL;")
        
        self.uncommitted_changes = False
        self.db_commit_timer = rospy.Timer(rospy.Duration(1.0), self.sync_database)
        rospy.loginfo(f"✅ MES 数据库已连接: {self.db_path}")

        # 初始化并启动 CAN 网关多线程
        self.init_can_bus()
        self.start_gateway_threads()

    # -------------------------------------------------------------------------
    def init_can_bus(self):
        try:
            self.bus = can.interface.Bus(channel=self.channel, bustype='socketcan', bitrate=self.bitrate)
            rospy.loginfo(f"CAN 网关已启动: {self.channel} @ {self.bitrate}bps")
        except Exception as e:
            rospy.logerr(f"CAN 网关初始化失败: {e}")

    # -------------------------------------------------------------------------
    def sync_database(self, event):
        """批量提交数据库"""
        if self.uncommitted_changes:
            with self.db_lock:
                try:
                    self.db_conn.commit()
                    self.uncommitted_changes = False
                except Exception as e:
                    self.db_conn.rollback()

    # -------------------------------------------------------------------------
    def on_cmd_received(self, msg):
        """下行路由：ROS -> CAN"""
        if not self.bus: return
        
        did = msg.device_id
        pos = int(msg.position[0])
        if (did, pos) == self.last_sent_data: return
        
        try:
            # 组装 11位 CAN ID：高4位为指令标识 0x1，低7位为设备号 did
            can_id = (0x1 << 7) | (did & 0x7F)
            
            # 只需要发纯粹的 4 字节数据 (小端序 integer)
            payload = struct.pack('<i', pos)
            
            self.bus.send(can.Message(arbitration_id=can_id, data=payload, is_extended_id=False))
            self.last_sent_data = (did, pos)
        except Exception as e:
            self.last_sent_data = None
            rospy.logerr(f"CAN 发送失败: {e}")

    # =========================================================================
    # 网关核心架构：生产者-消费者双线程解耦
    # =========================================================================

    def can_rx_worker(self):
        """线程 1：读取 CAN 总线，塞入队列"""
        while self.running and not rospy.is_shutdown():
            if not self.bus:
                rospy.sleep(1)
                continue
            try:
                msg = self.bus.recv(timeout=0.5)
                if msg:
                    if self.rx_queue.full():
                        self.rx_queue.get_nowait() # 防雪崩保护
                    self.rx_queue.put(msg)
            except Exception:
                pass

    def dispatch_worker(self):
        """线程 2：处理业务、写数据库、发 ROS 话题"""
        dev_gyro_base = 50 # 陀螺仪基准ID
        
        while self.running and not rospy.is_shutdown():
            try:
                msg = self.rx_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            # 拆解 CAN ID
            msg_type = (msg.arbitration_id >> 7) & 0x0F
            device_id = msg.arbitration_id & 0x7F
            
            # 只处理上报数据 (假设反馈数据高4位为 0x2)
            if msg_type != 0x2 or device_id not in self.device_registry:
                continue

            dev_info = self.device_registry[device_id]
            now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

            # --- 分支 A：陀螺仪多帧拼接 ---
            if 'imu' in dev_info['type']:
                try:
                    val1, val2 = struct.unpack('<ff', msg.data)
                except:
                    continue
                    
                self.gyro_cache[device_id] = (val1, val2)
                
                if (dev_gyro_base in self.gyro_cache and 
                    dev_gyro_base+1 in self.gyro_cache and 
                    dev_gyro_base+2 in self.gyro_cache):
                    
                    ax, ay = self.gyro_cache[dev_gyro_base]
                    az, gx = self.gyro_cache[dev_gyro_base+1]
                    gy, gz = self.gyro_cache[dev_gyro_base+2]
                    
                    val_tuple = (ax, ay, az, gx, gy, gz)
                    if self.realtime_data.get(dev_gyro_base) != val_tuple:
                        self.realtime_data[dev_gyro_base] = val_tuple
                        
                        gyro_json = json.dumps({"acc": [ax, ay, az], "gyro": [gx, gy, gz]})
                        self._db_insert(now_str, dev_gyro_base, gyro_json)
                        
                        ros_msg = GyroFeedback(header=Header(stamp=rospy.Time.now()), module_id=self.TARGET_MODULE_ID, device_id=dev_gyro_base)
                        ros_msg.accel_x, ros_msg.accel_y, ros_msg.accel_z = ax, ay, az
                        ros_msg.gyro_x, ros_msg.gyro_y, ros_msg.gyro_z = gx, gy, gz
                        self.pub_gyro.publish(ros_msg)
                        
                    self.gyro_cache.clear()

            # --- 分支 B：普通传感器/电机 ---
            elif dev_info['type'] in ['motor', 'sensor']:
                if len(msg.data) == 4:
                    value = struct.unpack('<i', msg.data)[0]
                    
                    if self.realtime_data.get(device_id) != value:
                        self.realtime_data[device_id] = value
                        self._db_insert(now_str, device_id, str(float(value)))
                        
                        ros_msg = Feedback(header=Header(stamp=rospy.Time.now()), module_id=self.TARGET_MODULE_ID, device_id=device_id)
                        ros_msg.position = [float(value)]
                        self.pub_all_feedback.publish(ros_msg)

    # -------------------------------------------------------------------------
    def _db_insert(self, time_str, sensor_id, data_str):
        """内部通用数据库写入 (写入 MES 架构)"""
        with self.db_lock:
            try:
                self.db_cursor.execute('''
                    INSERT INTO sensor_log (Createtime, creater_id, Work_ID, sensor_ID, isread, data)
                    VALUES (?, 1, 1, ?, 1, ?)
                ''', (time_str, sensor_id, data_str))
                self.uncommitted_changes = True
            except Exception as e:
                pass

    # -------------------------------------------------------------------------
    def start_gateway_threads(self):
        t_rx = threading.Thread(target=self.can_rx_worker)
        t_rx.daemon = True
        t_rx.start()
        
        t_dispatch = threading.Thread(target=self.dispatch_worker)
        t_dispatch.daemon = True
        t_dispatch.start()
        
    def close(self):
        self.running = False
        if self.uncommitted_changes:
            with self.db_lock:
                self.db_conn.commit()
        if hasattr(self, 'db_conn'):
            with self.db_lock:
                self.db_conn.close()
        if self.bus:
            self.bus.shutdown()

if __name__ == "__main__":
    rospy.init_node("hardware_node") # 配合算法组命名
    bridge = CANBusGateway() 
    rospy.loginfo(" CAN 网关节点启动（已对接 MES）")
    rospy.spin()
    bridge.close()