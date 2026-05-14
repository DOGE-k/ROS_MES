#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
节点B：逆运动学解算与控制指令发布（增量值）
订阅：/arm_alpha_beta, 硬件反馈
发布：三个电机的增量指令
数据库：ros_database.db → calculation 表
协调信息：
  - coord   : {"32": [x,y,z]}       (仅最优托举点坐标)
  - position: {"33": rot_delta, "34": sw_delta, "35": tel_delta}
  - device_ID: NULL,  Unit_id: 32/64/96
"""

import rospy
import json
import numpy as np
import math
import time
import sqlite3
import random
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from std_msgs.msg import Header, String
from robot_control_backend.msg import RotationCmd, SwingCmd, TelescopicCmd

# =============== 配置 ===============
class Config:
    MAX_SWING_ANGLE = 20.0
    ARM_MIN_EXTEND = 1.0            # cm
    ARM_MAX_EXTEND = 60.0           # cm
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

# =============== ROS节点B ===============
class KinematicsNode:
    def __init__(self):
        rospy.init_node("arm_kinematics")
        self.executor = ThreadPoolExecutor(max_workers=Config.MAX_WORKERS)

        # 订阅目标
        rospy.Subscriber("/arm_alpha_beta", String, self.alpha_beta_callback)

        # 订阅硬件反馈
        self.current_state = {}
        rospy.Subscriber("/hardware/rotation_feedback", RotationCmd, self.rotation_feedback_cb)
        rospy.Subscriber("/hardware/swing_feedback", SwingCmd, self.swing_feedback_cb)
        rospy.Subscriber("/hardware/telescope_feedback", TelescopicCmd, self.telescopic_feedback_cb)

        # 发布指令
        self.pub_rotation = rospy.Publisher('/control/kinematics_rotation_cmd', RotationCmd, queue_size=10)
        self.pub_swing = rospy.Publisher('/control/kinematics_swing_cmd', SwingCmd, queue_size=10)
        self.pub_telescopic = rospy.Publisher('/control/kinematics_telescopic_cmd', TelescopicCmd, queue_size=10)

        # 数据库
        db_path = rospy.get_param("~db_path", "ros_database.db")
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._create_table()
        rospy.loginfo("✅ 节点B 数据库已连接，路径: %s", db_path)

    def _create_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS calculation (
                Createtime DATETIME NOT NULL PRIMARY KEY,
                creator_id INTEGER,
                Work_ID    INTEGER,
                device_ID  INTEGER,
                isread     INTEGER,
                coord      TEXT,
                position   TEXT,
                del_flag   INTEGER DEFAULT 0,
                Notes      TEXT,
                model_id   INTEGER,
                Unit_id    INTEGER
            )
        """)
        self.conn.commit()

    # ----- 反馈回调 -----
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
            self.current_state[arm_id] = {"rotation": 0.0, "swing": 0.0, "telescopic": 0.0}

    # 臂编号 → 单元号
    @staticmethod
    def arm_to_unit(arm_id):
        return {1: 32, 2: 64, 3: 96}.get(arm_id, 0)

    # ----- 主回调 -----
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
                    target_j1 = arm_res["j1_rotate_deg"]
                    target_j2 = arm_res["j2_swing_deg"]
                    target_j3_cm = arm_res["j3_extend_cm"]

                    self._ensure_arm(arm_id)
                    cur_rot = self.current_state[arm_id]["rotation"]
                    cur_sw = self.current_state[arm_id]["swing"]
                    cur_tel = self.current_state[arm_id]["telescopic"]

                    # 增量
                    delta_rot = cur_rot - target_j1
                    delta_sw = target_j2 - cur_sw
                    target_j3_mm = target_j3_cm * 10.0
                    delta_tel = target_j3_mm - cur_tel

                    delta_rot = max(-180, min(delta_rot, 180))
                    delta_sw = max(-Config.MAX_SWING_ANGLE, min(delta_sw, Config.MAX_SWING_ANGLE))
                    delta_tel = max(-100, min(delta_tel, 100))

                    dev_rot = arm_id * 32 + 1
                    dev_sw  = arm_id * 32 + 2
                    dev_tel = arm_id * 32 + 3
                    now = rospy.Time.now()

                    # 发布
                    rot_msg = RotationCmd()
                    rot_msg.header = Header(stamp=now)
                    rot_msg.module_id = mid
                    rot_msg.device_id = dev_rot
                    rot_msg.position = [delta_rot]
                    self.pub_rotation.publish(rot_msg)

                    sw_msg = SwingCmd()
                    sw_msg.header = Header(stamp=now)
                    sw_msg.module_id = mid
                    sw_msg.device_id = dev_sw
                    sw_msg.position = [delta_sw]
                    self.pub_swing.publish(sw_msg)

                    tel_msg = TelescopicCmd()
                    tel_msg.header = Header(stamp=now)
                    tel_msg.module_id = mid
                    tel_msg.device_id = dev_tel
                    tel_msg.position = [delta_tel]
                    self.pub_telescopic.publish(tel_msg)

                    # 写入数据库
                    self._save_arm_record(mid, arm_id, arm_res["alpha"], delta_rot, delta_sw, delta_tel)

                    rospy.loginfo(
                        f"📤 模块{mid} 臂{arm_id} | "
                        f"旋转增量:{delta_rot:+.2f}° | "
                        f"摆动增量:{delta_sw:+.2f}° | "
                        f"伸缩增量:{delta_tel:+.1f}mm"
                    )

            duration = round((time.time() - start_time) * 1000, 2)
            rospy.loginfo(f"节点B 处理 {len(all_module_results)} 个模块 | 耗时 {duration}ms")

        except Exception as e:
            rospy.logerr(f"节点B处理异常: {str(e)}", exc_info=True)

    def _save_arm_record(self, module_id, arm_id, alpha, delta_rot, delta_sw, delta_tel):
        """存储一条臂记录"""
        unit = self.arm_to_unit(arm_id)

        # coord: {"32": [x,y,z]}
        coord_dict = {
            str(unit): alpha
        }

        # position: {"33": delta_rot, "34": delta_sw, "35": delta_tel}
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
                (Createtime, creator_id, Work_ID, device_ID, isread, coord, position, del_flag, Notes, model_id, Unit_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                createtime,
                1,                # creator_id
                1,                # Work_ID
                None,             # device_ID 留空
                2,                # isread
                json.dumps(coord_dict),
                json.dumps(position_dict),
                0,                # del_flag
                None,             # Notes
                module_id,        # model_id
                unit              # Unit_id
            ))
            self.conn.commit()
        except Exception as e:
            rospy.logerr(f"数据库写入失败: {e}")

    # ----- 解算模块 -----
    def process_module(self, mod):
        try:
            mid = mod["module_id"]
            arm_items = mod["alpha_beta"]
            arm_results = []
            for item in arm_items:
                base = np.array(item["base"])
                alpha = np.array(item["alpha"])
                j1, j2, j3 = solve_3dof(base, alpha)
                if abs(j2) == Config.MAX_SWING_ANGLE:
                    rospy.logwarn(f"机械臂 {item.get('arm_id','?')} 摆动角极限 {j2}°")
                arm_results.append({
                    "arm_id": item["arm_id"],
                    "alpha": np.round(alpha, 2).tolist(),   # 只保留坐标
                    "beta": item["beta"],
                    "j1_rotate_deg": j1,
                    "j2_swing_deg": j2,
                    "j3_extend_cm": j3
                })
            return {"module_id": mid, "arm_result": arm_results}
        except Exception as e:
            rospy.logerr(f"模块解算异常: {str(e)}", exc_info=True)
            return None

    def shutdown_hook(self):
        self.conn.close()

if __name__ == "__main__":
    try:
        node = KinematicsNode()
        rospy.on_shutdown(node.shutdown_hook)
        rospy.spin()
    except rospy.ROSInterruptException:
        pass