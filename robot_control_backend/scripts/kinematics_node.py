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

时序控制：每个机械臂每8秒只能接收一条轴控制指令
"""

import rospy
import json
import numpy as np
import math
import time
import os
from threading import Lock
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from std_msgs.msg import Header, String
from robot_control_backend.msg import RotationCmd, SwingCmd, TelescopicCmd

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
    
    # 时序控制参数（从环境变量读取）
    @staticmethod
    def get_cycle_interval():
        return float(os.environ.get('CYCLE_INTERVAL', '8.0'))

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
        
        # 机械臂状态管理（时序控制）
        self.arm_states = {}  # arm_id -> {"last_time": 0, "pending_cmds": deque}
        self.lock = Lock()

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

        rospy.loginfo(f"节点B（增量模式）启动 | 周期间隔: {Config.get_cycle_interval()}s")

    # ----- 反馈回调，更新当前值 -----
    def rotation_feedback_cb(self, msg):
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
        if arm_id not in self.arm_states:
            self.arm_states[arm_id] = {
                "last_time": 0,
                "pending_cmds": deque()
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

            # 将指令加入队列
            for mod_res in all_module_results:
                mid = mod_res["module_id"]
                for arm_res in mod_res["arm_result"]:
                    arm_id = arm_res["arm_id"]
                    
                    # 创建指令包
                    cmd = {
                        "module_id": mid,
                        "arm_id": arm_id,
                        "target_j1": arm_res["j1_rotate_deg"],
                        "target_j2": arm_res["j2_swing_deg"],
                        "target_j3_cm": arm_res["j3_extend_cm"]
                    }
                    
                    with self.lock:
                        self._ensure_arm(arm_id)
                        self.arm_states[arm_id]["pending_cmds"].append(cmd)
                
                rospy.loginfo(f"📥 模块{mid} 指令已加入队列")

            # 处理所有机械臂的指令队列
            for arm_id in self.arm_states.keys():
                self.process_arm_queue(arm_id)

            duration = round((time.time() - start_time) * 1000, 2)
            rospy.loginfo(f"节点B 处理 {len(all_module_results)} 个模块 | 耗时 {duration}ms")

        except Exception as e:
            rospy.logerr(f"节点B处理异常: {str(e)}", exc_info=True)

    def process_arm_queue(self, arm_id):
        """处理单个机械臂的指令队列（每8秒发送一条）"""
        with self.lock:
            state = self.arm_states.get(arm_id)
            if not state or not state["pending_cmds"]:
                return
            
            now = time.time()
            time_since_last = now - state["last_time"]
            
            if time_since_last >= Config.get_cycle_interval():
                # 可以发送新指令
                cmd = state["pending_cmds"].popleft()
                state["last_time"] = now
            else:
                rospy.loginfo(f"⏳ 臂{arm_id} 等待中，剩余 {Config.get_cycle_interval() - time_since_last:.1f}s")
                return
        
        # 发送指令
        self.publish_cmd(cmd)
        
        # 如果还有等待的指令，定时触发下一次发送
        with self.lock:
            if self.arm_states[arm_id]["pending_cmds"]:
                delay = Config.get_cycle_interval() - (time.time() - state["last_time"])
                rospy.Timer(rospy.Duration(max(0, delay)), 
                           lambda event, aid=arm_id: self.process_arm_queue(aid), 
                           oneshot=True)

    def publish_cmd(self, cmd):
        """发布单个指令包"""
        mid = cmd["module_id"]
        arm_id = cmd["arm_id"]
        target_j1 = cmd["target_j1"]
        target_j2 = cmd["target_j2"]
        target_j3_cm = cmd["target_j3_cm"]

        # 获取当前值
        self._ensure_arm(arm_id)
        cur_rot = self.current_state[arm_id]["rotation"]
        cur_sw = self.current_state[arm_id]["swing"]
        cur_tel = self.current_state[arm_id]["telescopic"]

        # 计算增量
        delta_rot = cur_rot - target_j1
        delta_sw = target_j2 - cur_sw
        target_j3_mm = target_j3_cm * 10.0
        delta_tel = target_j3_mm - cur_tel

        # 限定增量范围
        delta_rot = max(-180, min(delta_rot, 180))
        delta_sw = max(-Config.MAX_SWING_ANGLE, min(delta_sw, Config.MAX_SWING_ANGLE))
        delta_tel = max(-100, min(delta_tel, 100))

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
            f"旋转增量:{delta_rot:+.2f}° | 摆动增量:{delta_sw:+.2f}° | 伸缩增量:{delta_tel:+.1f}mm"
        )

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
        load_env_config()
        KinematicsNode()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass
