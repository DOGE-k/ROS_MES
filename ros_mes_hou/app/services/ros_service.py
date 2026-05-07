# app/services/ros_service.py

import json
import threading
from typing import Any, Dict, Optional


try:
    import rospy
    from std_msgs.msg import String
except Exception as exc:
    rospy = None
    String = None
    ROS_IMPORT_ERROR = exc
else:
    ROS_IMPORT_ERROR = None


class RosDispatchError(Exception):
    pass


pub: Optional["rospy.Publisher"] = None
ros_ready = False
ros_thread_started = False

latest_status = {
    "robot_status": "unknown",
    "battery": 85,
    "node": "ros_mes_api_server",
}


def _json_dumps(data: Dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False)


def publish_ros_command(command: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    FastAPI 接口调用这个函数，把前端请求统一发布到 ROS topic。
    """
    if rospy is None or String is None:
        raise RosDispatchError(f"rospy 未加载，请确认在 ROS 环境运行。错误：{ROS_IMPORT_ERROR}")

    if not ros_ready or pub is None:
        raise RosDispatchError("ROS 节点尚未初始化完成")

    ros_message = {
        "command": command,
        "payload": payload,
    }

    pub.publish(String(data=_json_dumps(ros_message)))

    return {
        "topic": "/web_cmd",
        "command": command,
        "payload": payload,
    }


def status_callback(msg: "String"):
    """
    可选：订阅 ROS 状态。
    如果 /robot_status 发的是普通字符串，就存字符串；
    如果发的是 JSON 字符串，就尝试解析。
    """
    raw = msg.data

    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            latest_status.update(data)
            return
    except Exception:
        pass

    latest_status["robot_status"] = raw


def ros_node():
    global pub, ros_ready

    if rospy is None or String is None:
        print(f"❌ rospy 加载失败：{ROS_IMPORT_ERROR}")
        return

    rospy.init_node(
        "ros_mes_api_server",
        anonymous=False,
        disable_signals=True,
    )

    pub = rospy.Publisher("/web_cmd", String, queue_size=10)

    # ROS 同学后面如果有状态 topic，就往 /robot_status 发 std_msgs/String
    rospy.Subscriber("/robot_status", String, status_callback)

    ros_ready = True
    rospy.loginfo("✅ ROS MES API 节点启动成功，发布 topic: /web_cmd")

    rospy.spin()


def start_ros_thread():
    """
    给 main.py 调用。
    FastAPI 启动时开线程跑 ROS，避免 rospy.spin() 阻塞 HTTP 服务。
    """
    global ros_thread_started

    if ros_thread_started:
        return

    ros_thread_started = True

    thread = threading.Thread(target=ros_node, daemon=True)
    thread.start()