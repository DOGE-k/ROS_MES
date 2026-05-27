#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import rospy
import os
import sqlite3
import json
from datetime import datetime
from std_msgs.msg import Header
from robot_control_backend.msg import SwingCmd, IntCmd

def load_env_config():
    env_path = os.path.join(os.path.dirname(__file__), '../rob_arm.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    os.environ[key] = value
        rospy.loginfo("✅ 已从 rob_arm.env 加载配置")

class SwingSimple:
    def __init__(self):
        load_env_config()
        rospy.init_node("swing_simple_node")
        rospy.loginfo("✅ 摆动轴节点启动 (支持 Arm1/2/3，统一下发话题，反馈转角度)")

        self.DEGREE_PER_TICK = float(os.environ.get('DEGREE_PER_TICK', '0.01248'))
        self.MODULE_ID = int(os.environ.get('MODULE_ID', '17'))
        self.ENC_MID = int(os.environ.get('ENC_MID', '15000'))
        self.ENC_MIN = int(os.environ.get('ENC_MIN', '580'))
        self.ENC_MAX = int(os.environ.get('ENC_MAX', '29420'))

        # 只订阅一个统一下发的话题（控制节点输出的 _sequenced）
        TOPIC_CMD = os.environ.get('ROS_TOPIC_KINEMATICS_SWING_CMD_SEQ', '/control/kinematics_swing_cmd_sequenced')
        TOPIC_SWING_FEEDBACK = os.environ.get('ROS_TOPIC_SWING_FEEDBACK', '/hardware/swing_feedback')
        TOPIC_SWING_OUTPUT = os.environ.get('ROS_TOPIC_SWING_OUTPUT', '/hardware/swing_output')

        self.angles = {0: 0.0, 1: 0.0, 2: 0.0}   # 存储实际角度（度）

        rospy.Subscriber(TOPIC_CMD, SwingCmd, self.cmd_callback)
        rospy.Subscriber(TOPIC_SWING_FEEDBACK, SwingCmd, self.feedback_callback)
        self.output_pub = rospy.Publisher(TOPIC_SWING_OUTPUT, IntCmd, queue_size=10)

        # ------------------ 数据库初始化 ------------------
        db_path = os.environ.get('DB_PATH', "ros_database.db")
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._create_table()
        rospy.loginfo("✅ 数据库已连接，路径: %s", db_path)

        rospy.loginfo(f"订阅指令话题: {TOPIC_CMD}")

    def _create_table(self):
        """创建 sensor_log 表（如果不存在）"""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS sensor_log (
                Createtime DATETIME NOT NULL,
                creater_id INTEGER NOT NULL,
                Work_ID INTEGER NOT NULL,
                sensor_ID INTEGER NOT NULL,
                isread INTEGER NOT NULL,
                data TEXT NOT NULL,
                del_flag BOOL DEFAULT false,
                Notes TEXT,
                PRIMARY KEY (Createtime, sensor_ID)
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

    def _device_to_arm_idx(self, device_id):
        if device_id == 34: return 0
        if device_id == 66: return 1
        if device_id == 98: return 2
        return -1

    def _tick_to_angle(self, tick):
        """编码器 tick → 角度（°）"""
        return (tick - self.ENC_MID) * self.DEGREE_PER_TICK

    def cmd_callback(self, msg):
        device_id = msg.device_id
        arm_idx = self._device_to_arm_idx(device_id)
        if arm_idx < 0:
            rospy.logwarn(f"摆动节点收到无法识别的 device_id: {device_id}")
            return

        target_delta_deg = msg.position[0]
        current_angle = self.angles[arm_idx]
        target_reach_deg = current_angle + target_delta_deg

        target_tick = self.ENC_MID + int(round(target_reach_deg / self.DEGREE_PER_TICK))
        target_tick = max(self.ENC_MIN, min(target_tick, self.ENC_MAX))

        int_cmd_msg = IntCmd()
        int_cmd_msg.header = Header(stamp=rospy.Time.now())
        int_cmd_msg.module_id = msg.module_id
        int_cmd_msg.device_id = device_id
        int_cmd_msg.position = [target_tick]
        self.output_pub.publish(int_cmd_msg)

        # 写入数据库
        self._insert_sensor_log(msg.module_id, device_id, target_tick, "下发摆动指令数据")

        rospy.loginfo(f"Arm{arm_idx+1} 摆动指令：{target_delta_deg:+.4f}° → 下发编码：{target_tick}")

    def feedback_callback(self, msg):
        """将编码器 tick 转换为角度后存储"""
        arm_idx = self._device_to_arm_idx(msg.device_id)
        if arm_idx >= 0:
            tick = msg.position[0]
            self.angles[arm_idx] = self._tick_to_angle(tick)

    def shutdown_hook(self):
        self.conn.close()
        rospy.loginfo("数据库连接已关闭")

if __name__ == "__main__":
    try:
        node = SwingSimple()
        rospy.on_shutdown(node.shutdown_hook)
        rospy.spin()
    except rospy.ROSInterruptException:
        rospy.loginfo("摆动轴节点停止")
    except Exception as e:
        rospy.logerr("摆动轴异常：%s" % str(e))