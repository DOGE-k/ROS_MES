#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""虚拟三轴遥测节点（模拟 /hardware/axis_status 与三轴位置反馈）。

仅用于前端联调，不参与任何控制决策，默认不随 roslaunch 启动，由人工按需启动：
    rosrun robot_control_backend sim_axis_status_node.py

背景：
  1) 下位机固件不发 msg=3 轴状态字帧 → /hardware/axis_status 无消息；
  2) 固件空闲时不发位置帧 → /hardware/can/*_raw 无消息；
  后端微调批次在发送前要求「三轴新鲜 axis_status（base_valid=1 且空闲）
  + 三轴新鲜编码器反馈」，缺任一都会 10s 后 blocked，运动帧不会下发。

模拟口径：
  - 位置反馈恒为 0（零点由人工调零，模拟基准固定为 0，不随真实到位角变化）；
  - 状态：收到 /arm/cmd_vel → RUN(1)；收到真实到位事件 → ARRIVE(2) 保持 0.6s → IDLE(0)；
  - base_valid 恒为 1（基准视为有效）。
"""
import os
import threading
import time

import rospy
from std_msgs.msg import Header
from robot_control_backend.msg import AxisStatus, Feedback, ArriveNotification, IntCmd

# 遥测话题的 module_id 是 CAN SEG 位域（ROS_MODULE_SEG_MAP 里模块 17 → SEG 0），
# 前后端都用 feedback.module_id === confirmedSeg 过滤，不能用业务模块号 17。
MODULE_ID = int(os.environ.get('SIM_MODULE_SEG', '0'))
TOPICS = {
    1: '/hardware/rotation_feedback',
    2: '/hardware/swing_feedback',
    3: '/hardware/telescope_feedback',
}
ARRIVE_TOPIC = '/hardware/arrive_notification'
STATUS_TOPIC = '/hardware/axis_status'
CMD_TOPIC = '/arm/cmd_vel'

BASE_POSITION = 0.0   # 模拟基准固定为 0
ARRIVE_HOLD_S = 0.6
RUN_TIMEOUT_S = 3.0


class _Axis:
    def __init__(self):
        self.running = False
        self.arrive_until = 0.0
        self.run_since = 0.0


def main():
    rospy.init_node('sim_axis_status')
    lock = threading.Lock()
    axes = {ax: _Axis() for ax in TOPICS}
    pubs = {ax: rospy.Publisher(TOPICS[ax], Feedback, queue_size=20) for ax in TOPICS}
    pub = rospy.Publisher(STATUS_TOPIC, AxisStatus, queue_size=30)

    def cmd_cb(msg):
        axis = int(msg.device_id)
        if axis not in axes or not msg.position:
            return
        now = time.monotonic()
        with lock:
            axes[axis].running = True
            axes[axis].run_since = now

    def arrive_cb(msg):
        axis = int(msg.device_id)
        if axis not in axes:
            return
        now = time.monotonic()
        with lock:
            a = axes[axis]
            a.running = False
            a.arrive_until = now + ARRIVE_HOLD_S

    rospy.Subscriber(CMD_TOPIC, IntCmd, cmd_cb, queue_size=50)
    rospy.Subscriber(ARRIVE_TOPIC, ArriveNotification, arrive_cb, queue_size=50)

    rate = rospy.Rate(5)
    rospy.loginfo("虚拟三轴遥测已启动：5Hz，轴1/2/3，位置固定 %.1f°，base_valid=1",
                  BASE_POSITION)
    while not rospy.is_shutdown():
        now = time.monotonic()
        stamp = rospy.Time.now()
        with lock:
            for axis, a in axes.items():
                if a.running and now - a.run_since > RUN_TIMEOUT_S:
                    a.running = False
                    a.arrive_until = now + ARRIVE_HOLD_S
                if a.running:
                    state, bits = 1, 0x0002
                elif now < a.arrive_until:
                    state, bits = 2, 0x0004
                else:
                    state, bits = 0, 0x0000
                pubs[axis].publish(Feedback(
                    header=Header(stamp=stamp), module_id=MODULE_ID,
                    device_id=axis, position=[BASE_POSITION]))
                pub.publish(AxisStatus(
                    header=Header(stamp=stamp), module_id=MODULE_ID,
                    device_id=axis, status_bits=bits, axis_state=state, base_valid=1))
        rate.sleep()


if __name__ == '__main__':
    main()
