#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
旋转轴节点 V2

V2 变更：
  - 支持 5 臂，每臂 3 轴：旋转轴 axis ∈ {1,4,7,10,13}，arm_idx=(axis-1)//3
  - 控制语义：输入相对增量角度（°），维护软件位置变量，未超限时原样透传增量（0.01°，int16）
  - 下发前检查：位置变量 + 增量 > 限位则丢弃该指令、变量不变，并回执超位 CmdAck
  - 反馈只用于定初值；反馈中断超过 FEEDBACK_TIMEOUT 后恢复时用新反馈重建变量
"""
import rospy
import os
import time
import sqlite3
import json
from datetime import datetime
from std_msgs.msg import Header
from robot_control_backend.msg import RotationCmd, IntCmd, CmdAck

def load_env_config():
    """从 .env 文件加载配置"""
    env_path = os.path.join(os.path.dirname(__file__), '../rob_arm.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value
        rospy.loginfo("✅ 已从 rob_arm.env 加载配置")

class RotationSimple:
    def __init__(self):
        load_env_config()
        rospy.init_node("rotation_simple_node")
        rospy.loginfo("旋转轴节点 V2 启动（5 臂×3 轴，增量透传，角度 0.01°）")

        # 话题只读 rob_arm.env（env 改了自动生效，无硬编码默认值）
        TOPIC_CMD = os.environ['ROS_TOPIC_KINEMATICS_ROTATION_CMD_SEQ']
        TOPIC_ROTATION_FEEDBACK = os.environ['ROS_TOPIC_ROTATION_FEEDBACK']
        TOPIC_ROTATION_OUTPUT = os.environ['ROS_TOPIC_ROTATION_OUTPUT']

        # 旋转轴绝对角度软限位（°）
        self.ROT_MIN = float(os.environ['ROTATION_MIN_ANGLE'])
        self.ROT_MAX = float(os.environ['ROTATION_MAX_ANGLE'])
        # 反馈中断阈值（秒）：超过该时长后恢复反馈，视为基准漂移并用新反馈重建软件位置变量
        self.FEEDBACK_TIMEOUT = 1.0

        # V2：5 臂软件位置变量（度）；axis_ready 标记该臂是否已收到首帧反馈（基准已知）
        self.angles = {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}
        self.axis_ready = {0: False, 1: False, 2: False, 3: False, 4: False}
        self.last_fb_time = {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}

        rospy.Subscriber(TOPIC_CMD, RotationCmd, self.cmd_callback)
        rospy.Subscriber(TOPIC_ROTATION_FEEDBACK, RotationCmd, self.feedback_callback)
        self.output_pub = rospy.Publisher(TOPIC_ROTATION_OUTPUT, IntCmd, queue_size=10)
        self.pub_cmd_ack = rospy.Publisher(os.environ['ROS_TOPIC_CMD_ACK'], CmdAck, queue_size=10)

        # ------------------ 数据库初始化 ------------------
        db_path = os.environ['DB_PATH']
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

    def _insert_sensor_log(self, module_id, device_id, position, note_str):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        data_json = json.dumps({
            "module_id": module_id,
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
        """V2：device_id 即轴号；旋转轴 axis ∈ {1,4,7,10,13}，arm_idx=(axis-1)//3"""
        axis = int(device_id)
        if axis in (1, 4, 7, 10, 13):
            return (axis - 1) // 3
        return -1

    def _publish_over_limit(self, msg, detail, new_angle):
        """回执超位 CmdAck：ack_msg=1、result=3（参数越界）、detail=1 上限 / 2 下限"""
        ack = CmdAck()
        ack.header = Header(stamp=rospy.Time.now())
        ack.module_id = msg.module_id
        ack.device_id = msg.device_id
        ack.ack_msg = 1
        ack.result = 3
        ack.detail = detail
        self.pub_cmd_ack.publish(ack)

    def cmd_callback(self, msg):
        device_id = msg.device_id
        arm_idx = self._device_to_arm_idx(device_id)
        if arm_idx < 0:
            rospy.logwarn(f"旋转节点收到无法识别的 device_id: {device_id}")
            return
        if not self.axis_ready.get(arm_idx, False):
            rospy.logwarn_throttle(2.0,
                f"⚠️ Arm{arm_idx+1} 尚未收到首帧反馈（基准未知），拒绝旋转增量指令，请先等待反馈")
            return

        delta_deg = float(msg.position[0])
        new_angle = self.angles[arm_idx] + delta_deg

        # 下发前检查：超限则丢弃指令、软件位置变量保持不变
        if new_angle > self.ROT_MAX or new_angle < self.ROT_MIN:
            detail = 1 if new_angle > self.ROT_MAX else 2
            self._publish_over_limit(msg, detail, new_angle)
            rospy.logwarn("⚠️ Arm%d 旋转超位：当前 %.3f° + 增量 %.3f° = %.3f° 超出 [%.1f, %.1f]，指令已丢弃",
                          arm_idx + 1, self.angles[arm_idx], delta_deg, new_angle,
                          self.ROT_MIN, self.ROT_MAX)
            return

        self.angles[arm_idx] = new_angle

        # 未超限：原样透传增量（0.01°，int16）
        delta_centi_deg = int(round(delta_deg * 100))
        int_cmd_msg = IntCmd()
        int_cmd_msg.header = Header(stamp=rospy.Time.now())
        int_cmd_msg.module_id = msg.module_id
        int_cmd_msg.device_id = device_id
        int_cmd_msg.position = [delta_centi_deg]
        self.output_pub.publish(int_cmd_msg)

        self._insert_sensor_log(msg.module_id, device_id, delta_centi_deg, "下发旋转增量数据")
        rospy.loginfo(f"Arm{arm_idx+1} 旋转增量：{delta_deg:+.4f}° → 下发 {delta_centi_deg}(0.01°) | 位置变量 {new_angle:+.3f}°")

    def feedback_callback(self, msg):
        """反馈仅用于定初值；反馈中断超过阈值后恢复时，用新反馈重建软件位置变量"""
        arm_idx = self._device_to_arm_idx(msg.device_id)
        if arm_idx < 0:
            return
        now = time.time()
        if not self.axis_ready[arm_idx]:
            self.angles[arm_idx] = msg.position[0]
            self.axis_ready[arm_idx] = True
            rospy.loginfo(f"✅ Arm{arm_idx+1} 旋转轴基准已建立（首帧反馈 {msg.position[0]:+.3f}°），允许增量控制")
        elif now - self.last_fb_time[arm_idx] > self.FEEDBACK_TIMEOUT:
            self.angles[arm_idx] = msg.position[0]
            rospy.logwarn(f"♻️ Arm{arm_idx+1} 旋转反馈中断 {now - self.last_fb_time[arm_idx]:.2f}s 后恢复，已用新反馈 {msg.position[0]:+.3f}° 重建位置变量")
        self.last_fb_time[arm_idx] = now

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
