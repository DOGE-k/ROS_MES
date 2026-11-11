#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
伸缩轴节点 V2

V2 变更：
  - 支持 5 臂，每臂 3 轴：伸缩轴 axis ∈ {3,6,9,12,15}，arm_idx=(axis-1)//3（J3，每臂第3轴）
  - 伸缩长度绝对范围 0~30mm（TELESCOPIC_MIN_MM / TELESCOPIC_MAX_MM）
  - 控制语义：输入相对增量（mm），维护软件长度变量，未超限时把增量按 0.01mm 原样透传
  - 下发前检查：长度变量 + 增量超限则丢弃该指令、变量不变，并回执超位 CmdAck
  - 单位：电机3 为直线位移轴，下行增量/上行反馈的 CAN 字段均为 0.01mm（不再是角度）
  - 反馈只用于定初值；反馈中断超过 FEEDBACK_TIMEOUT 后恢复时用新反馈重建变量
"""
import rospy
import os
import time
import sqlite3
import json
from datetime import datetime
from std_msgs.msg import Header
from robot_control_backend.msg import TelescopicCmd, IntCmd, CmdAck

def load_env_config():
    env_path = os.path.join(os.path.dirname(__file__), '../rob_arm.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value
        rospy.loginfo("✅ 已从 rob_arm.env 加载配置")

class TelescopeSimple:
    def __init__(self):
        load_env_config()
        rospy.init_node("telescope_simple_node")
        rospy.loginfo("✅ 伸缩轴节点 启动（5 臂×3 轴，0~30mm，增量按 0.01mm 透传）")

        # 电机3 为直线位移轴：CAN 字段单位为 0.01mm，不再做 mm↔角度 换算
        # （台架标定 1cm=177847 counts，counts 换算由下位机固件完成）
        # V2：module_id 不做静态配置，cmd_callback 从指令消息（msg.module_id）透传

        # 伸缩长度绝对软限位（mm）
        self.MIN_MM = float(os.environ['TELESCOPIC_MIN_MM'])
        self.MAX_MM = float(os.environ['TELESCOPIC_MAX_MM'])
        # 反馈中断阈值（秒）：超过该时长后恢复反馈，用新反馈重建软件长度变量
        self.FEEDBACK_TIMEOUT = 1.0

        # 只订阅一个统一下发的话题（控制节点输出的 _sequenced）；话题只读 rob_arm.env
        TOPIC_CMD = os.environ['ROS_TOPIC_KINEMATICS_TELESCOPIC_CMD_SEQ']
        TOPIC_TELESCOPE_FEEDBACK = os.environ['ROS_TOPIC_TELESCOPE_FEEDBACK']
        TOPIC_TELESCOPE_OUTPUT = os.environ['ROS_TOPIC_TELESCOPE_OUTPUT']

        # 零点由人工调零，下位机不回传基准信息：软件基准固定为 0mm
        self.lengths = {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}
        self.axis_ready = {0: True, 1: True, 2: True, 3: True, 4: True}
        self.last_fb_time = {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}

        rospy.Subscriber(TOPIC_CMD, TelescopicCmd, self.cmd_callback)
        rospy.Subscriber(TOPIC_TELESCOPE_FEEDBACK, TelescopicCmd, self.feedback_callback)
        self.output_pub = rospy.Publisher(TOPIC_TELESCOPE_OUTPUT, IntCmd, queue_size=10)
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
        """插入一条传感器日志，sensor_ID 填 device_id"""
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
        """V2：device_id 即轴号；伸缩轴 axis ∈ {3,6,9,12,15}，arm_idx=(axis-1)//3"""
        axis = int(device_id)
        if axis in (3, 6, 9, 12, 15):
            return (axis - 1) // 3
        return -1

    def _publish_over_limit(self, msg, detail, new_len):
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
            rospy.logwarn(f"伸缩节点收到无法识别的 device_id: {device_id}")
            return

        delta_mm = float(msg.position[0])
        new_len = self.lengths[arm_idx] + delta_mm

        # 下发前检查：超限则丢弃指令、软件长度变量保持不变
        if new_len > self.MAX_MM or new_len < self.MIN_MM:
            detail = 1 if new_len > self.MAX_MM else 2
            self._publish_over_limit(msg, detail, new_len)
            rospy.logwarn("⚠️ Arm%d 伸缩超位：当前 %.3fmm + 增量 %.3fmm = %.3fmm 超出 [%.1f, %.1f]，指令已丢弃",
                          arm_idx + 1, self.lengths[arm_idx], delta_mm, new_len,
                          self.MIN_MM, self.MAX_MM)
            return

        self.lengths[arm_idx] = new_len

        # 未超限：mm → 0.01mm 原样透传（直线位移轴下发距离，不换算角度）
        delta_centi_mm = int(round(delta_mm * 100))
        int_cmd_msg = IntCmd()
        int_cmd_msg.header = Header(stamp=rospy.Time.now())
        int_cmd_msg.module_id = msg.module_id
        int_cmd_msg.device_id = device_id
        int_cmd_msg.position = [delta_centi_mm]
        self.output_pub.publish(int_cmd_msg)

        self._insert_sensor_log(msg.module_id, device_id, delta_centi_mm, "下发伸缩增量数据")
        rospy.loginfo(f"Arm{arm_idx+1} 伸缩增量：{delta_mm:+.3f}mm → 下发 {delta_centi_mm}(0.01mm) | 长度变量 {new_len:+.3f}mm")

    def feedback_callback(self, msg):
        """零点由人工调零，下位机不回传基准：反馈仅记录时间戳，不参与长度变量计算"""
        arm_idx = self._device_to_arm_idx(msg.device_id)
        if arm_idx < 0:
            return
        self.last_fb_time[arm_idx] = time.time()

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
