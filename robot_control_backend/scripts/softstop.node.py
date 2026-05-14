#!/usr/bin/env python3 
# -*- coding: utf-8 -*- 

import rospy 
import os 
import sqlite3 
import threading 
import json 
from robot_control_backend.msg import IntCmd 
from std_msgs.msg import Header 

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
        rospy.loginfo("✅ Loaded config from rob_arm.env") 

class ArmSQLiteDB: 
    """全局统一SQLite数据库操作类，适配 sensor_log 传感器日志表""" 
    def __init__(self): 
        self.db_path = os.path.join(os.path.expanduser('~'), "/home/yc/ws/robot_ws/src/ros_packgage/ros_database.db") 
        self.db_lock = threading.Lock() 
        self.conn = None 
        self.cursor = None 
        self.connect() 

    def connect(self): 
        """连接SQLite数据库""" 
        try: 
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False) 
            self.cursor = self.conn.cursor() 
            rospy.loginfo("✅ 软急停节点：成功连接机械臂SQLite数据库") 
        except Exception as e: 
            rospy.logerr(f"❌ SQLite数据库连接失败: {str(e)}") 

    def insert_sensor_log(self, creater_id, work_id, sensor_id, isread, data_dict, notes): 
        """严格匹配 sensor_log 表结构写入日志""" 
        with self.db_lock: 
            if not self.conn or not self.cursor: 
                self.connect() 
            try: 
                data_json = json.dumps(data_dict, ensure_ascii=False) 
                sql = """ 
                INSERT INTO sensor_log(creater_id, Work_ID, sensor_ID, isread, data, del_flag, Notes) 
                VALUES(?, ?, ?, ?, ?, ?, ?) 
                """ 
                params = (creater_id, work_id, sensor_id, isread, data_json, False, notes) 
                self.cursor.execute(sql, params) 
                self.conn.commit() 
                rospy.loginfo(f"✅ 软急停日志入库成功: sensor_id={sensor_id}, isread={isread}") 
            except Exception as e: 
                rospy.logerr(f"❌ 软急停日志入库失败: {str(e)}") 
                if self.conn: 
                    self.conn.rollback() 

    def close(self): 
        """关闭数据库连接""" 
        if self.conn: 
            self.conn.close() 

class EmergencyStopNode: 
    def __init__(self): 
        load_env_config() 
        rospy.init_node('softstop_node') 
        rospy.loginfo("✅ 软急停节点已启动（适配 sensor_log 传感器日志表）") 

        self.db = ArmSQLiteDB() 

        self.MODEL_ID = int(os.environ.get('MODEL_ID', '17')) 
        self.CREATER_ID = int(os.environ.get('CREATER_ID', '1')) 
        self.WORK_ID = int(os.environ.get('WORK_ID', '1')) 
        self.UNIT_ID = 32 

        default_module_id = int(os.environ.get('MODULE_ID', '17')) 
        self.stop_trigger_id = int(os.environ.get('TARGET_MODULE_ID', str(default_module_id))) 
        self.stop_cmd_module = int(os.environ.get('MODULE_ID', str(default_module_id))) 
        self.stop_cmd_device = 0 

        topic_arm_cmd = os.environ.get('ROS_TOPIC_ARM_CMD_VEL', '/arm/cmd_vel') 
        self.cmd_pub = rospy.Publisher(topic_arm_cmd, IntCmd, queue_size=10) 
        rospy.Subscriber('/control/softstop', IntCmd, self.cmd_callback, queue_size=10) 

        rospy.loginfo("Emergency stop node started, watching module_id=%d", self.stop_trigger_id) 

    def cmd_callback(self, msg): 
        if msg.module_id == self.stop_trigger_id: 
            rospy.logwarn("Emergency stop triggered by module_id %d", msg.module_id) 
            self.publish_stop(msg.module_id) 

    def publish_stop(self, trigger_module_id): 
        """构造并发布停止指令 + 写入sensor_log日志""" 
        stop_cmd = IntCmd() 
        stop_cmd.header = Header(stamp=rospy.Time.now()) 
        stop_cmd.module_id = self.stop_cmd_module 
        stop_cmd.device_id = self.stop_cmd_device 
        stop_cmd.position = [] 
        self.cmd_pub.publish(stop_cmd) 
        rospy.logdebug("Stop command sent: module=%d, device=%d, position=%s", 
                       stop_cmd.module_id, stop_cmd.device_id, stop_cmd.position) 

        timestamp = rospy.Time.now().to_sec() 
        data_dict = { 
            "event_type": "软急停触发", 
            "trigger_module_id": trigger_module_id, 
            "unit_id": self.UNIT_ID, 
            "device_address": self.stop_cmd_device, 
            "timestamp": round(timestamp, 2) 
        } 
        notes = f"一号机械臂软急停，触发模块：{trigger_module_id}，所有运动轴已停止" 
        
        self.db.insert_sensor_log( 
            creater_id=self.CREATER_ID, 
            work_id=self.WORK_ID, 
            sensor_id=self.stop_cmd_device, 
            isread=2, 
            data_dict=data_dict, 
            notes=notes 
        ) 

    def run(self): 
        rospy.spin() 

    def __del__(self): 
        """程序退出自动关闭数据库连接""" 
        self.db.close() 

if __name__ == '__main__': 
    try: 
        node = EmergencyStopNode() 
        node.run() 
    except rospy.ROSInterruptException: 
        rospy.loginfo("软急停节点已停止") 
    except Exception as e: 
        rospy.logerr(f"软急停节点异常: {str(e)}")