#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
压力传感器控制节点 - 独立节点（立即响应版）
订阅话题：/control/sensor_cmd
发布话题：/arm/cmd_vel (IntCmd)

功能：接收触发信号后，立即发送压力传感器开关序列（关→0.5s→开）
"""

import rospy
import os
import time
import sqlite3
import json
from std_msgs.msg import Header
from robot_control_backend.msg import IntCmd

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

# ====================== 数据库：强制建表，绝对成功 ======================
def setup_database():
    # 直接用工作目录下的 ros_database.db，和节点A/B 完全一致
    db_path = os.environ.get('DB_PATH', "ros_database.db")
    
    # 线程安全，防止ROS报错
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cursor = conn.cursor()

    # 强制建表，不存在就创建
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sensor_logs (
        Createtime DATETIME NOT NULL,
        creater_id INTEGER NOT NULL,
        Work_ID INTEGER NOT NULL,
        sensor_ID INTEGER NOT NULL,
        isread INTEGER NOT NULL,
        data TEXT NOT NULL,
        del_flag BOOL DEFAULT false,
        Notes TEXT,
        PRIMARY KEY (Createtime, sensor_ID)
    );
    """)
    conn.commit()
    rospy.loginfo("✅ 数据库表 sensor_logs 已创建/已存在")
    return conn

# ====================== 写入数据库 ======================
def log_sensor_state(conn, sensor_id, state, action_desc):
    try:
        cursor = conn.cursor()
        data_json = json.dumps({"state": state}, ensure_ascii=False)
        notes_json = json.dumps({"action": action_desc}, ensure_ascii=False)

        cursor.execute("""
        INSERT INTO sensor_logs (Createtime, creater_id, Work_ID, sensor_ID, isread, data, del_flag, Notes)
        VALUES (datetime('now'), 1, 1, ?, 2, ?, 0, ?)
        """, (sensor_id, data_json, notes_json))
        conn.commit()
        rospy.loginfo(f"✅ 数据库写入成功：sensor={sensor_id}, state={state}")
    except Exception as e:
        rospy.logerr(f"❌ 数据库写入失败：{e}")

class PressureSensorControlNode:
    def __init__(self):
        load_env_config()
        rospy.init_node("pressure_sensor_control_node")
        
        # 配置参数（从环境变量读取）
        self.DEV_SENSOR = int(os.environ.get('DEV_SENSOR', '49'))
        
        rospy.loginfo(f"压力传感器控制节点已启动（立即响应模式）")

        # 话题名称（从环境变量读取）
        TOPIC_ARM_CMD_VEL = os.environ.get('ROS_TOPIC_ARM_CMD_VEL', '/arm/cmd_vel')
        TOPIC_SENSOR_CMD = os.environ.get('ROS_TOPIC_SENSOR_CMD', '/control/sensor_cmd')

        # 发布：向下位机发送压力传感器开关指令
        self.pub_sensor_cmd = rospy.Publisher(TOPIC_ARM_CMD_VEL, IntCmd, queue_size=10)

        # 订阅：触发信号
        rospy.Subscriber(TOPIC_SENSOR_CMD, IntCmd, self.trigger_callback)

        # 数据库（自动建表）
        self.db_conn = setup_database()

    def trigger_callback(self, msg):
        """收到触发信号 → 立即发送压力传感器开关序列"""
        target_module_id = msg.module_id
        rospy.loginfo(f"📡 收到传感器触发指令，module_id={target_module_id}，立即执行")
        self.send_sensor_sequence(target_module_id)

    def send_sensor_sequence(self, module_id):
        """发送压力传感器开关序列（2帧，间隔0.5秒）"""
        rospy.loginfo("🔌 发送压力传感器指令序列")

        # 第1帧：关闭
        cmd1 = IntCmd()
        cmd1.header = Header()
        cmd1.header.stamp = rospy.Time.now()
        cmd1.module_id = module_id
        cmd1.device_id = self.DEV_SENSOR
        cmd1.position = [0]
        self.pub_sensor_cmd.publish(cmd1)
        log_sensor_state(self.db_conn, self.DEV_SENSOR, 0, "关闭压力传感器")
        rospy.loginfo(f"压力传感器指令1: module={module_id}, pos=0")

        # 延迟0.5秒发送第2帧
        time.sleep(0.5)

        # 第2帧：打开
        cmd2 = IntCmd()
        cmd2.header = Header()
        cmd2.header.stamp = rospy.Time.now()
        cmd2.module_id = module_id
        cmd2.device_id = self.DEV_SENSOR
        cmd2.position = [1]
        self.pub_sensor_cmd.publish(cmd2)
        log_sensor_state(self.db_conn, self.DEV_SENSOR, 1, "打开压力传感器")
        rospy.loginfo(f"压力传感器指令2: module={module_id}, pos=1")

        rospy.loginfo("✅ 压力传感器指令序列发送完成")

    def shutdown_hook(self):
        self.db_conn.close()
        rospy.loginfo("✅ 数据库连接已关闭")

if __name__ == '__main__':
    try:
        node = PressureSensorControlNode()
        rospy.on_shutdown(node.shutdown_hook)
        rospy.spin()
    except rospy.ROSInterruptException:
        rospy.loginfo("❌ 压力传感器控制节点已停止")