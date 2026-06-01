#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
节点B：角度解算与控制指令发布（所有参数与话题强制从 .env 读取，无默认值）
"""

import rospy
import json
import numpy as np
import math
import time
import os
import sqlite3
import random
from datetime import datetime
from threading import Lock
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from std_msgs.msg import Header, String
from robot_control_backend.msg import RotationCmd, SwingCmd, TelescopicCmd


# ===================== 配置加载 =====================
def load_env_config():
    """从 .env 文件强制加载所有配置到环境变量（文件必须存在）"""
    env_path = os.path.join(os.path.dirname(__file__), '../rob_arm.env')
    if not os.path.exists(env_path):
        raise FileNotFoundError(f"配置文件 {env_path} 未找到")
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                key, value = line.split('=', 1)
                os.environ[key] = value
    rospy.loginfo("✅ 节点B 已从 rob_arm.env 加载配置")


# ===================== 配置参数（全部从环境变量强制读取） =====================
class Config:
    """所有参数通过 update_config_from_env 动态添加，无默认值"""
    pass


def update_config_from_env():
    """强制从环境变量读取运动学参数，缺少任何一项将引发 KeyError"""
    Config.MAX_SWING_ANGLE = float(os.environ['MAX_SWING_ANGLE'])
    Config.ARM_MIN_EXTEND   = float(os.environ['ARM_MIN_EXTEND'])       # cm
    Config.ARM_MAX_EXTEND   = float(os.environ['ARM_MAX_EXTEND'])       # cm
    Config.MIN_LENGTH_MM    = float(os.environ['MIN_LENGTH_MM'])
    Config.MAX_LENGTH_MM    = float(os.environ['MAX_LENGTH_MM'])
    Config.MAX_WORKERS      = int(os.environ['MAX_WORKERS'])
    Config.CYCLE_INTERVAL   = float(os.environ['CYCLE_INTERVAL'])       # 指令周期间隔


# ===================== 运动学解算 =====================
def solve_3dof(arm_base, target_p):
    """3自由度逆运动学解算，返回关节目标角度/长度"""
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


# ===================== ROS 节点B =====================
class KinematicsNode:
    """逆运动学节点：接收最优托举点，发布增量指令，并记录数据库"""

    def __init__(self):
        # ---------- 从环境变量强制读取话题名称 ----------
        topic_alpha_beta = os.environ['ROS_TOPIC_ARM_ALPHA_BETA']
        topic_rot_fb = os.environ['ROS_TOPIC_ROTATION_FEEDBACK']
        topic_sw_fb  = os.environ['ROS_TOPIC_SWING_FEEDBACK']
        topic_tel_fb = os.environ['ROS_TOPIC_TELESCOPE_FEEDBACK']
        # 输出话题（即控制节点的输入话题）
        topic_rot_cmd = os.environ['ROS_TOPIC_KINEMATICS_ROTATION_CMD_INPUT']
        topic_sw_cmd  = os.environ['ROS_TOPIC_KINEMATICS_SWING_CMD_INPUT']
        topic_tel_cmd = os.environ['ROS_TOPIC_KINEMATICS_TELESCOPIC_CMD_INPUT']

        rospy.init_node("arm_kinematics")
        self.executor = ThreadPoolExecutor(max_workers=Config.MAX_WORKERS)

        self.arm_states = {}      # 指令队列状态
        self.lock = Lock()

        # ---------- 订阅目标信息 ----------
        rospy.Subscriber(topic_alpha_beta, String, self.alpha_beta_callback)

        # ---------- 订阅硬件反馈 ----------
        self.current_state = {}   # arm_id -> {rotation, swing, telescopic}
        rospy.Subscriber(topic_rot_fb, RotationCmd,   self.rotation_feedback_cb)
        rospy.Subscriber(topic_sw_fb,  SwingCmd,      self.swing_feedback_cb)
        rospy.Subscriber(topic_tel_fb, TelescopicCmd, self.telescopic_feedback_cb)

        # ---------- 发布指令 ----------
        self.pub_rotation   = rospy.Publisher(topic_rot_cmd, RotationCmd,   queue_size=10)
        self.pub_swing      = rospy.Publisher(topic_sw_cmd,  SwingCmd,      queue_size=10)
        self.pub_telescopic = rospy.Publisher(topic_tel_cmd, TelescopicCmd, queue_size=10)

        # ---------- 数据库初始化 ----------
        db_path = os.environ.get('DB_PATH', 'ros_database.db')   # 数据库路径可保留默认值（非强制性配置）
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._create_table()
        rospy.loginfo("✅ 节点B 数据库已连接，路径: %s", db_path)

        rospy.loginfo(f"节点B（增量模式）启动 | 周期间隔: {Config.CYCLE_INTERVAL}s")

    def _create_table(self):
        """创建 calculation 表（如果不存在）"""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS calculation (
                Createtime DATETIME NOT NULL PRIMARY KEY,
                creater_id INTEGER NOT NULL,
                Work_ID    INTEGER NOT NULL,
                Module_ID  INTEGER NOT NULL,
                Unit_ID    INTEGER NOT NULL,
                device_ID  INTEGER NOT NULL,
                isread     INTEGER NOT NULL,
                coord      TEXT NOT NULL,
                position   TEXT NOT NULL,
                del_flag   BOOL NOT NULL DEFAULT false,
                Notes      TEXT NOT NULL
            )
        """)
        self.conn.commit()

    @staticmethod
    def arm_to_unit(arm_id):
        """臂编号 -> 单元号映射"""
        return {1: 32, 2: 64, 3: 96}.get(arm_id, 0)

    # ----- 硬件反馈回调（新 device_id 规则） -----
    def rotation_feedback_cb(self, msg):
        arm_id = (msg.device_id - 1) // 32        # 33→1, 65→2, 97→3
        self._ensure_arm(arm_id)
        self.current_state[arm_id]["rotation"] = msg.position[0]

    def swing_feedback_cb(self, msg):
        arm_id = (msg.device_id - 2) // 32        # 34→1, 66→2, 98→3
        self._ensure_arm(arm_id)
        self.current_state[arm_id]["swing"] = msg.position[0]

    def telescopic_feedback_cb(self, msg):
        arm_id = (msg.device_id - 3) // 32        # 35→1, 67→2, 99→3
        self._ensure_arm(arm_id)
        self.current_state[arm_id]["telescopic"] = msg.position[0]

    def _ensure_arm(self, arm_id):
        if arm_id not in self.current_state:
            self.current_state[arm_id] = {"rotation":0.0, "swing":0.0, "telescopic":0.0}
        if arm_id not in self.arm_states:
            self.arm_states[arm_id] = {"last_time":0, "pending_cmds":deque()}

    # ----- 主回调：接收最优托举点，解算后入队 -----
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

            for mod_res in all_module_results:
                mid = mod_res["module_id"]
                for arm_res in mod_res["arm_result"]:
                    arm_id = arm_res["arm_id"]
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

            for arm_id in self.arm_states.keys():
                self.process_arm_queue(arm_id)

            duration = round((time.time() - start_time) * 1000, 2)
            rospy.loginfo(f"节点B 处理 {len(all_module_results)} 个模块 | 耗时 {duration}ms")
        except Exception as e:
            rospy.logerr(f"节点B处理异常: {str(e)}", exc_info=True)

    def process_arm_queue(self, arm_id):
        """按周期从队列取出指令并发布"""
        with self.lock:
            state = self.arm_states.get(arm_id)
            if not state or not state["pending_cmds"]:
                return
            now = time.time()
            time_since_last = now - state["last_time"]
            if time_since_last >= Config.CYCLE_INTERVAL:
                cmd = state["pending_cmds"].popleft()
                state["last_time"] = now
            else:
                rospy.loginfo(f"⏳ 臂{arm_id} 等待中，剩余 {Config.CYCLE_INTERVAL - time_since_last:.1f}s")
                return
        self.publish_cmd(cmd)
        with self.lock:
            if self.arm_states[arm_id]["pending_cmds"]:
                delay = Config.CYCLE_INTERVAL - (time.time() - state["last_time"])
                rospy.Timer(rospy.Duration(max(0, delay)),
                           lambda event, aid=arm_id: self.process_arm_queue(aid),
                           oneshot=True)

    def publish_cmd(self, cmd):
        """发布一条指令（三个轴）并写入数据库"""
        mid = cmd["module_id"]
        arm_id = cmd["arm_id"]
        target_j1 = cmd["target_j1"]
        target_j2 = cmd["target_j2"]
        target_j3_cm = cmd["target_j3_cm"]

        self._ensure_arm(arm_id)
        cur_rot = self.current_state[arm_id]["rotation"]
        cur_sw  = self.current_state[arm_id]["swing"]
        cur_tel = self.current_state[arm_id]["telescopic"]

        # 计算增量
        delta_rot = cur_rot - target_j1
        delta_sw  = target_j2 - cur_sw
        target_j3_mm = target_j3_cm * 10.0
        delta_tel = target_j3_mm - cur_tel

        # 增量限幅
        delta_rot = max(-180, min(delta_rot, 180))
        delta_sw  = max(-Config.MAX_SWING_ANGLE, min(delta_sw, Config.MAX_SWING_ANGLE))
        delta_tel = max(-100, min(delta_tel, 100))

        # 新 device_id 规则
        dev_rot = arm_id * 32 + 1
        dev_sw  = arm_id * 32 + 2
        dev_tel = arm_id * 32 + 3

        now = rospy.Time.now()
        # 旋转增量
        rot_msg = RotationCmd()
        rot_msg.header = Header(stamp=now); rot_msg.module_id = mid; rot_msg.device_id = dev_rot; rot_msg.position = [delta_rot]
        self.pub_rotation.publish(rot_msg)

        # 摆动增量
        sw_msg = SwingCmd()
        sw_msg.header = Header(stamp=now); sw_msg.module_id = mid; sw_msg.device_id = dev_sw; sw_msg.position = [delta_sw]
        self.pub_swing.publish(sw_msg)

        # 伸缩增量
        tel_msg = TelescopicCmd()
        tel_msg.header = Header(stamp=now); tel_msg.module_id = mid; tel_msg.device_id = dev_tel; tel_msg.position = [delta_tel]
        self.pub_telescopic.publish(tel_msg)

        # 写入数据库（device_ID 固定为0）
        alpha = [target_j1, target_j2, target_j3_cm]
        self._save_arm_record(mid, arm_id, alpha, delta_rot, delta_sw, delta_tel)

        rospy.loginfo(f"📤 模块{mid} 臂{arm_id} | 旋转增量:{delta_rot:+.2f}° 摆动增量:{delta_sw:+.2f}° 伸缩增量:{delta_tel:+.1f}mm")

    def _save_arm_record(self, module_id, arm_id, alpha, delta_rot, delta_sw, delta_tel):
        """存储一条臂记录到数据库，device_ID 固定为 0，真正的电机ID在 position JSON 中"""
        unit = self.arm_to_unit(arm_id)

        coord_dict = {str(unit): alpha}
        position_dict = {
            str(arm_id * 32 + 1): round(delta_rot, 2),
            str(arm_id * 32 + 2): round(delta_sw, 2),
            str(arm_id * 32 + 3): round(delta_tel, 1)
        }

        now = datetime.now()
        createtime = (now.strftime("%Y-%m-%d %H:%M:%S.") +
                      f"{now.microsecond // 1000:03d}-{random.randint(0, 9999):04d}")

        try:
            self.conn.execute("""
                INSERT INTO calculation
                (Createtime, creater_id, Work_ID, Module_ID, Unit_ID, device_ID, isread, coord, position, del_flag, Notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                createtime,
                1,
                1,
                module_id,
                unit,
                0,                # device_ID 固定为 0
                2,
                json.dumps(coord_dict),
                json.dumps(position_dict),
                False,
                ""
            ))
            self.conn.commit()
        except Exception as e:
            rospy.logerr(f"数据库写入失败: {e}")

    def shutdown_hook(self):
        self.conn.close()
        rospy.loginfo("✅ 节点B 数据库连接已关闭")

    def process_module(self, mod):
        """处理单个模块，返回臂的解算结果"""
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
        """单个机械臂的运动学解算"""
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
    load_env_config()
    update_config_from_env()
    node = KinematicsNode()
    rospy.on_shutdown(node.shutdown_hook)
    rospy.spin()