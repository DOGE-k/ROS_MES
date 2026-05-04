#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import websockets
import json
import rospy
import threading
from robot_control_backend.msg import RotationCmd, SwingCmd, TelescopicCmd
from robot_control_backend.msg import Feedback, Kinematics,IntCmd

# ======================= 全局变量 =======================
# 保存所有连接的 WebSocket 客户端（前端/Java）
connected_clients = set()
# asyncio 事件循环（跨线程安全调用）
loop = None
# 多线程锁，防止同时修改客户端列表导致崩溃
lock = threading.Lock()

# ROS 发布者（全部正确初始化）
kinematics_pose_pub = None        # 发布坐标指令（x,y,z）
adjust_rot_pub = None             # 发布旋转轴微调指令
adjust_swing_pub = None           # 发布摆动轴微调指令
adjust_telescopic_pub = None      # 发布伸缩轴微调指令
module_cofirme_pub = None         # 发布模块确认指令
telescope_feedback_pub = None     # 伸缩轴反馈发布


# ======================= ROS 反馈回调 =======================
# 功能：接收硬件/轴反馈 → 打包成 JSON → 推送给前端
def ros_feedback_callback(msg):
    global loop, telescope_feedback_pub
    rospy.logdebug(f"[回调收到] device_id={msg.device_id}, position={msg.position}")

    # ----------------------
    # 1. 轴编码器 33/34/35
    # ----------------------
    if msg.device_id in [33, 34, 35]:
        feedback_data = {
            "time_id": rospy.get_time(),
            "header": {
                "secs": msg.header.stamp.secs,
                "nsecs": msg.header.stamp.nsecs
            },
            "module_id": msg.module_id,
            "device_id": msg.device_id,
            "position": msg.position,
            "data_type": "axis_encoder"
        }
    # ----------------------
    # 2. 压力传感器 49
    # ----------------------
    elif msg.device_id == 49:
        feedback_data = {
            "time_id": rospy.get_time(),
            "id": msg.id,
            "header": {
                "secs": msg.header.stamp.secs,
                "nsecs": msg.header.stamp.nsecs
            },
            "module_id": msg.module_id,
            "device_id": msg.device_id,
            "position": msg.position,
            "data_type": "pressure_sensor"
        }
    # ----------------------
    # 3. 未知设备
    # ----------------------
    else:
        feedback_data = {
            "time_id": rospy.get_time(),
            "module_id": msg.module_id,
            "device_id": msg.device_id,
            "position": msg.position,
            "data_type": "unknown"
        }

    # ----------------------
    # 给前端标注反馈类型（便于调试）
    # ----------------------
    if msg.device_id == 33:
        feedback_data["feedback_type"] = "旋转轴编码器"
    elif msg.device_id == 34:
        feedback_data["feedback_type"] = "摆动轴编码器"
    elif msg.device_id == 35:
        feedback_data["feedback_type"] = "伸长轴编码器"
        # 额外转发伸缩轴反馈
        if telescope_feedback_pub:
            telescope_feedback_pub.publish(msg)
    elif msg.device_id == 49:
        feedback_data["feedback_type"] = "压力传感器"

    # 转 JSON
    json_feedback = json.dumps(feedback_data)
    rospy.logdebug(f"[发送前端] {json_feedback}")

    # 跨线程安全发送给所有 WebSocket 客户端
    if loop and not loop.is_closed():
        loop.call_soon_threadsafe(
            asyncio.create_task,
            send_to_all_clients(json_feedback)
        )


# ======================= 广播给前端 =======================
async def send_to_all_clients(json_data):
    # 加锁复制客户端列表，防止遍历时被修改
    with lock:
        clients_to_send = list(connected_clients)

    # 给每个客户端发消息
    for ws in clients_to_send:
        try:
            await ws.send(json_data)
        except:
            # 发送失败 → 移除断开的客户端
            with lock:
                if ws in connected_clients:
                    connected_clients.remove(ws)
                    rospy.logwarn("⚠️  客户端已断开，已移除")


