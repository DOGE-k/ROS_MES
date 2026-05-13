#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
节点A：最优托举点计算（不包含运动学解算）
发布话题：/arm_alpha_beta
"""

import rospy
import json
import numpy as np
import time
import open3d as o3d
from concurrent.futures import ThreadPoolExecutor
from scipy.spatial import KDTree
from std_msgs.msg import String

# =============== 性能监控装饰器（可继承自原代码） ===============
def timeit(func):
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        duration = round((time.time() - start) * 1000, 2)
        wrapper.total_time = getattr(wrapper, 'total_time', 0) + duration
        wrapper.call_count = getattr(wrapper, 'call_count', 0) + 1
        return result
    return wrapper

# =============== 配置参数 ===============
class Config:
    VOXEL_SIZE = 0.1
    MAX_WORKERS = 4
    MAX_SWING_ANGLE = 20.0      # 此处虽用不到，但保留便于后续统一配置
    ARM_MIN_EXTEND = 1.0
    ARM_MAX_EXTEND = 60.0
    VERTICAL_CHECK_RADIUS = 1.0
    VERTICAL_FLAT_TOLERANCE = 0.3
    SURFACE_EXTRACT_K = 20
    SURFACE_ANGLE_THRESH = 30.0
    NORMAL_RADIUS = 2.0
    HORIZONTAL_ANGLE_THRESH = 5.0
    HORIZONTAL_Z_STD = 0.5
    DEFAULT_HEIGHT = 11.0
    MIN_POINTS_FOR_PCA = 3
    POINT_SELECT_STRATEGY = "balanced"
    DISTANCE_WEIGHT = 0.6
    ANGLE_WEIGHT = 0.4

# =============== 工具函数（仅点云处理，无运动学） ===============
@timeit
def extract_surface_points(points, k=Config.SURFACE_EXTRACT_K, angle_thresh=Config.SURFACE_ANGLE_THRESH):
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
def compute_point_normal(point, points, radius=Config.NORMAL_RADIUS):
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

# =============== 点选择与策略控制器（无运动学） ===============
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
        else:  # balanced
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
        """返回 (alpha, beta, strategy) 三元组，无角度"""
        points = self.downsample_points(points)
        if len(points) == 0:
            return self._create_default_result(arm_base)

        # 垂直策略
        res = self._try_vertical_strategy(arm_base, points)
        if res:
            return res
        # 水平策略
        res = self._try_horizontal_strategy(arm_base, points)
        if res:
            return res
        # 曲面策略
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

# =============== ROS节点A ===============
class PointSelectorNode:
    def __init__(self):
        rospy.init_node("arm_point_selector")
        self.selector = FusionPointSelector()
        self.executor = ThreadPoolExecutor(max_workers=Config.MAX_WORKERS)

        rospy.Subscriber("/module_arm_task", String, self.task_callback)
        self.pub_alpha_beta = rospy.Publisher("/arm_alpha_beta", String, queue_size=10)
        self.stats_pub = rospy.Publisher("/arm_fusion_stats", String, queue_size=1)
        rospy.Timer(rospy.Duration(10), self.publish_stats)

        rospy.loginfo("节点A（最优点选取）启动")

    def task_callback(self, msg):
        try:
            start_time = time.time()
            modules = json.loads(msg.data)
            out = []
            futures = [self.executor.submit(self.process_module, mod) for mod in modules]
            for future in futures:
                res = future.result()
                if res:
                    out.append(res)
            if out:
                self.pub_alpha_beta.publish(json.dumps(out, ensure_ascii=False))
            rospy.loginfo(f"节点A 发送 {len(out)} 个模块 | 耗时 {round((time.time()-start_time)*1000,2)}ms")
        except Exception as e:
            rospy.logerr(f"节点A处理异常: {str(e)}", exc_info=True)

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
                    "future": self.executor.submit(self.selector.process_arm, base, pts.copy())
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
            rospy.logerr(f"模块处理异常: {str(e)}", exc_info=True)
            return None

    def publish_stats(self, event):
        stats = self.selector.stats
        total = sum(stats.values())
        self.stats_pub.publish(json.dumps({"total": total, **stats}))

if __name__ == "__main__":
    try:
        PointSelectorNode()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass