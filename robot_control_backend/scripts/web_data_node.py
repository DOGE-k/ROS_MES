#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import websockets
import json
import rospy
import threading
from robot_control_backend.msg import RotationCmd, SwingCmd, TelescopicCmd
from robot_control_backend.msg import Feedback, Kinematics

# ======================= 全局变量 =======================
connected_clients = set()
loop = None
lock = threading.Lock()

# ROS 发布者（全部正确初始化）
kinematics_pose_pub = None
adjust_rot_pub = None
adjust_swing_pub = None
adjust_telescopic_pub = None
module_cofirme_pub = None
telescope_feedback_pub = None  


# ======================= ROS 反馈回调 =======================
def ros_feedback_callback(msg):
    global loop, telescope_feedback_pub

    # 轴编码器（33/34/35）
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
    # 压力传感器（49）
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
    else:
        feedback_data = {
            "time_id": rospy.get_time(),
            "module_id": msg.module_id,
            "device_id": msg.device_id,
            "position": msg.position,
            "data_type": "unknown"
        }

    # 反馈类型标注
    if msg.device_id == 33:
        feedback_data["feedback_type"] = "旋转轴编码器"
    elif msg.device_id == 34:
        feedback_data["feedback_type"] = "摆动轴编码器"
    elif msg.device_id == 35:
        feedback_data["feedback_type"] = "伸长轴编码器"
        if telescope_feedback_pub:
            telescope_feedback_pub.publish(msg)
    elif msg.device_id == 49:
        feedback_data["feedback_type"] = "压力传感器"

    json_feedback = json.dumps(feedback_data)

    if loop and not loop.is_closed():
        loop.call_soon_threadsafe(
            asyncio.create_task,
            send_to_all_clients(json_feedback)
        )


# ======================= 广播给前端 =======================
async def send_to_all_clients(json_data):
    with lock:
        clients_to_send = list(connected_clients)

    for ws in clients_to_send:
        try:
            await ws.send(json_data)
        except:
            with lock:
                if ws in connected_clients:
                    connected_clients.remove(ws)


# ======================= 处理 Java 指令 =======================
async def handle_java(websocket):
    rospy.loginfo("✅ Java 已连接")
    with lock:
        connected_clients.add(websocket)

    try:
        async for msg in websocket:
            try:
                cmd_data = json.loads(msg)
                device_id = cmd_data.get("device_id")
                position = cmd_data.get("position", [])
                module_id = cmd_data.get("module_id", 17)

                if device_id == 0:
                    kinematics_cmd = Kinematics()
                    kinematics_cmd.header = rospy.Header()
                    kinematics_cmd.module_id = module_id
                    kinematics_cmd.device_id = 0
                    kinematics_cmd.position = [0, 0]
                    module_cofirme_pub.publish(kinematics_cmd)
                    rospy.loginfo(f"📤 模块确认指令 module_id={module_id} → /control/module_cmd")

                elif device_id == 1:
                    kinematics_cmd = Kinematics()
                    kinematics_cmd.header = rospy.Header()
                    kinematics_cmd.module_id = module_id
                    kinematics_cmd.device_id = 0
                    kinematics_cmd.position = position
                    kinematics_pose_pub.publish(kinematics_cmd)
                    rospy.loginfo(f"📤 坐标指令 {position} → /control/kinematics_pose")

                elif device_id == 33:
                    rot_cmd = RotationCmd()
                    rot_cmd.header = rospy.Header()
                    rot_cmd.module_id = module_id
                    rot_cmd.device_id = 33
                    rot_cmd.position = position
                    adjust_rot_pub.publish(rot_cmd)
                    rospy.loginfo(f"📤 旋转轴 {position} → /control/adjust_rotation_cmd")

                elif device_id == 34:
                    swing_cmd = SwingCmd()
                    swing_cmd.header = rospy.Header()
                    swing_cmd.module_id = module_id
                    swing_cmd.device_id = 34
                    swing_cmd.position = position
                    adjust_swing_pub.publish(swing_cmd)
                    rospy.loginfo(f"📤 摆动轴 {position} → /control/adjust_swing_cmd")

                elif device_id == 35:
                    tel_cmd = TelescopicCmd()
                    tel_cmd.header = rospy.Header()
                    tel_cmd.module_id = module_id
                    tel_cmd.device_id = 35
                    tel_cmd.position = position
                    adjust_telescopic_pub.publish(tel_cmd)
                    rospy.loginfo(f"📤 伸缩轴 {position} → /control/adjust_telescopic_cmd")

                else:
                    rospy.logwarn(f"⚠️ 无效 device_id={device_id}，支持：0,1,33,34,35")

            except json.JSONDecodeError:
                rospy.logerr("❌ JSON 解析失败")
            except Exception as e:
                rospy.logerr(f"❌ 指令处理错误: {str(e)}")

    finally:
        with lock:
            if websocket in connected_clients:
                connected_clients.remove(websocket)
        rospy.loginfo("❌ Java 断开连接")


# ======================= ROS 线程 =======================
def ros_spin_thread():
    rospy.spin()


# ======================= 主函数 =======================
async def main():
    global loop
    global kinematics_pose_pub, adjust_rot_pub, adjust_swing_pub, adjust_telescopic_pub
    global module_cofirme_pub, telescope_feedback_pub

    loop = asyncio.get_running_loop()
    rospy.init_node("web_data_node")
    rospy.loginfo("✅ web_data_node 启动")

    # 发布者（全部正确初始化）
    module_cofirme_pub = rospy.Publisher("/control/module_cmd", Kinematics, queue_size=10)
    kinematics_pose_pub = rospy.Publisher("/control/kinematics_pose", Kinematics, queue_size=10)
    adjust_rot_pub = rospy.Publisher("/control/adjust_rotation_cmd", RotationCmd, queue_size=10)
    adjust_swing_pub = rospy.Publisher("/control/adjust_swing_cmd", SwingCmd, queue_size=10)
    adjust_telescopic_pub = rospy.Publisher("/control/adjust_telescopic_cmd", TelescopicCmd, queue_size=10)
    
    telescope_feedback_pub = rospy.Publisher("/hardware/telescope_feedback", Feedback, queue_size=10)

    # 订阅反馈
    rospy.Subscriber("/hardware/rotation_feedback", Feedback, ros_feedback_callback)
    rospy.Subscriber("/hardware/swing_feedback", Feedback, ros_feedback_callback)
    rospy.Subscriber("/hardware/telescope_feedback", Feedback, ros_feedback_callback)
    rospy.Subscriber("/hardware/sensor_feedback", Feedback, ros_feedback_callback)

    # ROS 线程
    threading.Thread(target=ros_spin_thread, daemon=True).start()

    # WebSocket
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