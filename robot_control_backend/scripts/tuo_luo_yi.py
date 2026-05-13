#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IMU 角度 + 末端坐标发布节点（正运动学，不漂移）
订阅：/hardware/gyroscope_feedback (GyroFeedback)
发布：/imu_angles (tuo_luo_yi)
"""

import rospy
import math
import numpy as np
from std_msgs.msg import Header
from robot_control_backend.msg import GyroFeedback, tuo_luo_yi

# ==================== 宏定义 ====================
# 陀螺仪初始姿态（竖直向上，指向前方）
INITIAL_ROLL  = 0.0          # 弧度
INITIAL_PITCH = 0.0
INITIAL_YAW   = 0.0

GRAVITY = 9.81               # m/s²
ACCEL_UNIT_IS_G = False      # 加速度单位是否为 g

# Mahony 互补滤波参数
KP = 0.5
KI = 0.05
ACC_TRUST_THRESH = 1.0       # m/s²

# 机械臂设备 ID 映射
ARM_BASE_IDS = [32, 64, 96]
GYRO_OFFSET = 18

# 底座在世界坐标系中的位置 (cm)
BASE_X = 0.0
BASE_Y = 0.0
BASE_Z = 0.0

# 摆动轴中心到底座的高度 (cm) —— 杆竖直时，摆动中心在底座上方这个高度
SWING_CENTER_HEIGHT = 30.0   # 请按实际修改

# 当前伸缩杆长度 (cm) —— 从摆动中心到末端的距离
TELESCOPIC_LENGTH = 50.0     # 请按实际修改，未来可改为动态获取
# ========================================================

class ImuAnglePublisher:
    def __init__(self):
        rospy.init_node('imu_angle_publisher')
        self.states = {}       # key: (module_id, arm_id)

        rospy.Subscriber('/hardware/gyroscope_feedback', GyroFeedback, self.imu_callback)
        self.angle_pub = rospy.Publisher('/imu_angles', tuo_luo_yi, queue_size=10)
        rospy.loginfo("IMU 角度+坐标节点启动 (正运动学)")

    def _get_arm_id(self, device_id):
        base = device_id - GYRO_OFFSET
        if base in ARM_BASE_IDS:
            return ARM_BASE_IDS.index(base) + 1
        return None

    def _ensure_state(self, module_id, arm_id):
        key = (module_id, arm_id)
        if key not in self.states:
            self.states[key] = {
                'quat':     self._euler_to_quat(INITIAL_ROLL, INITIAL_PITCH, INITIAL_YAW),
                'eInt':     np.zeros(3),
                'last_time': None
            }
        return self.states[key]

    @staticmethod
    def _euler_to_quat(roll, pitch, yaw):
        cy = math.cos(yaw * 0.5)
        sy = math.sin(yaw * 0.5)
        cp = math.cos(pitch * 0.5)
        sp = math.sin(pitch * 0.5)
        cr = math.cos(roll * 0.5)
        sr = math.sin(roll * 0.5)
        w = cr * cp * cy + sr * sp * sy
        x = sr * cp * cy - cr * sp * sy
        y = cr * sp * cy + sr * cp * sy
        z = cr * cp * sy - sr * sp * cy
        return np.array([w, x, y, z])

    @staticmethod
    def _quat_multiply(q1, q2):
        w1, x1, y1, z1 = q1
        w2, x2, y2, z2 = q2
        return np.array([
            w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
            w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2
        ])

    @staticmethod
    def _quat_normalize(q):
        norm = np.linalg.norm(q)
        if norm < 1e-10:
            return np.array([1.0, 0.0, 0.0, 0.0])
        return q / norm

    def _quat_to_euler_zyx_deg(self, quat):
        w, x, y, z = quat
        sin_pitch = 2.0 * (w * y - z * x)
        sin_pitch = max(-1.0, min(1.0, sin_pitch))
        pitch = math.asin(sin_pitch)
        yaw = math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))
        roll = math.atan2(2.0 * (w * x + y * z), 1.0 - 2.0 * (x * x + y * y))
        return math.degrees(roll), math.degrees(pitch), math.degrees(yaw)

    def imu_callback(self, msg):
        module_id = msg.module_id
        device_id = msg.device_id
        arm_id = self._get_arm_id(device_id)
        if arm_id is None:
            rospy.logwarn(f"未识别的 device_id: {device_id}，忽略")
            return

        state = self._ensure_state(module_id, arm_id)

        now = rospy.Time.now().to_sec()
        if state['last_time'] is None:
            state['last_time'] = now
            return
        dt = now - state['last_time']
        state['last_time'] = now
        if dt <= 0:
            return

        # 数据预处理
        accel = np.array([msg.accel_x, msg.accel_y, msg.accel_z])
        if ACCEL_UNIT_IS_G:
            accel *= GRAVITY
        gyro = np.radians([msg.gyro_x, msg.gyro_y, msg.gyro_z])

        # Mahony 互补滤波
        gyro_corrected = gyro.copy()
        acc_norm = np.linalg.norm(accel)
        if abs(acc_norm - GRAVITY) < ACC_TRUST_THRESH and acc_norm > 1e-6:
            acc_unit = accel / acc_norm
            w, x, y, z = state['quat']
            R = np.array([
                [1 - 2*y*y - 2*z*z,   2*x*y - 2*w*z,       2*x*z + 2*w*y],
                [2*x*y + 2*w*z,       1 - 2*x*x - 2*z*z,   2*y*z - 2*w*x],
                [2*x*z - 2*w*y,       2*y*z + 2*w*x,       1 - 2*x*x - 2*y*y]
            ])
            gravity_est = R[2, :]   # 世界系 Z 轴在机体系的投影
            error = np.cross(acc_unit, gravity_est)
            state['eInt'] += error * KI * dt
            correction = KP * error + state['eInt']
            gyro_corrected = gyro + correction

        # 四元数更新（右乘）
        omega_norm = np.linalg.norm(gyro_corrected)
        if omega_norm > 1e-6:
            axis = gyro_corrected / omega_norm
            angle = omega_norm * dt
            dq = np.array([math.cos(angle/2),
                           axis[0] * math.sin(angle/2),
                           axis[1] * math.sin(angle/2),
                           axis[2] * math.sin(angle/2)])
            state['quat'] = self._quat_multiply(state['quat'], dq)
            state['quat'] = self._quat_normalize(state['quat'])

        # 提取欧拉角并符号适配
        _, pitch_deg, yaw_deg = self._quat_to_euler_zyx_deg(state['quat'])
        swing = pitch_deg                     # 前倾为正
        rotation = -yaw_deg                   # 顺时针为正

        # ===== 正运动学坐标计算 =====
        swing_rad = math.radians(swing)
        rot_rad = math.radians(rotation)

        # 末端相对底座的位置
        dx_rel = TELESCOPIC_LENGTH * math.sin(swing_rad) * math.cos(rot_rad)
        dy_rel = TELESCOPIC_LENGTH * math.sin(swing_rad) * math.sin(rot_rad)
        dz_rel = SWING_CENTER_HEIGHT + TELESCOPIC_LENGTH * math.cos(swing_rad)

        # 世界坐标
        x = BASE_X + dx_rel
        y = BASE_Y + dy_rel
        z = BASE_Z + dz_rel

        # 发布消息
        angle_msg = tuo_luo_yi()
        angle_msg.header = Header(stamp=rospy.Time.now(), frame_id="world")
        angle_msg.module_id = module_id
        angle_msg.device_id = device_id
        angle_msg.swing_angle = swing
        angle_msg.rotation_angle = rotation
        angle_msg.x = x
        angle_msg.y = y
        angle_msg.z = z
        self.angle_pub.publish(angle_msg)

if __name__ == '__main__':
    try:
        node = ImuAnglePublisher()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass