#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模块确认节点 V2 —— 基于 CAN「到位通知」事件帧的三重到位判定

V2 到位通知 ArriveNotification 字段：
    module_id, device_id, angle(int32, 0.01°), pos_error(int16), status_bits(uint8), flags(uint8)

V2 到位判定（三重校验，对齐设计文档 §5.3.5 StatusBits 定义）：
    1. |angle - 目标| <= MODULE_CONFIRM_TOLERANCE（0.01° 单位）
    2. status_bits 的到位位（**bit2=0x04**）置位
    3. |pos_error| <= 容差

工作流：
    1. 上位机向 /control/module_cmd 下发目标（IntCmd，position[0] 为 0.01° 角度）
       → 转发到 /arm/cmd_vel，并登记待确认记录
    2. 到位事件 /hardware/arrive_notification 到达 → 按 device_id 匹配并三重校验
    3. 超差或超时 → 失败
"""
import os

import rospy
from std_msgs.msg import Header
from robot_control_backend.msg import IntCmd, ArriveNotification


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


class ModuleConfirm:
    RESULT_SUCCESS = 100
    RESULT_FAILED = -1
    # V2 status_bits（对齐设计文档 §5.3.5 轴状态字定义）：
    #   bit0 使能　bit1 运行　**bit2 到位**　bit3 上限位　bit4 下限位
    #   bit5 故障　bit6 轴忙　bit7 急停锁存　bit8 基准有效
    STATUS_IN_POSITION_MASK = 0x04  # bit2 = 到位位置位

    def __init__(self):
        load_env_config()
        rospy.init_node("module_confirme_node")
        rospy.loginfo("✅ 模块确认节点 V2 已启动（到位三重判定：角度+PosError+Status）")

        # V2：容差单位为 0.01°（配置 MODULE_CONFIRM_TOLERANCE，100 = 1.00°）
        self.tolerance = int(os.environ['MODULE_CONFIRM_TOLERANCE'])
        self.timeout_sec = float(os.environ['MODULE_CONFIRM_TIMEOUT'])

        # 话题全部只读 rob_arm.env（无硬编码默认值，env 改了上下游自动一致）
        TOPIC_ARM_CMD_VEL = os.environ['ROS_TOPIC_ARM_CMD_VEL']
        TOPIC_MODULE_CONFIRM_SUCCESS = os.environ['ROS_TOPIC_MODULE_CONFIRM_SUCCESS']
        TOPIC_MODULE_CONFIRM_FAILED = os.environ['ROS_TOPIC_MODULE_CONFIRM_FAILED']
        TOPIC_MODULE_CMD = os.environ['ROS_TOPIC_MODULE_CMD']
        TOPIC_ARRIVE = os.environ['ROS_TOPIC_ARRIVE_NOTIFICATION']

        self.pub_cmd = rospy.Publisher(TOPIC_ARM_CMD_VEL, IntCmd, queue_size=10)
        self.pub_success = rospy.Publisher(TOPIC_MODULE_CONFIRM_SUCCESS, IntCmd, queue_size=10)
        self.pub_failed = rospy.Publisher(TOPIC_MODULE_CONFIRM_FAILED, IntCmd, queue_size=10)

        rospy.Subscriber(TOPIC_MODULE_CMD, IntCmd, self.cb_upper_cmd)
        rospy.Subscriber(TOPIC_ARRIVE, ArriveNotification, self.cb_arrive)

        # V2：待确认记录按 device_id 索引
        self.pending = {}

        rospy.Timer(rospy.Duration(0.2), self._check_timeout)

    def cb_upper_cmd(self, msg):
        device_id = int(msg.device_id)
        # V2：device_id 即轴号 1~20（到位确认仅针对运动轴）
        if not (1 <= device_id <= 20):
            rospy.logwarn("⚠️ 模块确认指令 device_id=%d 非法（允许轴号 1~20），已忽略", device_id)
            return
        if not msg.position:
            rospy.logwarn("⚠️ 模块确认指令缺少目标位置 position，已忽略")
            return

        target_centideg = int(msg.position[0])

        self.pub_cmd.publish(msg)

        self.pending[device_id] = {
            "module_id": msg.module_id,
            "device_id": device_id,
            "target": target_centideg,
            "deadline": rospy.Time.now() + rospy.Duration(self.timeout_sec),
        }
        rospy.loginfo("[模块确认] 已下发并登记 device_id=%d 目标角度=%.2f°（超时%.1fs）",
                      device_id, target_centideg * 0.01, self.timeout_sec)

    def cb_arrive(self, msg):
        device_id = int(msg.device_id)
        record = self.pending.get(device_id)
        if record is None:
            rospy.loginfo("收到 device_id=%d 到位通知，但无待确认记录，忽略", device_id)
            return

        target = record["target"]
        actual_angle = int(msg.angle)
        pos_error = int(msg.pos_error)
        status_bits = int(msg.status_bits)

        # V2 三重判定
        angle_diff = abs(actual_angle - target)
        in_position = bool(status_bits & self.STATUS_IN_POSITION_MASK)
        error_ok = abs(pos_error) <= self.tolerance
        angle_ok = angle_diff <= self.tolerance

        if angle_ok and in_position and error_ok:
            self._publish_result(self.pub_success, record, self.RESULT_SUCCESS,
                                 "到位成功 device=%d 角度差=%d(0.01°) PosError=%d Status=0x%02X"
                                 % (device_id, angle_diff, pos_error, status_bits))
        else:
            self._publish_result(self.pub_failed, record, self.RESULT_FAILED,
                                 "到位判定失败 device=%d angle_ok=%s in_pos=%s error_ok=%s "
                                 "角度差=%d PosError=%d Status=0x%02X"
                                 % (device_id, angle_ok, in_position, error_ok,
                                    angle_diff, pos_error, status_bits))
        del self.pending[device_id]

    def _check_timeout(self, _event):
        now = rospy.Time.now()
        expired = [did for did, rec in self.pending.items() if now >= rec["deadline"]]
        for did in expired:
            record = self.pending.pop(did)
            self._publish_result(self.pub_failed, record, self.RESULT_FAILED,
                                 "到位超时 device=%d 目标=%.2f°（>%.1fs）"
                                 % (did, record["target"] * 0.01, self.timeout_sec))

    def _publish_result(self, publisher, record, result_code, log_text):
        m = IntCmd()
        m.header = Header(stamp=rospy.Time.now())
        m.module_id = record["module_id"]
        m.device_id = record["device_id"]
        m.position = [result_code]
        publisher.publish(m)
        if result_code == self.RESULT_SUCCESS:
            rospy.loginfo("[模块确认成功] %s", log_text)
        else:
            rospy.logwarn("[模块确认失败] %s", log_text)

    def run(self):
        rospy.spin()


if __name__ == "__main__":
    try:
        node = ModuleConfirm()
        node.run()
    except rospy.ROSInterruptException:
        rospy.loginfo("❌ 模块确认节点停止")
    except Exception as e:
        rospy.logerr("❌ 模块节点异常: %s" % str(e))
