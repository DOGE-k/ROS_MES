#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import rospy
import os
import sqlite3
import json
from datetime import datetime
from std_msgs.msg import Header
from robot_control_backend.msg import RotationCmd, IntCmd

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

class RotationSimple:
    def __init__(self):
        load_env_config()
        rospy.init_node("rotation_simple_node")
        rospy.loginfo("旋转轴节点启动")

        # 编码器换算系数（从环境变量读取）
        self.DEGREE_PER_TICK = float(os.environ.get('DEGREE_PER_TICK', '0.01248'))
        self.MODULE_ID = int(os.environ.get('MODULE_ID', '17'))
        self.DEV_ROTATE_CONTROL = int(os.environ.get('DEV_ROTATE_CONTROL', '33'))
        self.DEV_SENSOR = int(os.environ.get('DEV_SENSOR', '49'))

        # 编码器限位
        self.ENC_MID = int(os.environ.get('ENC_MID', '15000'))
        self.ENC_MIN = int(os.environ.get('ENC_MIN', '580'))
        self.ENC_MAX = int(os.environ.get('ENC_MAX', '29420'))

        # 话题名称
        TOPIC_ADJUST_ROTATION_CMD = os.environ.get('ROS_TOPIC_ADJUST_ROTATION_CMD', '/control/adjust_rotation_cmd')
        TOPIC_KINEMATICS_ROTATION_CMD = os.environ.get('ROS_TOPIC_KINEMATICS_ROTATION_CMD', '/control/kinematics_rotation_cmd')
        TOPIC_ROTATION_FEEDBACK = os.environ.get('ROS_TOPIC_ROTATION_FEEDBACK', '/hardware/rotation_feedback')
        TOPIC_ROTATION_OUTPUT = os.environ.get('ROS_TOPIC_ROTATION_OUTPUT', '/hardware/rotation_output')
        TOPIC_SENSOR_CMD = os.environ.get('ROS_TOPIC_SENSOR_CMD', '/control/sensor_cmd')

        # 核心变量
        self.target_delta_deg = 0.0
        self.current_angle_deg = 0.0
        self.target_reach_deg = 0.0

        # 订阅双指令
        rospy.Subscriber(TOPIC_ADJUST_ROTATION_CMD, RotationCmd, self.cmd_callback)
        rospy.Subscriber(TOPIC_KINEMATICS_ROTATION_CMD, RotationCmd, self.cmd_callback)
        rospy.Subscriber(TOPIC_ROTATION_FEEDBACK, RotationCmd, self.feedback_callback)

        # 发布输出
        self.output_pub = rospy.Publisher(TOPIC_ROTATION_OUTPUT, IntCmd, queue_size=10)
        self.sensor_cmd_pub = rospy.Publisher(TOPIC_SENSOR_CMD, IntCmd, queue_size=10)

        # ------------------ 数据库初始化 ------------------
        db_path = rospy.get_param("~db_path", "ros_database.db")
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._create_table()
        rospy.loginfo("✅ 数据库已连接，路径: %s", db_path)

    def _create_table(self):
        """创建 sensor_log 表（如果不存在）"""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS sensor_log (
                Createtime DATETIME NOT NULL PRIMARY KEY,
                creater_id INTEGER,
                Work_ID INTEGER,
                sensor_ID INTEGER,
                isread INTEGER,
                data TEXT,
                del_flag INTEGER DEFAULT 0,
                Notes TEXT
            )
        """)
        self.conn.commit()

    def _insert_sensor_log(self, model_id, device_id, position, note_str):
        """插入一条传感器日志，sensor_ID 填 device_id"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S.") + f"{datetime.now().microsecond:06d}"[:6]
        data_json = json.dumps({
            "model_id": model_id,
            "device_id": device_id,
            "position": position
        })
        try:
            self.conn.execute("""
                INSERT INTO sensor_log (Createtime, creater_id, Work_ID, sensor_ID, isread, data, del_flag, Notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (now, 1, 1, device_id, 2, data_json, 0, note_str))
            self.conn.commit()
        except Exception as e:
            rospy.logerr("数据库写入失败: %s", e)

    def cmd_callback(self, msg):
        """接收增量指令 → 计算目标 → 只发一次命令"""
        self.target_delta_deg = msg.position[0]
        self.target_reach_deg = self.current_angle_deg + self.target_delta_deg

        # 角度 → 编码器编码（带限位）
        target_tick = self.ENC_MID + int(round(self.target_reach_deg / self.DEGREE_PER_TICK))
        target_tick = max(self.ENC_MIN, min(target_tick, self.ENC_MAX))

        # 构建旋转电机指令
        int_cmd_msg = IntCmd()
        int_cmd_msg.header = Header()
        int_cmd_msg.header.stamp = rospy.Time.now()
        int_cmd_msg.module_id = self.MODULE_ID
        int_cmd_msg.device_id = self.DEV_ROTATE_CONTROL
        int_cmd_msg.position = [target_tick]

        # 构建传感器指令（position=0）
        sen_cmd_msg = IntCmd()
        sen_cmd_msg.header = Header()
        sen_cmd_msg.header.stamp = rospy.Time.now()
        sen_cmd_msg.module_id = self.MODULE_ID
        sen_cmd_msg.device_id = self.DEV_SENSOR
        sen_cmd_msg.position = 0

        # 发布
        self.output_pub.publish(int_cmd_msg)
        self.sensor_cmd_pub.publish(sen_cmd_msg)

        # 写入数据库（两条记录，sensor_ID 均填对应的 device_id）
        self._insert_sensor_log(self.MODULE_ID, self.DEV_ROTATE_CONTROL, target_tick, "下发旋转指令数据")
        self._insert_sensor_log(self.MODULE_ID, self.DEV_SENSOR, 0, "下发传感器指令数据")

        # 日志
        cmd_topic = msg._connection_header.get('topic', '未知话题')
        if cmd_topic == os.environ.get('ROS_TOPIC_ADJUST_ROTATION_CMD', '/control/adjust_rotation_cmd'):
            rospy.loginfo("旋转轴微调：+%.4f° → 下发编码：%d" % (self.target_delta_deg, target_tick))
        elif cmd_topic == os.environ.get('ROS_TOPIC_KINEMATICS_ROTATION_CMD', '/control/kinematics_rotation_cmd'):
            rospy.loginfo("旋转轴运动学：+%.4f° → 下发编码：%d" % (self.target_delta_deg, target_tick))

    def feedback_callback(self, msg):
        """仅更新当前角度，监控状态"""
        if msg.device_id == self.DEV_ROTATE_CONTROL or msg.device_id == int(os.environ.get('DEV_ROTATE', '41')):
            self.current_angle_deg = msg.position[0]

    def shutdown_hook(self):
        self.conn.close()
        rospy.loginfo("数据库连接已关闭")

if __name__ == "__main__":
    try:
        node = RotationSimple()
        rospy.on_shutdown(node.shutdown_hook)
        rospy.spin()
    except rospy.ROSInterruptException:
        rospy.loginfo("旋转轴节点停止")
    except Exception as e:
        rospy.logerr("旋转轴异常：%s" % str(e))