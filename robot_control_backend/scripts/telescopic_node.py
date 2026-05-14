#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import rospy
import os
import sqlite3
import json
from datetime import datetime
from std_msgs.msg import Header
from robot_control_backend.msg import TelescopicCmd, IntCmd

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

class TelescopeSimple:
    def __init__(self):
        load_env_config()
        rospy.init_node("telescope_simple_node")
        rospy.loginfo("✅ 伸缩轴节点启动")

        # 1. 电机参数
        self.DEGREE_PER_TICK = float(os.environ.get('DEGREE_PER_TICK', '0.01248'))
        self.MM_PER_REV = float(os.environ.get('MM_PER_REV', '0.7'))
        self.TICK_PER_MM = (360.0 / self.MM_PER_REV) / self.DEGREE_PER_TICK
        self.MODULE_ID = int(os.environ.get('MODULE_ID', '17'))
        self.DEV_TELES_CONTROL = int(os.environ.get('DEV_TELES_CONTROL', '35'))
        self.DEV_TELES = int(os.environ.get('DEV_TELES', '43'))
        self.DEV_SENSOR = int(os.environ.get('DEV_SENSOR', '49'))

        # 编码器硬件限位
        self.ENC_MID = int(os.environ.get('ENC_MID', '15000'))
        self.ENC_MIN = int(os.environ.get('ENC_MIN', '580'))
        self.ENC_MAX = int(os.environ.get('ENC_MAX', '29420'))

        # 长度机械限位
        self.MIN_LENGTH = float(os.environ.get('MIN_LENGTH', '0.0'))
        self.MAX_LENGTH = float(os.environ.get('MAX_LENGTH', '150.0'))

        rospy.loginfo("参数：1mm ≈ %.2f 编码，长度限位 %.1f-%.1fmm" %
                     (self.TICK_PER_MM, self.MIN_LENGTH, self.MAX_LENGTH))

        # 话题名称
        TOPIC_ADJUST_TELESCOPIC_CMD = os.environ.get('ROS_TOPIC_ADJUST_TELESCOPIC_CMD', '/control/adjust_telescopic_cmd')
        TOPIC_KINEMATICS_TELESCOPIC_CMD = os.environ.get('ROS_TOPIC_KINEMATICS_TELESCOPIC_CMD', '/control/kinematics_telescopic_cmd')
        TOPIC_TELESCOPE_FEEDBACK = os.environ.get('ROS_TOPIC_TELESCOPE_FEEDBACK', '/hardware/telescope_feedback')
        TOPIC_TELESCOPE_OUTPUT = os.environ.get('ROS_TOPIC_TELESCOPE_OUTPUT', '/hardware/telescope_output')
        TOPIC_SENSOR_CMD = os.environ.get('ROS_TOPIC_SENSOR_CMD', '/control/sensor_cmd')

        # 核心变量
        self.target_delta_mm = 0.0
        self.current_length_mm = 0.0
        self.target_reach_mm = 0.0

        # 订阅双指令 + 反馈
        rospy.Subscriber(TOPIC_ADJUST_TELESCOPIC_CMD, TelescopicCmd, self.cmd_callback)
        rospy.Subscriber(TOPIC_KINEMATICS_TELESCOPIC_CMD, TelescopicCmd, self.cmd_callback)
        rospy.Subscriber(TOPIC_TELESCOPE_FEEDBACK, TelescopicCmd, self.feedback_callback)

        # 发布输出
        self.output_pub = rospy.Publisher(TOPIC_TELESCOPE_OUTPUT, IntCmd, queue_size=10)
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
        """收到指令 → 计算 → 只发一次"""
        self.target_delta_mm = msg.position[0]

        # 安全限制
        self.target_delta_mm = max(-50, min(self.target_delta_mm, 50))

        # 计算目标长度
        self.target_reach_mm = self.current_length_mm + self.target_delta_mm
        self.target_reach_mm = max(self.MIN_LENGTH, min(self.target_reach_mm, self.MAX_LENGTH))

        # 长度 → 编码值
        target_tick = self.ENC_MID + int(round(self.target_reach_mm * self.TICK_PER_MM))
        target_tick = max(self.ENC_MIN, min(target_tick, self.ENC_MAX))

        # 构建伸缩电机指令
        int_cmd_msg = IntCmd()
        int_cmd_msg.header = Header()
        int_cmd_msg.header.stamp = rospy.Time.now()
        int_cmd_msg.module_id = self.MODULE_ID
        int_cmd_msg.device_id = self.DEV_TELES_CONTROL
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
        self._insert_sensor_log(self.MODULE_ID, self.DEV_TELES_CONTROL, target_tick, "下发伸缩指令数据")
        self._insert_sensor_log(self.MODULE_ID, self.DEV_SENSOR, 0, "下发传感器指令数据")

        # 日志
        cmd_topic = msg._connection_header.get('topic', '未知话题')
        if cmd_topic == os.environ.get('ROS_TOPIC_ADJUST_TELESCOPIC_CMD', '/control/adjust_telescopic_cmd'):
            rospy.loginfo("伸缩轴微调：+%.2fmm → 下发编码：%d" % (self.target_delta_mm, target_tick))
        elif cmd_topic == os.environ.get('ROS_TOPIC_KINEMATICS_TELESCOPIC_CMD', '/control/kinematics_telescopic_cmd'):
            rospy.loginfo("伸缩轴运动学：+%.2fmm → 下发编码：%d" % (self.target_delta_mm, target_tick))

    def feedback_callback(self, msg):
        """仅更新当前长度，不写数据库"""
        if msg.device_id == self.DEV_TELES_CONTROL or msg.device_id == self.DEV_TELES:
            self.current_length_mm = msg.position[0]

    def shutdown_hook(self):
        self.conn.close()
        rospy.loginfo("数据库连接已关闭")

if __name__ == "__main__":
    try:
        node = TelescopeSimple()
        rospy.on_shutdown(node.shutdown_hook)
        rospy.spin()
    except rospy.ROSInterruptException:
        rospy.loginfo("伸缩轴节点停止")
    except Exception as e:
        rospy.logerr("伸缩轴异常：%s" % str(e))