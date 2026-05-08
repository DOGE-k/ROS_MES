# app/services/ros_control.py
import os
import json
import asyncio
import traceback # 用于打印更详细的错误
import sys

try:
    import websockets
except ImportError:
    websockets = None

# ==========================================
# 1. 黑魔法：路径自动寻址 (绝对路径)
# ==========================================
# 获取当前文件 (ros_control.py) 的绝对目录
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# 向上推 3 层，到达项目根目录 (即包含 ros_mes_hou 和 robot_control_backend 的文件夹)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "../../../"))

# 精准锁定 ROS 脚本存放位置
SCRIPTS_DIR = os.path.join(PROJECT_ROOT, "robot_control_backend", "scripts")

# 你的执行环境（如果你在 venv 里无法运行 ROS 库，可将此改为 "/usr/bin/python3" 或具体的 conda/ros 环境路径）
PYTHON_CMD = "python"

# WebSocket 地址（web_data_node 的 rosbridge 桥接端口）
WEBSOCKET_URI = "ws://localhost:8760"


async def get_hardware_status() -> dict:
    """
    无痛调用 hardware_node.py (获取硬件状态)
    特性：防阻塞保护 + 自动数据格式化
    """
    script_path = os.path.join(SCRIPTS_DIR, "hardware_node.py")

    # 1. 拦截：如果路径错误直接报错，不让进程空跑
    if not os.path.exists(script_path):
        return {"error": "系统找不到指定的 ROS 脚本", "path": script_path}

    try:
        # 2. 异步拉起底层脚本
        process = await asyncio.create_subprocess_exec(
            PYTHON_CMD, script_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # 3. 护城河：5秒超时杀进程！
        # 很多 ROS 脚本含有 rospy.spin() 或 while True，会导致 Web 接口永久卡死。
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=5.0)

        # 4. 结果处理
        if process.returncode == 0:
            output = stdout.decode().strip()
            # 兼容处理：尝试解析为 JSON，如果原脚本只打印了普通字符串，也照单全收
            try:
                return json.loads(output)
            except json.JSONDecodeError:
                return {"status": "success", "raw_data": output}
        else:
            return {"error": "ROS 脚本执行失败", "details": stderr.decode().strip()}

    except asyncio.TimeoutError:
        process.kill() # 强制击毙超时进程
        return {"error": "Timeout", "details": "hardware_node.py 执行超时，已被系统强制中断。"}
    except Exception as e:
        return {"error": "未知系统错误", "details": str(e)}


async def trigger_emergency_stop() -> bool:
    """
    通过 WebSocket 向 web_data_node 发送 rosbridge 格式的急停指令
    data="000000" 表示急停
    """
    if websockets is None:
        print("[紧急故障] websockets 库未安装，无法发送急停指令")
        return False

    emergency_msg = json.dumps({
        "op": "publish",
        "topic": "/emergency_stop",
        "msg": {"data": "000000"}
    }, ensure_ascii=False)

    try:
        async with websockets.connect(WEBSOCKET_URI, close_timeout=1) as ws:
            await asyncio.wait_for(ws.send(emergency_msg), timeout=2.0)
        print("[急停] rosbridge 指令已发送: " + emergency_msg)
        return True
    except asyncio.TimeoutError:
        print("[紧急故障] 急停 WebSocket 发送超时")
        return False
    except Exception as e:
        print(f"[紧急故障] 急停系统异常: {e}")
        return False
    

async def stream_real_robot_data():
    """
    建立真实 ROS 数据流：
    启动底层的 web_data_node.py，并持续、异步地读取它输出的 ROS 数据
    """
    # 假设 web_data_node.py 是专门用来向 Web 提供数据的节点
    script_path = os.path.join(SCRIPTS_DIR, "web_data_node.py")
    
    # 异步启动 ROS 节点进程 (类似于 Java 的 ProcessBuilder)
    # stdbuf -oL 强制 Python 脚本的输出不走缓存，实现真正实时的行输出 (在 Linux/ROS 环境下非常有用)
    try:
        process = await asyncio.create_subprocess_exec(
            "python", "-u", script_path, # -u 参数强制 python 不使用输出缓存
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        print(f"底层 ROS 数据节点 ({script_path}) 已成功唤醒，正在监听数据...")

        # 持续按行读取底层脚本的输出
        while True:
            line = await process.stdout.readline()
            if not line:
                break # 如果节点进程意外结束，跳出循环
            
            # 解码并去除两端的空白符
            decoded_line = line.decode('utf-8').strip()
            if decoded_line:
                # 只要节点输出了数据（假设是 JSON 字符串），我们就把它作为数据流产出
                yield decoded_line
                
    except asyncio.CancelledError:
        # 当 WebSocket 意外断开时，FastAPI 会取消这个任务
        # 我们必须优雅地“杀死”底层的 ROS 进程，防止僵尸进程占用机器资源
        print("停止底层 ROS 数据流采集...")
        process.terminate()
        raise
    except Exception as e:
        print(f"启动 ROS 节点失败: {e}")