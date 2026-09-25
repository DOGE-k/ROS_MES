#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
摆动轴节点 V2

V2 变更：
  - 支持 5 臂
  - 摆动轴 axis ∈ {2,6,10,14,18}，arm_idx=(axis-1)//4
  - 摆动角上限 ±15°（V1.1 为 ±20°，由 MAX_SWING_ANGLE 配置）
  - 位置量从编码器 tick 改为绝对角度（0.01°，int32）
"""
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
        rospy.loginfo("✅ 摆动轴节点 V2 启动（5 臂，±15°，角度 0.01°）")

        # V2：module_id 不做静态配置，cmd_callback 从指令消息（msg.module_id）透传
        self.MAX_SWING_ANGLE = float(os.environ['MAX_SWING_ANGLE'])

        # 只订阅一个统一下发的话题（控制节点输出的 _sequenced）；话题只读 rob_arm.env
        TOPIC_CMD = os.environ['ROS_TOPIC_KINEMATICS_SWING_CMD_SEQ']
        TOPIC_SWING_FEEDBACK = os.environ['ROS_TOPIC_SWING_FEEDBACK']
        TOPIC_SWING_OUTPUT = os.environ['ROS_TOPIC_SWING_OUTPUT']

        self.angles = {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}
        # 各臂基准就绪标志：首帧反馈到达前拒绝增量指令（避免按 0 位累加跳变）
        self.axis_ready = {0: False, 1: False, 2: False, 3: False, 4: False}

        rospy.Subscriber(TOPIC_CMD, SwingCmd, self.cmd_callback)
        rospy.Subscriber(TOPIC_SWING_FEEDBACK, SwingCmd, self.feedback_callback)
        self.output_pub = rospy.Publisher(TOPIC_SWING_OUTPUT, IntCmd, queue_size=10)

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
                PRIMARY KEY (Createtime, sensor_ID),
                FOREIGN KEY (creater_id) REFERENCES Users(User_ID),
                FOREIGN KEY (Work_ID) REFERENCES works(Work_ID),
                FOREIGN KEY (sensor_id) REFERENCES sensors(id)
            )
        """)
        self.conn.commit()

    def _insert_sensor_log(self, module_id, device_id, position, note_str):
        """插入一条传感器日志，sensor_ID 填 device_id"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S.") + f"{datetime.now().microsecond:06d}"[:6]
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
        """V2：device_id 即轴号；摆动轴 axis ∈ {2,6,10,14,18}，arm_idx=(axis-1)//4"""
        axis = int(device_id)
        if axis in (2, 6, 10, 14, 18):
            return (axis - 1) // 4
        return -1

    def cmd_callback(self, msg):
        device_id = msg.device_id
        arm_idx = self._device_to_arm_idx(device_id)
        if arm_idx < 0:
            rospy.logwarn(f"摆动节点收到无法识别的 device_id: {device_id}")
            return

        target_delta_deg = msg.position[0]
        # 基准保护：首帧反馈到达前不知道当前角，拒绝增量累加
        if not self.axis_ready[arm_idx]:
            rospy.logwarn_throttle(2.0,
                f"⚠️ Arm{arm_idx+1} 摆动轴尚无反馈基准，请先回零/等待反馈，本次增量 {target_delta_deg:+.4f}° 已拒绝")
            return
        current_angle = self.angles[arm_idx]
        target_reach_deg = current_angle + target_delta_deg
        # V2 摆动角限幅 ±15°
        target_reach_deg = max(-self.MAX_SWING_ANGLE, min(target_reach_deg, self.MAX_SWING_ANGLE))

        # V2：直接输出绝对角度（0.01°）
        target_centi_deg = int(round(target_reach_deg * 100))

        int_cmd_msg = IntCmd()
        int_cmd_msg.header = Header(stamp=rospy.Time.now())
        int_cmd_msg.module_id = msg.module_id
        int_cmd_msg.device_id = device_id
        int_cmd_msg.position = [target_centi_deg]
        self.output_pub.publish(int_cmd_msg)

        self._insert_sensor_log(msg.module_id, device_id, target_centi_deg, "下发摆动指令数据")
        rospy.loginfo(f"Arm{arm_idx+1} 摆动指令：{target_delta_deg:+.4f}° → 下发角度(0.01°)：{target_centi_deg}")

    def feedback_callback(self, msg):
        """V2：feedback_node 已换算为角度（°），存储并置基准就绪标志"""
        arm_idx = self._device_to_arm_idx(msg.device_id)
        if arm_idx >= 0:
            self.angles[arm_idx] = msg.position[0]
            if not self.axis_ready[arm_idx]:
                self.axis_ready[arm_idx] = True
                rospy.loginfo(f"✅ Arm{arm_idx+1} 摆动轴基准已建立（首帧反馈 {msg.position[0]:+.3f}°），允许增量控制")

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