# ======================= 处理 Java 指令 =======================
# 功能：接收前端/Java WebSocket 指令 → 解析 → 转发 ROS
async def handle_java(websocket):
    rospy.loginfo("✅ Java 已连接")
    with lock:
        connected_clients.add(websocket)

    try:
        # 持续监听前端消息
        async for msg in websocket:
            try:
                rospy.logdebug(f"[收到前端指令] {msg}")
                cmd_data = json.loads(msg)

                # 提取指令关键字段
                device_id = cmd_data.get("device_id")
                position = cmd_data.get("position", [])
                module_id = cmd_data.get("module_id", 17)

                rospy.loginfo(f"📥 解析指令：device_id={device_id}, pos={position}")

                # ----------------------
                # device_id == 0 → 模块确认
                # ----------------------
                if device_id == 0:
                    module_cmd = IntCmd()
                    module_cmd.header = rospy.Header()
                    module_cmd.module_id = module_id
                    module_cmd.device_id = 0
                    module_cmd.position = [100]
                    module_cofirme_pub.publish(module_cmd)
                    rospy.loginfo(f"📤 模块确认指令 → /control/module_cmd")

                # ----------------------
                # device_id == 1 → 坐标指令（逆运动学）
                # ----------------------
                elif device_id == 1:
                    kinematics_cmd = Kinematics()
                    kinematics_cmd.header = rospy.Header()
                    kinematics_cmd.module_id = module_id
                    kinematics_cmd.device_id = 0
                    kinematics_cmd.position = position
                    kinematics_pose_pub.publish(kinematics_cmd)
                    rospy.loginfo(f"📤 坐标指令 {position} → /control/kinematics_pose")

                # ----------------------
                # device_id == 33 → 旋转轴微调
                # ----------------------
                elif device_id == 33:
                    rot_cmd = RotationCmd()
                    rot_cmd.header = rospy.Header()
                    rot_cmd.module_id = module_id
                    rot_cmd.device_id = 33
                    rot_cmd.position = position
                    adjust_rot_pub.publish(rot_cmd)
                    rospy.loginfo(f"📤 旋转轴 {position} → /control/adjust_rotation_cmd")

                # ----------------------
                # device_id == 34 → 摆动轴微调
                # ----------------------
                elif device_id == 34:
                    swing_cmd = SwingCmd()
                    swing_cmd.header = rospy.Header()
                    swing_cmd.module_id = module_id
                    swing_cmd.device_id = 34
                    swing_cmd.position = position
                    adjust_swing_pub.publish(swing_cmd)
                    rospy.loginfo(f"📤 摆动轴 {position} → /control/adjust_swing_cmd")

                # ----------------------
                # device_id == 35 → 伸缩轴微调
                # ----------------------
                elif device_id == 35:
                    tel_cmd = TelescopicCmd()
                    tel_cmd.header = rospy.Header()
                    tel_cmd.module_id = module_id
                    tel_cmd.device_id = 35
                    tel_cmd.position = position
                    adjust_telescopic_pub.publish(tel_cmd)
                    rospy.loginfo(f"📤 伸缩轴 {position} → /control/adjust_telescopic_cmd")

                # ----------------------
                # 不支持的 device_id
                # ----------------------
                else:
                    rospy.logwarn(f"⚠️ 无效 device_id={device_id}，支持：0,1,33,34,35")

            except json.JSONDecodeError:
                rospy.logerr("❌ JSON 解析失败：格式错误")
            except Exception as e:
                rospy.logerr(f"❌ 指令处理错误: {str(e)}")

    finally:
        # 断开连接时清理
        with lock:
            if websocket in connected_clients:
                connected_clients.remove(websocket)
        rospy.loginfo("❌ Java 断开连接")


# ======================= ROS 线程 =======================
# 单独线程运行 ROS，不阻塞 WebSocket
def ros_spin_thread():
    rospy.spin()


# ======================= 主函数 =======================
async def main():
    global loop
    global kinematics_pose_pub, adjust_rot_pub, adjust_swing_pub, adjust_telescopic_pub
    global module_cofirme_pub, telescope_feedback_pub

    loop = asyncio.get_running_loop()
    rospy.init_node("web_data_node")
    rospy.loginfo("=" * 60)
    rospy.loginfo("✅ web_data_node 启动（带完整调试注释）")
    rospy.loginfo("=" * 60)


    # =======================
    # ROS 发布者初始化
    # =======================
    module_cofirme_pub = rospy.Publisher("/control/module_cmd", IntCmd, queue_size=10)
    kinematics_pose_pub = rospy.Publisher("/control/kinematics_pose", Kinematics, queue_size=10)
    adjust_rot_pub = rospy.Publisher("/control/adjust_rotation_cmd", RotationCmd, queue_size=10)
    adjust_swing_pub = rospy.Publisher("/control/adjust_swing_cmd", SwingCmd, queue_size=10)
    adjust_telescopic_pub = rospy.Publisher("/control/adjust_telescopic_cmd", TelescopicCmd, queue_size=10)
    telescope_feedback_pub = rospy.Publisher("/hardware/telescope_feedback", Feedback, queue_size=10)

    # =======================
    # ROS 订阅者（所有反馈）
    # =======================
    rospy.Subscriber("/hardware/rotation_feedback", Feedback, ros_feedback_callback)
    rospy.Subscriber("/hardware/swing_feedback", Feedback, ros_feedback_callback)
    rospy.Subscriber("/hardware/telescope_feedback", Feedback, ros_feedback_callback)
    rospy.Subscriber("/hardware/sensor_feedback", Feedback, ros_feedback_callback)

    rospy.loginfo("✅ ROS 发布/订阅 初始化完成")

    # 启动 ROS 独立线程
    threading.Thread(target=ros_spin_thread, daemon=True).start()

    # 启动 WebSocket 服务（端口 8760）
    server = await websockets.serve(handle_java, "0.0.0.0", 8760)
    rospy.loginfo("🚀 WebSocket 服务已启动：ws://0.0.0.0:8760")
    await server.wait_closed()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        rospy.logerr(f"❌ 异常退出: {str(e)}")
    finally:
        if not rospy.is_shutdown():
            rospy.signal_shutdown("exit")