#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
节点A：最优托举点计算 α/β估计
策略链：垂直区域 → 水平平面 → 曲面自适应 → 默认
曲面得分：DISTANCE_WEIGHT=0.6 ANGLE_WEIGHT=0.4
ROS2迁移，严格按照图片任务要求，原有点云算法完全保留不修改
并发：MultiThreadedExecutor+ReentrantCallbackGroup(ROS消息)，独立ThreadPoolExecutor(max_workers=4)做计算
"""
import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from rclpy.callback_groups import ReentrantCallbackGroup
from concurrent.futures import ThreadPoolExecutor
import json
import numpy as np
import time
import sqlite3
import open3d as o3d
import os
import random
from datetime import datetime
from scipy.spatial import KDTree
from std_msgs.msg import String

# =============== 性能监控装饰器【原版原样保留】 ===============
def timeit(func):
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        duration = round((time.time() - start) * 1000, 2)
        wrapper.total_time = getattr(wrapper, 'total_time', 0) + duration
        wrapper.call_count = getattr(wrapper, 'call_count', 0) + 1
        return result
    return wrapper

# =============== 配置类 ===============
class Config:
    pass

def load_env_config():
    """从 .env 文件加载所有配置到环境变量"""
    env_path = os.path.join(os.path.dirname(__file__), '../rob_arm.env')
    if not os.path.exists(env_path):
        raise FileNotFoundError(f"配置文件 {env_path} 未找到")
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                key, value = line.split('=', 1)
                os.environ[key] = value

def update_config_from_env():
    """从环境变量读取配置，未定义使用内置默认值，全部沿用ROS1原版"""
    Config.VOXEL_SIZE             = float(os.environ.get('VOXEL_SIZE', 0.1))
    Config.MAX_WORKERS            = int(os.environ.get('MAX_WORKERS', 4))
    Config.MAX_SWING_ANGLE        = float(os.environ.get('MAX_SWING_ANGLE', 20.0))
    Config.ARM_MIN_EXTEND         = float(os.environ.get('ARM_MIN_EXTEND', 1.0))
    Config.ARM_MAX_EXTEND         = float(os.environ.get('ARM_MAX_EXTEND', 60.0))
    Config.VERTICAL_CHECK_RADIUS  = float(os.environ.get('VERTICAL_CHECK_RADIUS', 1.0))
    Config.VERTICAL_FLAT_TOLERANCE = float(os.environ.get('VERTICAL_FLAT_TOLERANCE', 0.3))
    Config.SURFACE_EXTRACT_K      = int(os.environ.get('SURFACE_EXTRACT_K', 20))
    Config.SURFACE_ANGLE_THRESH   = float(os.environ.get('SURFACE_ANGLE_THRESH', 30.0))
    Config.NORMAL_RADIUS          = float(os.environ.get('NORMAL_RADIUS', 2.0))
    Config.HORIZONTAL_ANGLE_THRESH = float(os.environ.get('HORIZONTAL_ANGLE_THRESH', 5.0))
    Config.HORIZONTAL_Z_STD       = float(os.environ.get('HORIZONTAL_Z_STD', 0.5))
    Config.DEFAULT_HEIGHT         = float(os.environ.get('DEFAULT_HEIGHT', 11.0))
    Config.MIN_POINTS_FOR_PCA     = int(os.environ.get('MIN_POINTS_FOR_PCA', 3))
    Config.POINT_SELECT_STRATEGY  = os.environ.get('POINT_SELECT_STRATEGY', 'balanced')
    Config.DISTANCE_WEIGHT        = float(os.environ.get('DISTANCE_WEIGHT', 0.6))
    Config.ANGLE_WEIGHT           = float(os.environ.get('ANGLE_WEIGHT', 0.4))
    Config.DB_PATH                = os.environ.get('DB_PATH', 'ros_database.db')

# =============== 工具函数【ROS1原版逻辑完全复制，不作修改】 ===============
@timeit
def extract_surface_points(points, k=None, angle_thresh=None):
    if k is None:
        k = Config.SURFACE_EXTRACT_K
    if angle_thresh is None:
        angle_thresh = Config.SURFACE_ANGLE_THRESH
    if len(points) < k:
        return points.copy()
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points)
    pcd.estimate_normals(
        search_param=o3d.geometry.KDTreeSearchParamKNN(k),
        fast_normal_computation=True
    )
    normals = np.asarray(pcd.normals)
    tree = KDTree(points)
    _, indices = tree.query(points, k=k+1)
    is_surface = np.zeros(len(points), dtype=bool)
    for i in range(len(points)):
        ref = normals[i]
        neighbor_normals = normals[indices[i][1:]]
        cos_angles = np.abs(np.dot(neighbor_normals, ref))
        angles = np.degrees(np.arccos(np.clip(cos_angles, -1, 1)))
        if np.max(angles) > angle_thresh:
            is_surface[i] = True
    return points[is_surface]

@timeit
def compute_point_normal(point, points, radius=None):
    if radius is None:
        radius = Config.NORMAL_RADIUS
    if len(points) < Config.MIN_POINTS_FOR_PCA:
        return np.array([0, 0, -1])
    dists = np.linalg.norm(points - point, axis=1)
    neighbor_indices = np.where(dists < radius)[0]
    if len(neighbor_indices) < Config.MIN_POINTS_FOR_PCA:
        return np.array([0, 0, -1])
    neighbor_pts = points[neighbor_indices]
    pcd_neighbor = o3d.geometry.PointCloud()
    pcd_neighbor.points = o3d.utility.Vector3dVector(neighbor_pts)
    pcd_neighbor.estimate_normals(
        search_param=o3d.geometry.KDTreeSearchParamKNN(len(neighbor_indices))
    )
    normal = np.asarray(pcd_neighbor.normals)[0]
    return normal if normal[2] < 0 else -normal

@timeit
def is_horizontal_plane(points):
    if len(points) < 3:
        return False, np.array([0, 0, 1])
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points)
    plane_model, inliers = pcd.segment_plane(
        distance_threshold=Config.HORIZONTAL_Z_STD,
        ransac_n=3,
        num_iterations=100
    )
    if len(inliers) < 0.5 * len(points):
        return False, np.array([0, 0, 1])
    normal = np.array(plane_model[:3])
    normal /= np.linalg.norm(normal)
    gravity = np.array([0, 0, 1])
    angle = np.degrees(np.arccos(np.clip(np.abs(np.dot(normal, gravity)), 0, 1)))
    z_std = np.std(points[:, 2])
    return (angle < Config.HORIZONTAL_ANGLE_THRESH) and (z_std < Config.HORIZONTAL_Z_STD), normal

# =============== 点选择与策略控制器【原版全部保留，策略链不变】 ===============
class FusionPointSelector:
    def __init__(self):
        self.stats = {"vertical": 0, "horizontal": 0, "surface": 0}
        self.tree_cache = {}
        self.strategy_used = ""
    def downsample_points(self, points):
        if len(points) < 1000:
            return points
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(points)
        pcd = pcd.voxel_down_sample(Config.VOXEL_SIZE)
        return np.asarray(pcd.points)
    def get_cached_tree(self, points):
        points_hash = hash(points.tobytes())
        if points_hash in self.tree_cache:
            return self.tree_cache[points_hash]
        tree = KDTree(points)
        self.tree_cache[points_hash] = tree
        return tree
    def find_optimal_point(self, base, points):
        if len(points) == 0:
            return None
        local = points - base
        r = np.linalg.norm(local, axis=1)
        dxy = np.linalg.norm(local[:, :2], axis=1)
        r_safe = np.where(r < 1e-6, 1e-6, r)
        phi = np.arcsin(np.clip(dxy / r_safe, -1, 1))
        valid_mask = (r >= Config.ARM_MIN_EXTEND) & (r <= Config.ARM_MAX_EXTEND)
        if Config.POINT_SELECT_STRATEGY == "min_angle":
            self.strategy_used = "min_angle"
            return points[np.argmin(phi)]
        elif Config.POINT_SELECT_STRATEGY == "min_distance":
            self.strategy_used = "min_distance"
            return points[np.argmin(r)]
        else:
            self.strategy_used = "balanced"
            r_score = (r - np.min(r)) / (np.max(r) - np.min(r) + 1e-6)
            phi_score = phi / np.max(phi) if np.max(phi) > 0 else 0
            combined = Config.DISTANCE_WEIGHT * r_score + Config.ANGLE_WEIGHT * phi_score
            if np.any(valid_mask):
                best = np.where(valid_mask)[0][np.argmin(combined[valid_mask])]
                return points[best]
            else:
                return points[np.argmin(combined)]
    def process_arm(self, arm_base, points):
        points = self.downsample_points(points)
        if len(points) == 0:
            return self._create_default_result(arm_base)
        res = self._try_vertical_strategy(arm_base, points)
        if res:
            return res
        res = self._try_horizontal_strategy(arm_base, points)
        if res:
            return res
        return self._surface_strategy(arm_base, points)
    def _try_vertical_strategy(self, arm_base, points):
        cx, cy, cz = arm_base
        mask = (points[:, 0] - cx)**2 + (points[:, 1] - cy)**2 < Config.VERTICAL_CHECK_RADIUS**2
        local_pts = points[mask]
        if len(local_pts) >= 5 and (np.max(local_pts[:, 2]) - np.min(local_pts[:, 2]) <= Config.VERTICAL_FLAT_TOLERANCE):
            target_z = np.median(local_pts[:, 2])
            arm_extend = target_z - cz
            if Config.ARM_MIN_EXTEND <= arm_extend <= Config.ARM_MAX_EXTEND:
                alpha = np.array([cx, cy, target_z])
                self.stats["vertical"] += 1
                self.strategy_used = "vertical"
                return alpha, np.array([0, 0, -1]), "vertical"
        return None
    def _try_horizontal_strategy(self, arm_base, points):
        is_flat, _ = is_horizontal_plane(points)
        if is_flat:
            center = np.mean(points, axis=0)
            dist_sq = (points[:,0]-center[0])**2 + (points[:,1]-center[1])**2
            near_center = dist_sq < 4.0
            z_med = np.median(points[near_center, 2]) if np.sum(near_center) > 3 else center[2]
            alpha = np.array([center[0], center[1], z_med])
            arm_extend = alpha[2] - arm_base[2]
            if Config.ARM_MIN_EXTEND <= arm_extend <= Config.ARM_MAX_EXTEND:
                self.stats["horizontal"] += 1
                self.strategy_used = "horizontal"
                return alpha, np.array([0, 0, -1]), "horizontal"
        return None
    def _surface_strategy(self, arm_base, points):
        surface_pts = extract_surface_points(points) if len(points) > 50 else points
        alpha = self.find_optimal_point(arm_base, surface_pts)
        if alpha is None:
            alpha = points[np.argmin(np.linalg.norm(points - arm_base, axis=1))]
        beta = compute_point_normal(alpha, points)
        self.stats["surface"] += 1
        return alpha, beta, self.strategy_used
    def _create_default_result(self, arm_base):
        cx, cy, cz = arm_base
        alpha = np.array([cx, cy, cz + Config.DEFAULT_HEIGHT])
        return alpha, np.array([0, 0, -1]), "default"

# =============== ROS2节点主体 ===============
class PointSelectorNode(Node):
    def __init__(self):
        super().__init__("arm_point_selector")
        load_env_config()
        update_config_from_env()
        # 话题强制从环境变量读取
        self.topic_module_arm_task = os.environ['ROS_TOPIC_MODULE_ARM_TASK']
        self.topic_arm_alpha_beta = os.environ['ROS_TOPIC_ARM_ALPHA_BETA']
        self.topic_arm_fusion_stats = os.environ['ROS_TOPIC_ARM_FUSION_STATS']

        self.callback_group = ReentrantCallbackGroup()
        # 图片要求：独立计算线程池 max_workers=4，仅用于业务计算，不做ROS spin
        self.compute_pool = ThreadPoolExecutor(max_workers=Config.MAX_WORKERS)

        self.selector = FusionPointSelector()
        self.sub_task = self.create_subscription(
            String,
            self.topic_module_arm_task,
            self.task_callback,
            10,
            callback_group=self.callback_group
        )
        self.pub_alpha_beta = self.create_publisher(String, self.topic_arm_alpha_beta, 10)
        self.stats_pub = self.create_publisher(String, self.topic_arm_fusion_stats, 1)
        self.timer_stats = self.create_timer(10.0, self.publish_stats, callback_group=self.callback_group)

        self.conn = sqlite3.connect(Config.DB_PATH, check_same_thread=False)
        self._create_table()
        self.get_logger().info("✅ calculation_node(αβ选点) ROS2启动；策略链：垂直→水平→曲面→默认")

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
    def arm_to_ids(arm_id):
        mapping = {1: 32, 2: 64, 3: 96}
        return mapping.get(arm_id, 0)

    def task_callback(self, msg: String):
        """ROS消息回调：仅提交任务至计算池，立刻返回，不阻塞消息线程（图片要求）"""
        try:
            payload = msg.data
            fut = self.compute_pool.submit(self._task_work, payload)
            fut.add_done_callback(self._on_task_done)
        except Exception as e:
            self.get_logger().error(f"task回调异常: {str(e)}")

    @timeit
    def _task_work(self, json_str):
        modules = json.loads(json_str)
        out = []
        futures = [self.compute_pool.submit(self.process_module, mod) for mod in modules]
        for future in futures:
            res = future.result()
            if res:
                out.append(res)
        for mod in out:
            module_id = mod["module_id"]
            coord_dict = {}
            position_dict = {}
            for arm in mod["alpha_beta"]:
                arm_id = arm["arm_id"]
                unit = self.arm_to_ids(arm_id)
                coord_dict[str(unit)] = {
                    "alpha": arm["alpha"],
                    "arm_id": arm_id,
                    "base": arm["base"],
                    "strategy": arm["strategy"]
                }
                position_dict[str(unit)] = arm["beta"]
            self._save_module_record(module_id, coord_dict, position_dict)
        return out

    def _on_task_done(self, future):
        try:
            out = future.result()
            if out:
                msg_out = String()
                msg_out.data = json.dumps(out, ensure_ascii=False)
                self.pub_alpha_beta.publish(msg_out)
                self.get_logger().info(f"发布{len(out)}个模块αβ结果")
        except Exception as e:
            self.get_logger().error(f"计算任务完成回调异常 {str(e)}", exc_info=True)

    def _save_module_record(self, module_id, coord_dict, position_dict):
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
                0,
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
            pts = np.array(mod["points"])
            arms = np.array(mod["arms"])
            arm_results = []
            tasks = []
            for i, base in enumerate(arms):
                tasks.append({
                    "arm_id": i + 1,
                    "base": base,
                    "future": self.compute_pool.submit(self.selector.process_arm, base, pts.copy())
                })
            for task in tasks:
                alpha, beta, strategy = task["future"].result()
                arm_results.append({
                    "arm_id": task["arm_id"],
                    "base": np.round(task["base"], 2).tolist(),
                    "alpha": np.round(alpha, 2).tolist(),
                    "beta": np.round(beta, 4).tolist(),
                    "strategy": strategy
                })
            return {"module_id": mid, "alpha_beta": arm_results}
        except Exception as e:
            self.get_logger().error(f"模块处理异常: {str(e)}", exc_info=True)
            return None

    def publish_stats(self):
        stats = self.selector.stats
        total = sum(stats.values())
        msg = String()
        msg.data = json.dumps({"total": total, **stats})
        self.stats_pub.publish(msg)

    def shutdown_hook(self):
        self.compute_pool.shutdown(wait=True)
        self.conn.close()
        self.get_logger().info("calculation_node：线程池、数据库已关闭")


def main(args=None):
    rclpy.init(args=args)
    node = PointSelectorNode()
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
