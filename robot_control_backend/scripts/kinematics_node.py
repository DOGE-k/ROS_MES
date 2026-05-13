#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
节点B：角度解算与控制指令发布（发布增量值）
订阅话题：/arm_alpha_beta
          /hardware/rotation_feedback
          /hardware/swing_feedback
          /hardware/telescope_feedback
发布话题：/control/kinematics_rotation_cmd   (RotationCmd, 增量角度，度)
          /control/kinematics_swing_cmd      (SwingCmd,    增量角度，度)
          /control/kinematics_telescopic_cmd (TelescopicCmd,增量长度，mm)
"""

import rospy
import json
import numpy as np
import math
import time
from concurrent.futures import ThreadPoolExecutor
from std_msgs.msg import Header, String
from robot_control_backend.msg import RotationCmd, SwingCmd, TelescopicCmd

# =============== 配置 ===============
class Config:
    # 运动学限制
    MAX_SWING_ANGLE = 20.0          # 摆动角最大度数
    ARM_MIN_EXTEND = 1.0            # cm
    ARM_MAX_EXTEND = 60.0           # cm

    # 伸缩轴参数
    MIN_LENGTH_MM = 50.0
    MAX_LENGTH_MM = 500.0

    MAX_WORKERS = 4

# =============== 运动学解算 ===============
def solve_3dof(arm_base, target_p):
    dx, dy, dz = target_p - arm_base
    dxy = np.hypot(dx, dy)
    j1 = np.degrees(np.arctan2(dy, dx)) if dxy > 1e-3 else 0.0
    ideal_j2 = np.pi/2 if abs(dz) < 1e-6 else np.arctan2(dxy, dz)
    limited_j2 = np.clip(ideal_j2, -np.radians(Config.MAX_SWING_ANGLE), np.radians(Config.MAX_SWING_ANGLE))
    if abs(np.degrees(ideal_j2)) > Config.MAX_SWING_ANGLE:
        rospy.logwarn(f"摆动角超限! 理想值: {np.degrees(ideal_j2):.2f}°, 已限制至 {Config.MAX_SWING_ANGLE}°")
    j3 = dxy if abs(dz) < 1e-6 else dz / np.cos(limited_j2)
    j3 = np.clip(j3, Config.ARM_MIN_EXTEND, Config.ARM_MAX_EXTEND)
    return round(j1, 2), round(np.degrees(limited_j2), 2), round(j3, 2)

# =============== ROS节点B（增量发布） ===============
class KinematicsNode:
    def __init__(self):
        rospy.init_node("arm_kinematics")
        self.executor = ThreadPoolExecutor(max_workers=Config.MAX_WORKERS)

        # 订阅目标信息
        rospy.Subscriber("/arm_alpha_beta", String, self.alpha_beta_callback)

        # 订阅硬件反馈，以获取各轴的当前实际值
        self.current_state = {}  # arm_id -> {"rotation": deg, "swing": deg, "telescopic": mm}
        rospy.Subscriber("/hardware/rotation_feedback", RotationCmd, self.rotation_feedback_cb)
        rospy.Subscriber("/hardware/swing_feedback", SwingCmd, self.swing_feedback_cb)
        rospy.Subscriber("/hardware/telescope_feedback", TelescopicCmd, self.telescopic_feedback_cb)

        # 三个指令话题
        self.pub_rotation = rospy.Publisher(
            '/control/kinematics_rotation_cmd', RotationCmd, queue_size=10)
        self.pub_swing = rospy.Publisher(
            '/control/kinematics_swing_cmd', SwingCmd, queue_size=10)
        self.pub_telescopic = rospy.Publisher(
            '/control/kinematics_telescopic_cmd', TelescopicCmd, queue_size=10)

        rospy.loginfo("节点B（增量模式）启动，订阅硬件反馈中...")

    # ----- 反馈回调，更新当前值 -----
    def rotation_feedback_cb(self, msg):
        # 根据 device_id 反算 arm_id（规则：arm_id*32+1）
        arm_id = (msg.device_id - 1) // 32
        self._ensure_arm(arm_id)
        self.current_state[arm_id]["rotation"] = msg.position[0]

    def swing_feedback_cb(self, msg):
        arm_id = (msg.device_id - 2) // 32
        self._ensure_arm(arm_id)
        self.current_state[arm_id]["swing"] = msg.position[0]

    def telescopic_feedback_cb(self, msg):
        arm_id = (msg.device_id - 3) // 32
        self._ensure_arm(arm_id)
        self.current_state[arm_id]["telescopic"] = msg.position[0]

    def _ensure_arm(self, arm_id):
        if arm_id not in self.current_state:
            self.current_state[arm_id] = {
                "rotation": 0.0,
                "swing": 0.0,
                "telescopic": 0.0
            }

    # ----- 主处理 -----
    def alpha_beta_callback(self, msg):
        try:
            start_time = time.time()
            modules = json.loads(msg.data)
            all_module_results = []
            futures = [self.executor.submit(self.process_module, mod) for mod in modules]
            for future in futures:
                res = future.result()
                if res:
                    all_module_results.append(res)

            # 发布增量指令
            for mod_res in all_module_results:
                mid = mod_res["module_id"]
                for arm_res in mod_res["arm_result"]:
                    arm_id = arm_res["arm_id"]
                    target_j1 = arm_res["j1_rotate_deg"]      # 绝对目标旋转角度
                    target_j2 = arm_res["j2_swing_deg"]       # 绝对目标摆动角度
                    target_j3_cm = arm_res["j3_extend_cm"]    # 绝对目标伸缩长度(cm)

                    # 获取当前值（若无反馈则默认0）
                    self._ensure_arm(arm_id)
                    cur_rot = self.current_state[arm_id]["rotation"]
                    cur_sw = self.current_state[arm_id]["swing"]
                    cur_tel = self.current_state[arm_id]["telescopic"]  # mm

                    # 计算增量
                    delta_rot = cur_rot - target_j1
                    delta_sw = target_j2 - cur_sw
                    target_j3_mm = target_j3_cm * 10.0
                    delta_tel = target_j3_mm - cur_tel

                    # 限定增量范围（可选，避免异常跳变）
                    delta_rot = max(-180, min(delta_rot, 180))
                    delta_sw = max(-Config.MAX_SWING_ANGLE, min(delta_sw, Config.MAX_SWING_ANGLE))
                    delta_tel = max(-100, min(delta_tel, 100))  # 一次伸缩最大100mm

                    # device_id
                    dev_rot = arm_id * 32 + 1
                    dev_sw  = arm_id * 32 + 2
                    dev_tel = arm_id * 32 + 3

                    now = rospy.Time.now()

                    # 旋转增量
                    rot_msg = RotationCmd()
                    rot_msg.header = Header(stamp=now)
                    rot_msg.module_id = mid
                    rot_msg.device_id = dev_rot
                    rot_msg.position = [delta_rot]
                    self.pub_rotation.publish(rot_msg)

                    # 摆动增量
                    sw_msg = SwingCmd()
                    sw_msg.header = Header(stamp=now)
                    sw_msg.module_id = mid
                    sw_msg.device_id = dev_sw
                    sw_msg.position = [delta_sw]
                    self.pub_swing.publish(sw_msg)

                    # 伸缩增量 (mm)
                    tel_msg = TelescopicCmd()
                    tel_msg.header = Header(stamp=now)
                    tel_msg.module_id = mid
                    tel_msg.device_id = dev_tel
                    tel_msg.position = [delta_tel]
                    self.pub_telescopic.publish(tel_msg)

                    rospy.loginfo(
                        f"📤 模块{mid} 臂{arm_id} | "
                        f"旋转增量:{delta_rot:+.2f}° (目标:{target_j1:.2f} 当前:{cur_rot:.2f}) | "
                        f"摆动增量:{delta_sw:+.2f}° (目标:{target_j2:.2f} 当前:{cur_sw:.2f}) | "
                        f"伸缩增量:{delta_tel:+.1f}mm (目标:{target_j3_mm:.1f} 当前:{cur_tel:.1f})"
                    )

            duration = round((time.time() - start_time) * 1000, 2)
            rospy.loginfo(f"节点B 处理 {len(all_module_results)} 个模块 | 耗时 {duration}ms")

        except Exception as e:
            rospy.logerr(f"节点B处理异常: {str(e)}", exc_info=True)

    def process_module(self, mod):
        try:
            mid = mod["module_id"]
            arm_items = mod["alpha_beta"]
            arm_results = []
            tasks = [self.executor.submit(self.process_single_arm, item) for item in arm_items]
            for task, item in zip(tasks, arm_items):
                res = task.result()
                res["arm_id"] = item["arm_id"]
                res["base_pos"] = item["base"]
                res["strategy"] = item.get("strategy", "unknown")
                dx = res["alpha"][0] - item["base"][0]
                dy = res["alpha"][1] - item["base"][1]
                dz = res["alpha"][2] - item["base"][2]
                res["distance"] = round(math.sqrt(dx**2 + dy**2 + dz**2), 2)
                arm_results.append(res)
            return {"module_id": mid, "arm_result": arm_results}
        except Exception as e:
            rospy.logerr(f"模块解算异常: {str(e)}", exc_info=True)
            return None

    def process_single_arm(self, item):
        base = np.array(item["base"])
        alpha = np.array(item["alpha"])
        j1, j2, j3 = solve_3dof(base, alpha)
        if abs(j2) == Config.MAX_SWING_ANGLE:
            rospy.logwarn(f"机械臂 {item.get('arm_id','?')} 摆动角极限 {j2}°")
        return {
            "alpha": alpha.tolist(),
            "beta": item["beta"],
            "j1_rotate_deg": j1,
            "j2_swing_deg": j2,
            "j3_extend_cm": j3
        }

if __name__ == "__main__":
    try:
        KinematicsNode()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass