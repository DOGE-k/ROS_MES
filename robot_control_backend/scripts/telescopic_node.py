#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
伸缩轴节点 V2

V2 变更：
  - 支持 5 臂
  - 伸缩轴 axis ∈ {4,8,12,16,20}，arm_idx=(axis-1)//4（J4，每臂第4轴）
  - 位置量从编码器 tick 改为绝对角度（0.01°，int32）
  - mm ↔ 角度机械换算：angle_deg = length_mm × (360 / MM_PER_REV)
  - 删除 ENC_MID/ENC_MIN/ENC_MAX/DEGREE_PER_TICK 等编码器系数
"""
import rospy
import os
import sqlite3
import json
from datetime import datetime
from std_msgs.msg import Header
from robot_control_backend.msg import TelescopicCmd, IntCmd

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

class TelescopeSimple:
    def __init__(self):
        load_env_config()
        rospy.init_node("telescope_simple_node")
        rospy.loginfo("✅ 伸缩轴节点 启动（5 臂，mm↔角度 0.01°）")

        # V2：module_id 不做静态配置，cmd_callback 从指令消息（msg.module_id）透传
        # V2 机械换算：每转导程 MM_PER_REV mm → 360°，即 1mm = 360/MM_PER_REV 度
        mm_per_rev = float(os.environ['MM_PER_REV'])
        self.deg_per_mm = 360.0 / mm_per_rev
        self.mm_per_deg = mm_per_rev / 360.0

        self.MIN_LENGTH = float(os.environ['MIN_LENGTH_MM'])
        self.MAX_LENGTH = float(os.environ['MAX_LENGTH_MM'])
        # V2：单次伸缩增量限幅（mm），与 kinematics_node 共用同一配置
        self.MAX_DELTA_MM = float(os.environ['TELESCOPIC_MAX_DELTA_MM'])

        # 只订阅一个统一下发的话题（控制节点输出的 _sequenced）；话题只读 rob_arm.env
        TOPIC_CMD = os.environ['ROS_TOPIC_KINEMATICS_TELESCOPIC_CMD_SEQ']
        TOPIC_TELESCOPE_FEEDBACK = os.environ['ROS_TOPIC_TELESCOPE_FEEDBACK']
        TOPIC_TELESCOPE_OUTPUT = os.environ['ROS_TOPIC_TELESCOPE_OUTPUT']

        self.lengths = {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}
        self.axis_ready = {0: False, 1: False, 2: False, 3: False, 4: False}

        rospy.Subscriber(TOPIC_CMD, TelescopicCmd, self.cmd_callback)
        rospy.Subscriber(TOPIC_TELESCOPE_FEEDBACK, TelescopicCmd, self.feedback_callback)
        self.output_pub = rospy.Publisher(TOPIC_TELESCOPE_OUTPUT, IntCmd, queue_size=10)

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
        """V2：device_id 即轴号；伸缩轴 axis ∈ {4,8,12,16,20}，arm_idx=(axis-1)//4"""
        axis = int(device_id)
        if axis in (4, 8, 12, 16, 20):
            return (axis - 1) // 4
        return -1

    def cmd_callback(self, msg):
        device_id = msg.device_id
        arm_idx = self._device_to_arm_idx(device_id)
        if arm_idx < 0:
            rospy.logwarn(f"伸缩节点收到无法识别的 device_id: {device_id}")
            return

        target_delta_mm = msg.position[0]
        # 基准保护：首帧反馈到达前不知道当前长度，拒绝增量累加
        if not self.axis_ready[arm_idx]:
            rospy.logwarn_throttle(2.0,
                f"⚠️ Arm{arm_idx+1} 伸缩轴尚无反馈基准，请先回零/等待反馈，本次增量 {target_delta_mm:+.2f}mm 已拒绝")
            return
        target_delta_mm = max(-self.MAX_DELTA_MM, min(target_delta_mm, self.MAX_DELTA_MM))

        current_length = self.lengths[arm_idx]
        target_reach_mm = current_length + target_delta_mm
        target_reach_mm = max(self.MIN_LENGTH, min(target_reach_mm, self.MAX_LENGTH))

        # V2：mm → 角度 → 0.01°（int32）
        target_deg = target_reach_mm * self.deg_per_mm
        target_centi_deg = int(round(target_deg * 100))

        int_cmd_msg = IntCmd()
        int_cmd_msg.header = Header(stamp=rospy.Time.now())
        int_cmd_msg.module_id = msg.module_id
        int_cmd_msg.device_id = device_id
        int_cmd_msg.position = [target_centi_deg]
        self.output_pub.publish(int_cmd_msg)

        self._insert_sensor_log(msg.module_id, device_id, target_centi_deg, "下发伸缩指令数据")
        rospy.loginfo(f"Arm{arm_idx+1} 伸缩指令：{target_delta_mm:+.2f}mm → 下发角度(0.01°)：{target_centi_deg}")

    def feedback_callback(self, msg):
        """V2：feedback_node 已换算为角度（°），再换算回 mm 存储，并置基准就绪标志"""
        arm_idx = self._device_to_arm_idx(msg.device_id)
        if arm_idx >= 0:
            angle_deg = msg.position[0]
            self.lengths[arm_idx] = angle_deg * self.mm_per_deg
            if not self.axis_ready[arm_idx]:
                self.axis_ready[arm_idx] = True
                rospy.loginfo(f"✅ Arm{arm_idx+1} 伸缩轴基准已建立（首帧反馈 {self.lengths[arm_idx]:+.2f}mm），允许增量控制")

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
