#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
节点B（V2）：角度解算与控制指令发布（所有参数与话题强制从 .env 读取）

V2 关键变更：
  - 5 臂映射（V1.1 为 3 臂）
  - device_id 即 AXIS 寻址单元（1~15轴/21~25臂级），每臂 3 轴（J1旋转/J2摆动/J3伸缩）
  - 三轴限位全部由 rob_arm.env 控制：
      旋转 ROTATION_MIN_ANGLE / ROTATION_MAX_ANGLE
      摆动 SWING_MIN_ANGLE / MAX_SWING_ANGLE
      伸缩 TELESCOPIC_MIN_MM / TELESCOPIC_MAX_MM
"""

import rospy
import json
import numpy as np
import math
import time
import os
import sqlite3
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
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value
    rospy.loginfo("✅ 节点B 已从 rob_arm.env 加载配置")


# ===================== 配置参数（全部从环境变量强制读取） =====================
class Config:
    """所有参数通过 update_config_from_env 动态添加，无默认值"""
    pass


def update_config_from_env():
    """强制从环境变量读取运动学参数，缺少任何一项将引发 KeyError"""
    # 三轴绝对限位（与轴级节点共用同一组配置键）
    Config.ROTATION_MIN_ANGLE = float(os.environ['ROTATION_MIN_ANGLE'])
    Config.ROTATION_MAX_ANGLE = float(os.environ['ROTATION_MAX_ANGLE'])
    Config.SWING_MIN_ANGLE    = float(os.environ['SWING_MIN_ANGLE'])
    Config.MAX_SWING_ANGLE    = float(os.environ['MAX_SWING_ANGLE'])
    Config.TELESCOPIC_MIN_MM  = float(os.environ['TELESCOPIC_MIN_MM'])
    Config.TELESCOPIC_MAX_MM  = float(os.environ['TELESCOPIC_MAX_MM'])
    # 伸缩轴零点：伸缩读数为 0 时，臂端接触面距基座的高度（cm，现场实测 12.5）
    # 逆解得到的「基座→目标」距离必须减掉它，才是能下发的位移量，
    # 因为伸缩行程（±20mm）是相对这个零位量的，不是从基座量起。
    Config.ARM_TIP_HEIGHT_AT_ZERO = float(os.environ['ARM_TIP_HEIGHT_AT_ZERO'])
    # 伸缩轴为直线位移轴，反馈/指令单位均为 mm（CAN 字段 0.01mm，由 feedback_node 换算）
    # 单次伸缩增量告警阈值（mm），超过仅告警，不裁剪解算结果
    Config.TELESCOPIC_MAX_DELTA_MM = float(os.environ['TELESCOPIC_MAX_DELTA_MM'])
    Config.MAX_WORKERS      = int(os.environ['MAX_WORKERS'])
    Config.CYCLE_INTERVAL   = float(os.environ['CYCLE_INTERVAL'])       # 指令周期间隔


# ===================== 运动学解算 =====================
def solve_3dof(arm_base, target_p):
    """3自由度逆运动学解算，返回 (j1_deg, j2_deg, j3_ext_cm, reachable, reason)。

    图纸下发：解算结果必须按 rob_arm.env 的三轴软限位裁剪后再下发。
    轴节点（rotation/swing/telescopic）对超位指令是直接丢弃并回执 CmdAck，
    解算端不裁剪会导致图纸指令全部被判超位、命令下发不出去。
    微调不经过本节点，不受此裁剪影响。

    j3_ext_cm 是**相对臂端零位的伸出量**，不是基座到目标的绝对距离。
    伸缩轴只有 ±20mm 行程，且这个行程是对着「伸缩读数为 0 时的臂端位置」量的，
    必须减去 ARM_TIP_HEIGHT_AT_ZERO 才能当指令用。
    reachable=False 表示即使裁到限位也够不到目标（摆动超软限位，或伸出量超行程），
    调用方据此把三轴置 0 并上报，不再把「歪着伸过去但托空」当成功指令发出去。
    """
    dx, dy, dz = target_p - arm_base
    dxy = np.hypot(dx, dy)
    r = float(np.hypot(dxy, dz))

    # 旋转轴限位裁剪（°）
    j1 = np.degrees(np.arctan2(dy, dx)) if dxy > 1e-3 else 0.0
    j1_clipped = float(np.clip(j1, Config.ROTATION_MIN_ANGLE, Config.ROTATION_MAX_ANGLE))
    if not np.isclose(j1_clipped, j1):
        rospy.logwarn("旋转解算值 %.2f° 超出限位 [%.1f, %.1f]°，已裁剪为 %.2f°",
                      j1, Config.ROTATION_MIN_ANGLE, Config.ROTATION_MAX_ANGLE, j1_clipped)
    j1 = j1_clipped

    # 摆动轴限位裁剪（°）
    ideal_j2 = np.pi/2 if abs(dz) < 1e-6 else np.arctan2(dxy, dz)
    j2_deg = np.degrees(ideal_j2)
    j2_clipped = float(np.clip(j2_deg, Config.SWING_MIN_ANGLE, Config.MAX_SWING_ANGLE))
    swing_ok = bool(np.isclose(j2_clipped, j2_deg))
    if not swing_ok:
        rospy.logwarn("摆动解算值 %.2f° 超出限位 [%.1f, %.1f]°，已裁剪为 %.2f°",
                      j2_deg, Config.SWING_MIN_ANGLE, Config.MAX_SWING_ANGLE, j2_clipped)
    j2_deg = j2_clipped

    # 伸缩轴：先用裁剪后的摆动角反算需要的臂长（保高度），再减掉零位得到伸出量。
    # 摆动未被裁剪时 dz/cos(j2) 就等于三维距离 r，两种情形连续，不会跳变。
    cos_j2 = float(np.cos(np.radians(j2_deg)))
    reach_cm = r if abs(cos_j2) < 1e-6 else float(dz) / cos_j2

    # 轴节点限位单位是 mm，伸出量单位是 cm，需先换算
    j3_raw = reach_cm - Config.ARM_TIP_HEIGHT_AT_ZERO
    j3_min_cm = Config.TELESCOPIC_MIN_MM / 10.0
    j3_max_cm = Config.TELESCOPIC_MAX_MM / 10.0
    j3 = float(np.clip(j3_raw, j3_min_cm, j3_max_cm))
    ext_ok = bool(np.isclose(j3, j3_raw))
    if not ext_ok:
        rospy.logwarn("伸缩解算值 %.2fcm（基座→目标 %.2fcm − 零位 %.2fcm）"
                      "超出限位 [%.1f, %.1f]mm，已裁剪为 %.2fcm",
                      j3_raw, reach_cm, Config.ARM_TIP_HEIGHT_AT_ZERO,
                      Config.TELESCOPIC_MIN_MM, Config.TELESCOPIC_MAX_MM, j3)

    if not swing_ok:
        reason = (f"摆动 {np.degrees(ideal_j2):.2f}° 超出软限位 "
                  f"[{Config.SWING_MIN_ANGLE:.1f}, {Config.MAX_SWING_ANGLE:.1f}]°")
        reachable = False
    elif not ext_ok:
        reason = (f"伸缩需 {j3_raw * 10:.1f}mm 超出软限位 "
                  f"[{Config.TELESCOPIC_MIN_MM:.0f}, {Config.TELESCOPIC_MAX_MM:.0f}]mm")
        reachable = False
    else:
        reason = ""
        reachable = True

    return round(j1, 2), round(j2_deg, 2), round(j3, 3), reachable, reason


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
        db_path = os.environ['DB_PATH']   # 只读 rob_arm.env
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
        """V2：5 臂映射，单元号即臂号"""
        return {1: 1, 2: 2, 3: 3, 4: 4, 5: 5}.get(arm_id, 0)

    # ----- 硬件反馈回调（V2：device_id 即轴号，臂号=(轴号-1)//3+1）-----
    def rotation_feedback_cb(self, msg):
        arm_id = (int(msg.device_id) - 1) // 3 + 1
        self._ensure_arm(arm_id)
        self.current_state[arm_id]["rotation"] = msg.position[0]

    def swing_feedback_cb(self, msg):
        arm_id = (int(msg.device_id) - 1) // 3 + 1
        self._ensure_arm(arm_id)
        self.current_state[arm_id]["swing"] = msg.position[0]

    def telescopic_feedback_cb(self, msg):
        """伸缩轴为直线位移轴：反馈已是 mm（feedback_node 由 0.01mm 换算），直接存入 current_state"""
        arm_id = (int(msg.device_id) - 1) // 3 + 1
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
                active_arm_ids = set()
                for arm_res in mod_res["arm_result"]:
                    arm_id = arm_res["arm_id"]
                    active_arm_ids.add(arm_id)
                    cmd = {
                        "module_id": mid,
                        "arm_id": arm_id,
                        "target_j1": arm_res["j1_rotate_deg"],
                        "target_j2": arm_res["j2_swing_deg"],
                        "target_j3_cm": arm_res["j3_extend_cm"],
                        "reachable": arm_res.get("reachable", True),
                        "reason": arm_res.get("reason", ""),
                    }
                    with self.lock:
                        self._ensure_arm(arm_id)
                        self.arm_states[arm_id]["pending_cmds"].append(cmd)
                rospy.loginfo(f"📥 模块{mid} 指令已加入队列")

                # V2 空指令占位：本模块未分配到的臂无需动作，补齐 position=0 的空指令，
                # 保证控制节点能收齐 5 臂×3 轴（否则其指令缓冲会永久等待）
                for arm_id in range(1, 6):
                    if arm_id in active_arm_ids:
                        continue
                    zero_cmd = {"module_id": mid, "arm_id": arm_id, "empty": True}
                    with self.lock:
                        self._ensure_arm(arm_id)
                        self.arm_states[arm_id]["pending_cmds"].append(zero_cmd)
                    rospy.loginfo(f"📥 模块{mid} Arm{arm_id} 无需动作，已生成 position=0 空指令占位")

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
        # 空指令无目标值，用 0 占位（后续分支不会使用）
        target_j1 = cmd.get("target_j1", 0.0)
        target_j2 = cmd.get("target_j2", 0.0)
        target_j3_cm = cmd.get("target_j3_cm", 0.0)

        self._ensure_arm(arm_id)

        # V2 空指令：该臂本模块无需动作，三轴增量精确为 0（不读取反馈基准，避免缺反馈时取不到状态）
        if cmd.get("empty"):
            delta_rot = delta_sw = delta_tel = 0.0
        elif not cmd.get("reachable", True):
            # 目标不在可达域内：裁到限位也够不到，发出去只会「歪着伸过去但托空」，
            # 且不会报错，比不动更隐蔽。这里三轴置 0 并上报原因。
            delta_rot = delta_sw = delta_tel = 0.0
            rospy.logerr("⛔ 模块%s 臂%d 目标不可达，三轴保持不动 | %s",
                         mid, arm_id, cmd.get("reason", "未知"))
        else:
            cur_rot = self.current_state[arm_id]["rotation"]
            cur_sw  = self.current_state[arm_id]["swing"]
            cur_tel = self.current_state[arm_id]["telescopic"]

            # 计算增量（目标 - 当前 = 应移动的增量）
            delta_rot = target_j1 - cur_rot
            delta_sw  = target_j2 - cur_sw
            target_j3_mm = target_j3_cm * 10.0
            delta_tel = target_j3_mm - cur_tel

            # 解算目标已在 solve_3dof 按三轴软限位裁剪，这里只按裁剪后的目标求增量，
            # 不再额外裁剪增量，保证轴节点收到的是限位内的位置。
            if abs(delta_tel) > Config.TELESCOPIC_MAX_DELTA_MM:
                rospy.logwarn("Arm%d 伸缩增量 %.2fmm 超过建议单次值 %.1fmm，按已裁剪目标下发",
                              arm_id, delta_tel, Config.TELESCOPIC_MAX_DELTA_MM)

        # V2 device_id 规则（device_id 即 AXIS 寻址单元，不再乘 100）：
        #   每臂 3 轴（J1旋转/J2摆动/J3伸缩），轴号=1~15
        #   Arm1: axis 1/2/3 → device_id 1/2/3
        #   Arm2: axis 4/5/6 → device_id 4/5/6  ...
        #   Arm5: axis13/14/15 → device_id 13/14/15
        axis_rot = (arm_id - 1) * 3 + 1
        axis_sw  = (arm_id - 1) * 3 + 2
        axis_tel = (arm_id - 1) * 3 + 3
        dev_rot = axis_rot
        dev_sw  = axis_sw
        dev_tel = axis_tel

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

        # 写入数据库（device_ID 固定为0）；不可达时把原因写进 Notes 供后端/前端展示
        alpha = [target_j1, target_j2, target_j3_cm]
        notes = "" if cmd.get("reachable", True) else f"不可达：{cmd.get('reason', '')}"
        self._save_arm_record(mid, arm_id, alpha, delta_rot, delta_sw, delta_tel, notes)

        if cmd.get("reachable", True):
            rospy.loginfo(f"📤 模块{mid} 臂{arm_id} | 旋转增量:{delta_rot:+.2f}° 摆动增量:{delta_sw:+.2f}° 伸缩增量:{delta_tel:+.1f}mm")
        else:
            rospy.logwarn(f"📤 模块{mid} 臂{arm_id} | 不可达，三轴 0 增量（%s）",
                          cmd.get("reason", "未知"))

    def _save_arm_record(self, module_id, arm_id, alpha, delta_rot, delta_sw, delta_tel, notes=""):
        """存储一条臂记录到数据库，device_ID 固定为 0，真正的电机ID在 position JSON 中"""
        unit = self.arm_to_unit(arm_id)

        coord_dict = {str(unit): alpha}
        axis_rot = (arm_id - 1) * 3 + 1
        axis_sw  = (arm_id - 1) * 3 + 2
        axis_tel = (arm_id - 1) * 3 + 3
        position_dict = {
            str(axis_rot): round(delta_rot, 2),
            str(axis_sw): round(delta_sw, 2),
            str(axis_tel): round(delta_tel, 1)
        }

        createtime = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")

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
                notes
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
        j1, j2, j3, reachable, reason = solve_3dof(base, alpha)
        return {
            "alpha": alpha.tolist(),
            "beta": item["beta"],
            "j1_rotate_deg": j1,
            "j2_swing_deg": j2,
            "j3_extend_cm": j3,
            "reachable": reachable,
            "reason": reason,
        }


if __name__ == "__main__":
    load_env_config()
    update_config_from_env()
    node = KinematicsNode()
    rospy.on_shutdown(node.shutdown_hook)
    rospy.spin()