#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import rospy
import json
import numpy as np
import open3d as o3d
from std_msgs.msg import String
from flask import Flask, send_file
import threading
import os

app = Flask(__name__)
point_cloud_data = None
output_dir = "/tmp/ros_pointcloud_output/"

if not os.path.exists(output_dir):
    os.makedirs(output_dir)
    rospy.loginfo(f"📂 已创建输出目录: {output_dir}")

# ===================== 参数 =====================
MODULE_ORIGIN_X = 0.0          # cm，模块原点 X
MODULE_ORIGIN_Y = 0.0          # cm，模块原点 Y
MODULE_ORIGIN_Z = 0.0          # cm，模块原点 Z

FIRST_ARM = np.array([5, 5, 0])
ARM_STEP = 10
MODULE_SIZE_X = 10
MODULE_SIZE_Y = 30
ARM_MIN_HEIGHT = 10.0
ARM_SAFE_GAP = 1.0

module_pub = None

# ===================== 摆正函数 =====================
def align_max_face_down(pcd):
    pts = np.asarray(pcd.points)
    center = np.mean(pts, axis=0)
    cov = np.cov((pts - center).T)
    eigvals, eigvecs = np.linalg.eigh(cov)

    v_short = eigvecs[:, 0]
    v_mid   = eigvecs[:, 1]
    v_long  = eigvecs[:, 2]

    target_z_down = np.array([0, 0, -1])
    if np.dot(v_short, target_z_down) < 0:
        v_short = -v_short

    R = np.array([
        v_mid,
        v_long,
        -v_short
    ])

    if np.linalg.det(R) < 0:
        R[1, :] *= -1

    pcd_rotated = o3d.geometry.PointCloud(pcd)
    pcd_rotated.rotate(R, center=center)
    return pcd_rotated

# ===================== 移动至工作原点 =====================
def move_to_origin(points):
    min_x = np.min(points[:, 0])
    max_x = np.max(points[:, 0])
    min_y = np.min(points[:, 1])
    max_y = np.max(points[:, 1])
    min_z = np.min(points[:, 2])

    MODULE_X = 10.0
    MODULE_Y = 30.0
    SAFE_LIMIT_X = 15.0
    SAFE_LIMIT_Y = 35.0

    obj_w_x = max_x - min_x
    obj_h_y = max_y - min_y

    if obj_w_x <= SAFE_LIMIT_X:
        cx = (min_x + max_x) / 2.0
        target_cx = MODULE_ORIGIN_X + MODULE_X / 2.0
        points[:, 0] += (target_cx - cx)
        rospy.loginfo(f"✅ X向小工件居中 宽度:{obj_w_x:.2f}cm")
    else:
        points[:, 0] += (MODULE_ORIGIN_X - min_x)

    if obj_h_y <= SAFE_LIMIT_Y:
        cy = (min_y + max_y) / 2.0
        target_cy = MODULE_ORIGIN_Y + MODULE_Y / 2.0
        points[:, 1] += (target_cy - cy)
        rospy.loginfo(f"✅ Y向小工件居中 高度:{obj_h_y:.2f}cm")
    else:
        points[:, 1] += (MODULE_ORIGIN_Y - min_y)

    target_z = MODULE_ORIGIN_Z + ARM_MIN_HEIGHT + ARM_SAFE_GAP
    dz = target_z - min_z
    points[:, 2] += dz
    rospy.loginfo(f"📍 点云已移动：最低 Z {min_z:.2f} → {target_z:.1f} cm")
    return points

# ===================== 切分为模块（最优全覆盖 + 新编号） =====================
def split_into_modules(points):
    min_x = np.min(points[:, 0])
    max_x = np.max(points[:, 0])
    min_y = np.min(points[:, 1])
    max_y = np.max(points[:, 1])

    base_x = np.floor(min_x / MODULE_SIZE_X) * MODULE_SIZE_X
    base_y = np.floor(min_y / MODULE_SIZE_Y) * MODULE_SIZE_Y

    nx = max(1, int(np.ceil((max_x - base_x) / MODULE_SIZE_X)))
    ny = max(1, int(np.ceil((max_y - base_y) / MODULE_SIZE_Y)))
    modules = []
    for i in range(nx):
        for j in range(ny):
            x0 = base_x + i * MODULE_SIZE_X
            x1 = x0 + MODULE_SIZE_X
            y0 = base_y + j * MODULE_SIZE_Y
            y1 = y0 + MODULE_SIZE_Y
            mask = (points[:, 0] >= x0) & (points[:, 0] < x1) & \
                   (points[:, 1] >= y0) & (points[:, 1] < y1)
            seg = points[mask]
            if len(seg) == 0:
                continue

            arm_x = x0 + 5
            arm_y1 = y0 + 5
            arm_y2 = y0 + 15
            arm_y3 = y0 + 25

            # ★ 新编号规则：module_id = (i+1)*16 + (j+1)  十进制
            module_id = (i + 1) * 16 + (j + 1)

            modules.append({
                "module_id": module_id,          # 数字类型，json中为数值
                "points": seg.tolist(),
                "arms": [[arm_x, arm_y1, 0], [arm_x, arm_y2, 0], [arm_x, arm_y3, 0]]
            })
    return modules

# ===================== 发布模块 =====================
def publish_all_modules(modules):
    global module_pub
    if module_pub is None:
        module_pub = rospy.Publisher('/module_arm_task', String, queue_size=10)
    msg = String()
    msg.data = json.dumps(modules)
    module_pub.publish(msg)
    rospy.loginfo(f"📤 已发送 {len(modules)} 个模块")

# ===================== JSON 回调处理 =====================
def json_callback(msg):
    global point_cloud_data
    try:
        json_data = json.loads(msg.data)
        if "points" not in json_data:
            rospy.logerr("缺少 points 字段")
            return

        point_cloud_data = np.array(json_data["points"], dtype=np.float64)
        point_cloud_data /= 10.0

        rospy.loginfo(f"✅ 成功解析点云，共 {len(point_cloud_data)} 个点 (已转为 cm)")

        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(point_cloud_data)

        cl, ind = pcd.remove_statistical_outlier(nb_neighbors=50, std_ratio=2.0)
        pcd = pcd.select_by_index(ind)
        rospy.loginfo(f"🧹 统计滤波后保留 {len(pcd.points)} 个点")

        pcd = align_max_face_down(pcd)
        rospy.loginfo("🔽 最大面已朝下，长轴→Y，次长→X")

        points = np.asarray(pcd.points)
        points = move_to_origin(points)
        pcd.points = o3d.utility.Vector3dVector(points)

        modules = split_into_modules(points)
        rospy.loginfo(f"📦 已切割出 {len(modules)} 个模块")

        publish_all_modules(modules)

        o3d.io.write_point_cloud(os.path.join(output_dir, "pointcloud.pcd"), pcd)
        rospy.loginfo("💾 已保存处理后的点云文件")

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

# ===================== Flask =====================
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
    rospy.init_node('pointcloud_processor_node')
    rospy.Subscriber('frontend_pointcloud_topic', String, json_callback)
    rospy.loginfo("🚀 ROS点云处理节点已启动（PCA摆正 + 统计滤波 + 智能全覆盖切块 + 十六进制编号）")

    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    rospy.loginfo("🌐 Flask服务运行在 5000 端口")

    rospy.spin()

if __name__ == '__main__':
    main()
