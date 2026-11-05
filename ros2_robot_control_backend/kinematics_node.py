
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
节点B kinematics_node ROS2版本：角度解算与控制指令发布
严格按照图片任务迁移；solve_3dof数学逻辑完全保留；增量限位：rot±180°, swing±15°, telescopic±3mm
并发模型：MultiThreadedExecutor + ReentrantCallbackGroup；独立ThreadPoolExecutor(4)做逆解计算
"""
import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.time import Time
from concurrent.futures import ThreadPoolExecutor
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

from std_msgs.msg import String
from robot_control_backend.msg import RotationCmd, SwingCmd, TelescopicCmd


def load_env_config():
    """从 .env 文件强制加载所有配置到环境变量（文件必须存在）"""
    env_path = os.path.join(os.path.dirname(__file__), '../rob_arm.env')
    if not os.path.exists(env_path):
        raise FileNotFoundError(f"配置文件 {env_path} 未找到")
    with open(env_path, 'r', encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                key, value = line.split('=', 1)
                os.environ[key] = value


class Config:
    """所有参数通过 update_config_from_env 动态添加"""
    pass


def update_config_from_env():
    """强制从环境变量读取运动学参数，缺少引发KeyError"""
    Config.MAX_SWING_ANGLE = float(os.environ['MAX_SWING_ANGLE'])
    Config.ARM_MIN_EXTEND   = float(os.environ['ARM_MIN_EXTEND'])    # cm
    Config.ARM_MAX_EXTEND   = float(os.environ['ARM_MAX_EXTEND'])    # cm
    Config.MIN_LENGTH_MM    = float(os.environ['MIN_LENGTH_MM'])
    Config.MAX_LENGTH_MM    = float(os.environ['MAX_LENGTH_MM'])
    Config.MAX_WORKERS      = int(os.environ['MAX_WORKERS'])
    Config.CYCLE_INTERVAL   = float(os.environ['CYCLE_INTERVAL'])    # 指令周期间隔

    # =========图片任务新增：增量限位参数（从rob_arm.env读取）=========
    Config.DELTA_ROT_LIMIT_DEG   = float(os.environ["DELTA_ROT_LIMIT_DEG"])
    Config.DELTA_SWING_LIMIT_DEG = float(os.environ["DELTA_SWING_LIMIT_DEG"])
    Config.DELTA_EXTEND_LIMIT_MM = float(os.environ["DELTA_EXTEND_LIMIT_MM"])


def solve_3dof(arm_base, target_p):
    """
    3自由度逆运动学解算【ROS1原版数学逻辑原样保留，不做任何修改】
    返回关节目标角度/长度 j1(deg), j2(deg), j3(cm)
    """
    dx, dy, dz = target_p - arm_base
    dxy = np.hypot(dx, dy)
    j1 = np.degrees(np.arctan2(dy, dx)) if dxy > 1e-3 else 0.0
    ideal_j2 = np.pi/2 if abs(dz) < 1e-6 else np.arctan2(dxy, dz)
    limited_j2 = np.clip(ideal_j2, -np.radians(Config.MAX_SWING_ANGLE), np.radians(Config.MAX_SWING_ANGLE))
    if abs(np.degrees(ideal_j2)) > Config.MAX_SWING_ANGLE:
        rospy_logwarn_fake = f"摆动角超限! 理想值: {np.degrees(ideal_j2):.2f}°, 已限制至 {Config.MAX_SWING_ANGLE}°"
    j3 = dxy if abs(dz) < 1e-6 else dz / np.cos(limited_j2)
    j3 = np.clip(j3, Config.ARM_MIN_EXTEND, Config.ARM_MAX_EXTEND)
    return round(j1, 2), round(np.degrees(limited_j2), 2), round(j3, 2)


class KinematicsNode(Node):
    """逆运动学节点：接收最优托举点，发布增量指令，并记录数据库；ROS2迁移版本"""
    def __init__(self):
        super().__init__("arm_kinematics")
        load_env_config()
        update_config_from_env()

        # 图片任务：ROS消息层回调组
        self.callback_group = ReentrantCallbackGroup()
        # 图片任务：独立计算线程池，专门跑逆解，不参与ROS spin
        self.compute_pool = ThreadPoolExecutor(max_workers=Config.MAX_WORKERS)

        # ---------- 话题全部强制读取环境变量 ----------
        topic_alpha_beta = os.environ['ROS_TOPIC_ARM_ALPHA_BETA']
        topic_rot_fb = os.environ['ROS_TOPIC_ROTATION_FEEDBACK']
        topic_sw_fb  = os.environ['ROS_TOPIC_SWING_FEEDBACK']
        topic_tel_fb = os.environ['ROS_TOPIC_TELESCOPE_FEEDBACK']

        topic_rot_cmd = os.environ['ROS_TOPIC_KINEMATICS_ROTATION_CMD_INPUT']
        topic_sw_cmd  = os.environ['ROS_TOPIC_KINEMATICS_SWING_CMD_INPUT']
        topic_tel_cmd = os.environ['ROS_TOPIC_KINEMATICS_TELESCOPIC_CMD_INPUT']

        self.arm_states = {}
        self.lock = Lock()

        # ---------- 订阅 ----------
        self.sub_alpha_beta = self.create_subscription(
            String,
            topic_alpha_beta,
            self.alpha_beta_callback,
            10,
            callback_group=self.callback_group
        )
        self.sub_rot_fb = self.create_subscription(
            RotationCmd,
            topic_rot_fb,
            self.rotation_feedback_cb,
            10,
            callback_group=self.callback_group
        )
        self.sub_sw_fb = self.create_subscription(
            SwingCmd,
            topic_sw_fb,
            self.swing_feedback_cb,
            10,
            callback_group=self.callback_group
        )
        self.sub_tel_fb = self.create_subscription(
            TelescopicCmd,
            topic_tel_fb,
            self.telescopic_feedback_cb,
            10,
            callback_group=self.callback_group
        )

        # ---------- 发布 ----------
        self.pub_rotation   = self.create_publisher(RotationCmd, topic_rot_cmd, 10)
        self.pub_swing      = self.create_publisher(SwingCmd, topic_sw_cmd, 10)
        self.pub_telescopic = self.create_publisher(TelescopicCmd, topic_tel_cmd, 10)

        self.current_state = {}

        # ---------- 数据库初始化 ----------
        db_path = os.environ.get('DB_PATH', 'ros_database.db')
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._create_table()

        self.get_logger().info("✅ kinematics_node ROS2启动；数据库已连接")
        self.get_logger().info(
            f"增量限位：delta_rot ±{Config.DELTA_ROT_LIMIT_DEG}°, "
            f"delta_swing ±{Config.DELTA_SWING_LIMIT_DEG}°, "
            f"delta_telescopic ±{Config.DELTA_EXTEND_LIMIT_MM} mm | 周期{Config.CYCLE_INTERVAL}s"
        )

    def _create_table(self):
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
        return {1: 32, 2: 64, 3: 96}.get(arm_id, 0)

    # --------硬件反馈回调（原始映射逻辑不变）--------
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
            self.current_state[arm_id] = {"rotation":0.0, "swing":0.0, "telescopic":0.0}
        if arm_id not in self.arm_states:
            self.arm_states[arm_id] = {"last_time":0, "pending_cmds":deque()}

    def alpha_beta_callback(self, msg: String):
        """ROS消息回调：只提交任务到计算池，立刻返回，不阻塞消息线程【图片任务强制要求】"""
        try:
            payload = msg.data
            fut = self.compute_pool.submit(self._task_work, payload)
            fut.add_done_callback(self._on_task_finished)
        except Exception as e:
            self.get_logger().error(f"kinematics alpha_beta回调异常 {str(e)}", exc_info=True)

    def _task_work(self, json_str):
        start_time = time.time()
        modules = json.loads(json_str)
        all_module_results = []
        futures = [self.compute_pool.submit(self.process_module, mod) for mod in modules]
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

            self.get_logger().info(f"📥 模块{mid} 指令已加入队列")

        for arm_id in self.arm_states.keys():
            self.process_arm_queue(arm_id)

        duration = round((time.time() - start_time)*1000, 2)
        return {"module_cnt":len(all_module_results), "ms":duration}

    def _on_task_finished(self, future):
        try:
            ret = future.result()
            self.get_logger().info(f"kinematics处理 {ret['module_cnt']} 模块，耗时 {ret['ms']}ms")
        except Exception as e:
            self.get_logger().error(f"kinematics计算任务完成回调异常 {str(e)}", exc_info=True)

    def process_arm_queue(self, arm_id):
        """按周期取出指令，ROS2实现oneshot延时定时器"""
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
                delay = Config.CYCLE_INTERVAL - time_since_last
                self.get_logger().info(f"⏳ 臂{arm_id} 等待中，剩余 {delay:.1f}s")
                # ROS2 oneshot一次性定时器
                self.create_timer(
                    delay,
                    lambda event, aid=arm_id: self.process_arm_queue(aid),
                    callback_group=self.callback_group
                )
                return
        self.publish_cmd(cmd)
        with self.lock:
            if self.arm_states[arm_id]["pending_cmds"]:
                delay = Config.CYCLE_INTERVAL - (time.time() - state["last_time"])
                self.create_timer(
                    max(0.0, delay),
                    lambda event, aid=arm_id: self.process_arm_queue(aid),
                    callback_group=self.callback_group
                )

    def publish_cmd(self, cmd):
        mid = cmd["module_id"]
        arm_id = cmd["arm_id"]
        target_j1 = cmd["target_j1"]
        target_j2 = cmd["target_j2"]
        target_j3_cm = cmd["target_j3_cm"]
        self._ensure_arm(arm_id)

        cur_rot = self.current_state[arm_id]["rotation"]
        cur_sw  = self.current_state[arm_id]["swing"]
        cur_tel = self.current_state[arm_id]["telescopic"]

        delta_rot = cur_rot - target_j1
        delta_sw  = target_j2 - cur_sw
        target_j3_mm = target_j3_cm * 10.0
        delta_tel = target_j3_mm - cur_tel

        # =========图片任务要求：增量硬裁剪np.clip，放在增量计算的末尾=========
        delta_rot  = np.clip(delta_rot, -Config.DELTA_ROT_LIMIT_DEG, Config.DELTA_ROT_LIMIT_DEG)
        delta_sw   = np.clip(delta_sw,  -Config.DELTA_SWING_LIMIT_DEG, Config.DELTA_SWING_LIMIT_DEG)
        delta_tel  = np.clip(delta_tel, -Config.DELTA_EXTEND_LIMIT_MM, Config.DELTA_EXTEND_LIMIT_MM)

        dev_rot = arm_id * 32 + 1
        dev_sw  = arm_id * 32 + 2
        dev_tel = arm_id * 32 + 3
        stamp = Time.now().to_msg()

        rot_msg = RotationCmd()
        rot_msg.header.stamp = stamp
        rot_msg.module_id = mid
        rot_msg.device_id = dev_rot
        rot_msg.position = [float(delta_rot)]
        self.pub_rotation.publish(rot_msg)

        sw_msg = SwingCmd()
        sw_msg.header.stamp = stamp
        sw_msg.module_id = mid
        sw_msg.device_id = dev_sw
        sw_msg.position = [float(delta_sw)]
        self.pub_swing.publish(sw_msg)

        tel_msg = TelescopicCmd()
        tel_msg.header.stamp = stamp
        tel_msg.module_id = mid
        tel_msg.device_id = dev_tel
        tel_msg.position = [float(delta_tel)]
        self.pub_telescopic.publish(tel_msg)

        alpha = [target_j1, target_j2, target_j3_cm]
        self._save_arm_record(mid, arm_id, alpha, delta_rot, delta_sw, delta_tel)
        self.get_logger().info(
            f"📤模块{mid} 臂{arm_id} | rot:{delta_rot:+.2f}° swing:{delta_sw:+.2f}° tel:{delta_tel:+.1f}mm"
        )

    def _save_arm_record(self, module_id, arm_id, alpha, delta_rot, delta_sw, delta_tel):
        unit = self.arm_to_unit(arm_id)
        coord_dict = {str(unit): alpha}
        position_dict = {
            str(arm_id * 32 + 1): round(delta_rot, 2),
            str(arm_id * 32 + 2): round(delta_sw, 2),
            str(arm_id * 32 + 3): round(delta_tel, 1)
        }
        now = datetime.now()
        createtime = now.strftime("%Y-%m-%d %H:%M:%S.") + f"{now.microsecond // 1000:03d}-{random.randint(0,9999):04d}"
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
                0,
                2,
                json.dumps(coord_dict),
                json.dumps(position_dict),
                False,
                ""
            ))
            self.conn.commit()
        except Exception as e:
            self.get_logger().error(f"数据库写入失败: {e}")

    def process_module(self, mod):
        try:
            mid = mod["module_id"]
            arm_items = mod["alpha_beta"]
            arm_results = []
            tasks = [self.compute_pool.submit(self.process_single_arm, item) for item in arm_items]
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
            self.get_logger().error(f"模块解算异常 {str(e)}", exc_info=True)
            return None

    def process_single_arm(self, item):
        base = np.array(item["base"])
        alpha = np.array(item["alpha"])
        j1, j2, j3 = solve_3dof(base, alpha)
        if abs(j2) == Config.MAX_SWING_ANGLE:
            self.get_logger().warn(f"机械臂 {item.get('arm_id','?')} 摆动角极限 {j2}°")
        return {
            "alpha": alpha.tolist(),
            "beta": item["beta"],
            "j1_rotate_deg": j1,
            "j2_swing_deg": j2,
            "j3_extend_cm": j3
        }

    def shutdown_hook(self):
        """图片任务：线程池优雅关闭，等待正在执行任务完成"""
        self.compute_pool.shutdown(wait=True)
        self.conn.close()
        self.get_logger().info("✅ kinematics_node：计算线程池、数据库连接已关闭")


def main(args=None):
    rclpy.init(args=args)
    node = KinematicsNode()
    executor = MultiThreadedExecutor(num_threads=2)
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.shutdown_hook()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()