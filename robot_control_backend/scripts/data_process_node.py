#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
点云处理节点（融合版）：接收前端路径或直接点云，处理后发布模块任务。
- 从 .env 强制读取所有配置参数，缺失则崩溃
- 包含数据库记录、点云预处理、模块切分、可视化等模块
"""

import rospy
import json
import numpy as np
import open3d as o3d
from std_msgs.msg import String
from flask import Flask, send_file
import threading
import os
import sqlite3
from datetime import datetime

app = Flask(__name__)
output_dir = "/tmp/ros_pointcloud_output/"

if not os.path.exists(output_dir):
    os.makedirs(output_dir)
    rospy.loginfo(f"📂 已创建输出目录: {output_dir}")

# ===================== 数据库配置 =====================
DB_FILE = "ros_database.db"          # 与节点B共享的数据库文件
DEFAULT_CREATER_ID = 1
DEFAULT_DEL_FLAG = 0
DEFAULT_NOTES = None

# ===================== 全局参数（将从 .env 强制加载） =====================
MODULE_ORIGIN_X = None
MODULE_ORIGIN_Y = None
MODULE_ORIGIN_Z = None
MODULE_SIZE_X = None
MODULE_SIZE_Y = None
ARM_MIN_HEIGHT = None
ARM_SAFE_GAP = None
TOPIC_FRONTEND_INPUT = None
TOPIC_MODULE_ARM_TASK = None

module_pub = None


# ===================== 数据库初始化 =====================
def init_database():
    """创建 point_data 表（如果不存在）"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS point_data (
            Createtime DATETIME NOT NULL PRIMARY KEY,
            creater_id INT NOT NULL,
            Module_id INT,
            point TEXT NOT NULL,
            arms_address TEXT NOT NULL,
            del_flag BOOL DEFAULT false,
            Notes TEXT
        )
        ''')
        conn.commit()
        conn.close()
        rospy.loginfo(f"🗄️ 数据库初始化成功: {os.path.abspath(DB_FILE)}")
    except Exception as e:
        rospy.logerr(f"❌ 数据库初始化失败: {e}")
        raise


# ===================== 数据库存储 =====================
def save_modules_to_database(modules):
    """将切分出的模块点云与机械臂基座数据存入 point_data 表"""
    if not modules:
        rospy.logwarn("⚠️ 无模块数据，跳过数据库存储")
        return
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        success_count = 0
        for module in modules:
            point_json = json.dumps(module["points"])
            arms_json = json.dumps(module["arms"])
            cursor.execute('''
            INSERT INTO point_data (Createtime, creater_id, Module_id, point, arms_address, del_flag, Notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (current_time, DEFAULT_CREATER_ID, module["module_id"], point_json, arms_json, DEFAULT_DEL_FLAG, DEFAULT_NOTES))
            success_count += 1
        conn.commit()
        conn.close()
        rospy.loginfo(f"✅ 数据库存储完成: {success_count} 条记录")
    except Exception as e:
        rospy.logerr(f"❌ 数据库存储失败: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()


# ===================== 配置加载（无兜底，强制读取） =====================
def load_env_config():
    """从 rob_arm.env 加载所有配置到环境变量，文件必须存在"""
    env_path = os.path.join(os.path.dirname(__file__), '../rob_arm.env')
    if not os.path.exists(env_path):
        rospy.logerr(f"❌ 配置文件不存在: {env_path}")
        raise FileNotFoundError(f"配置文件 {env_path} 未找到")
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                key, value = line.split('=', 1)
                os.environ[key] = value
    rospy.loginfo("✅ 点云处理节点已从 rob_arm.env 加载配置")


def update_params_from_env():
    """强制从环境变量读取参数，缺失将抛出 KeyError"""
    global MODULE_ORIGIN_X, MODULE_ORIGIN_Y, MODULE_ORIGIN_Z
    global MODULE_SIZE_X, MODULE_SIZE_Y
    global ARM_MIN_HEIGHT, ARM_SAFE_GAP
    global TOPIC_FRONTEND_INPUT, TOPIC_MODULE_ARM_TASK

    MODULE_ORIGIN_X = float(os.environ['MODULE_ORIGIN_X'])
    MODULE_ORIGIN_Y = float(os.environ['MODULE_ORIGIN_Y'])
    MODULE_ORIGIN_Z = float(os.environ['MODULE_ORIGIN_Z'])
    MODULE_SIZE_X = int(os.environ['MODULE_SIZE_X'])
    MODULE_SIZE_Y = int(os.environ['MODULE_SIZE_Y'])
    ARM_MIN_HEIGHT = float(os.environ['ARM_MIN_HEIGHT'])
    ARM_SAFE_GAP = float(os.environ['ARM_SAFE_GAP'])

    TOPIC_FRONTEND_INPUT = os.environ['ROS_TOPIC_FRONTEND_POINTCLOUD']
    TOPIC_MODULE_ARM_TASK = os.environ['ROS_TOPIC_MODULE_ARM_TASK']


# ===================== 点云摆正 =====================
def align_max_face_down(pcd):
    """PCA 摆正：最长轴→Y，次长轴→X，最短轴朝下（Z）"""
    pts = np.asarray(pcd.points)
    center = np.mean(pts, axis=0)
    cov = np.cov((pts - center).T)
    _, eigvecs = np.linalg.eigh(cov)

    v_short = eigvecs[:, 0]   # 最短轴 → Z（朝下）
    v_mid   = eigvecs[:, 1]   # 次长轴 → X
    v_long  = eigvecs[:, 2]   # 最长轴 → Y

    if np.dot(v_short, np.array([0, 0, -1])) < 0:
        v_short = -v_short

    R = np.array([v_mid, v_long, -v_short])
    if np.linalg.det(R) < 0:
        R[1, :] *= -1

    pcd_rotated = o3d.geometry.PointCloud(pcd)
    pcd_rotated.rotate(R, center=center)
    return pcd_rotated


# ===================== 移动到工作原点 =====================
def move_to_origin(points):
    """将点云移动至模块原点，并进行安全居中处理"""
    min_x, max_x = np.min(points[:,0]), np.max(points[:,0])
    min_y, max_y = np.min(points[:,1]), np.max(points[:,1])
    min_z = np.min(points[:,2])

    SAFE_LIMIT_X, SAFE_LIMIT_Y = 15.0, 35.0
    obj_w_x = max_x - min_x
    obj_h_y = max_y - min_y

    if obj_w_x <= SAFE_LIMIT_X:
        cx = (min_x + max_x) / 2.0
        target_cx = MODULE_ORIGIN_X + MODULE_SIZE_X / 2.0
        points[:,0] += (target_cx - cx)
    else:
        points[:,0] += (MODULE_ORIGIN_X - min_x)

    if obj_h_y <= SAFE_LIMIT_Y:
        cy = (min_y + max_y) / 2.0
        target_cy = MODULE_ORIGIN_Y + MODULE_SIZE_Y / 2.0
        points[:,1] += (target_cy - cy)
    else:
        points[:,1] += (MODULE_ORIGIN_Y - min_y)

    target_z = MODULE_ORIGIN_Z + ARM_MIN_HEIGHT + ARM_SAFE_GAP
    dz = target_z - min_z
    points[:,2] += dz
    rospy.loginfo(f"📍 点云已移动：最低 Z {min_z:.2f} → {target_z:.1f} cm")
    return points


# ===================== 切分为模块 =====================
def split_into_modules(points):
    """按固定尺寸切分点云，生成模块列表，每个模块包含三个机械臂基座坐标"""
    min_x, max_x = np.min(points[:,0]), np.max(points[:,0])
    min_y, max_y = np.min(points[:,1]), np.max(points[:,1])

    base_x = np.floor(min_x / MODULE_SIZE_X) * MODULE_SIZE_X
    base_y = np.floor(min_y / MODULE_SIZE_Y) * MODULE_SIZE_Y

    nx = max(1, int(np.ceil((max_x - base_x) / MODULE_SIZE_X)))
    ny = max(1, int(np.ceil((max_y - base_y) / MODULE_SIZE_Y)))
    modules = []
    for i in range(nx):
        for j in range(ny):
            x0 = base_x + i * MODULE_SIZE_X
            y0 = base_y + j * MODULE_SIZE_Y
            mask = (points[:,0] >= x0) & (points[:,0] < x0 + MODULE_SIZE_X) & \
                   (points[:,1] >= y0) & (points[:,1] < y0 + MODULE_SIZE_Y)
            seg = points[mask]
            if len(seg) == 0:
                continue

            arm_x = x0 + 5
            arm_y1 = y0 + 5
            arm_y2 = y0 + 15
            arm_y3 = y0 + 25
            module_id = (i + 1) * 16 + (j + 1)

            modules.append({
                "module_id": module_id,
                "points": seg.tolist(),
                "arms": [[arm_x, arm_y1, 0], [arm_x, arm_y2, 0], [arm_x, arm_y3, 0]]
            })
    return modules


# ===================== 发布模块任务 =====================
def publish_all_modules(modules):
    """将模块数据发布到 /module_arm_task，供节点A使用"""
    global module_pub
    if module_pub is None:
        module_pub = rospy.Publisher(TOPIC_MODULE_ARM_TASK, String, queue_size=10)
    msg = String()
    msg.data = json.dumps(modules)
    module_pub.publish(msg)
    rospy.loginfo(f"📤 已发送 {len(modules)} 个模块")


# ===================== 主回调：接收路径或点云 =====================
def json_callback(msg):
    """接收前端发来的文件路径或直接点云，完成整个处理流水线"""
    try:
        json_data = json.loads(msg.data)
        file_path = json_data.get("file_path")
        if file_path:
            # 从图纸文件读取点云
            rospy.loginfo(f"📂 收到图纸路径: {file_path}")
            if not os.path.exists(file_path):
                rospy.logerr(f"❌ 图纸文件不存在: {file_path}")
                return
            with open(file_path, 'r', encoding='utf-8') as f:
                drawing_json = json.load(f)
            parts = drawing_json.get("虚拟部件列表", [])
            points_list = []
            for part in parts:
                for coord in part.get("坐标列表", []):
                    x = coord.get("全局X(mm)", 0)
                    y = coord.get("全局Y(mm)", 0)
                    z = coord.get("全局Z(mm)", 0)
                    points_list.append([x, y, z])
            if not points_list:
                rospy.logerr("❌ JSON文件中没有找到坐标数据")
                return
            point_cloud = np.array(points_list, dtype=np.float64) / 10.0
            pcd = o3d.geometry.PointCloud()
            pcd.points = o3d.utility.Vector3dVector(point_cloud)
        elif "points" in json_data:
            # 直接使用消息中的点云
            point_cloud = np.array(json_data["points"], dtype=np.float64) / 10.0
            pcd = o3d.geometry.PointCloud()
            pcd.points = o3d.utility.Vector3dVector(point_cloud)
        else:
            rospy.logerr("缺少 points 或 file_path 字段")
            return

        if len(pcd.points) == 0:
            rospy.logerr("❌ 点云为空")
            return

        # 统计滤波去噪
        cl, ind = pcd.remove_statistical_outlier(nb_neighbors=50, std_ratio=2.0)
        pcd = pcd.select_by_index(ind)
        rospy.loginfo(f"🧹 统计滤波后保留 {len(pcd.points)} 个点")

        # PCA 摆正
        pcd = align_max_face_down(pcd)
        rospy.loginfo("🔽 最大面已朝下，长轴→Y，次长→X")

        # 移动至工作原点
        points = np.asarray(pcd.points)
        points = move_to_origin(points)
        pcd.points = o3d.utility.Vector3dVector(points)

        # 切分模块并发布
        modules = split_into_modules(points)
        rospy.loginfo(f"📦 已切割出 {len(modules)} 个模块")
        publish_all_modules(modules)

        # 存入数据库
        save_modules_to_database(modules)

        # 保存点云文件
        o3d.io.write_point_cloud(os.path.join(output_dir, "pointcloud.pcd"), pcd)
        rospy.loginfo("💾 已保存处理后的点云文件")

        # 生成三视图
        vis = o3d.visualization.Visualizer()
        vis.create_window(visible=False, width=1600, height=1000)
        vis.add_geometry(pcd)
        ctr = vis.get_view_control()
        center = np.mean(points, axis=0)
        zoom = 0.4
        ctr.set_lookat(center); ctr.set_front([0,0,-1]); ctr.set_up([0,1,0])
        ctr.set_zoom(zoom); vis.poll_events(); vis.update_renderer()
        vis.capture_screen_image(os.path.join(output_dir, "top.png"))
        ctr.set_lookat(center); ctr.set_front([0,-1,0]); ctr.set_up([0,0,1])
        vis.poll_events(); vis.update_renderer()
        vis.capture_screen_image(os.path.join(output_dir, "front.png"))
        ctr.set_lookat(center); ctr.set_front([-1,0,0]); ctr.set_up([0,1,0])
        vis.poll_events(); vis.update_renderer()
        vis.capture_screen_image(os.path.join(output_dir, "side.png"))
        vis.destroy_window()
        rospy.loginfo("🖼️ 已生成三视图")
    except Exception as e:
        rospy.logerr(f"❌ 处理失败: {e}")
        import traceback
        traceback.print_exc()


# ===================== Flask 服务 =====================
@app.route('/get_view/<view_name>')
def get_view(view_name):
    img_path = os.path.join(output_dir, f"{view_name}.png")
    if os.path.exists(img_path):
        return send_file(img_path, mimetype='image/png')
    return "图片不存在", 404


def run_flask():
    app.run(host='0.0.0.0', port=5000, debug=False)


# ===================== 主程序 =====================
def main():
    global module_pub
    load_env_config()          # 加载 .env 到环境变量
    update_params_from_env()   # 强制更新全局参数，缺失则异常
    rospy.init_node('pointcloud_processor_node')

    init_database()

    # 订阅前端输入话题（必须已在 .env 中定义）
    rospy.Subscriber(TOPIC_FRONTEND_INPUT, String, json_callback)
    module_pub = rospy.Publisher(TOPIC_MODULE_ARM_TASK, String, queue_size=10)
    rospy.loginfo("🚀 ROS点云处理节点已启动（强制从 .env 加载配置，无默认值）")
    rospy.loginfo(f"🗄️ 共享数据库: {os.path.abspath(DB_FILE)}")

    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    rospy.loginfo("🌐 Flask服务运行在 5000 端口")
    rospy.spin()


if __name__ == '__main__':
    main()