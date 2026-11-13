# app/ros/base.py
"""ROS 适配层统一接口与版本无关的共用实现。

业务端点只依赖 `RosDispatcher` 接口，不感知 ROS1/ROS2 差异；
当前激活的适配器由 `app.ros.get_ros_dispatcher()` 工厂提供。
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict

from app.ros.profile import RosProfile


class RosbridgeError(RuntimeError):
    """rosbridge 通信失败（连接、超时、确认失败等）。"""


class RosDispatchError(Exception):
    """原生 ROS 通道（rospy）下发失败或不可用。"""


# 子进程执行 ROS 脚本用的解释器；
# Linux 环境通常没有 python 别名，默认使用当前后端解释器，可用 ROS_PYTHON_CMD 覆盖
PYTHON_CMD = os.environ.get("ROS_PYTHON_CMD", sys.executable)


class RosDispatcher(ABC):
    """ROS 适配器接口。

    必须实现：rosbridge 一次性下发、反馈流、急停。
    原生节点通道（/web_cmd）只有 ROS1 适配器提供，基类默认"不可用"。
    """

    profile: RosProfile

    # ---- rosbridge 通道 ----
    @abstractmethod
    def dispatch(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """一次性下发指令（fine_tuning / drawing_path / module_confirm）。

        module_confirm 会同步等待 ROS 端确认后才返回。
        """

    @abstractmethod
    def stream_feedback(self) -> AsyncIterator[Dict[str, Any]]:
        """订阅 /hardware/* 反馈话题，逐条产出归一化后的消息。"""

    @abstractmethod
    async def trigger_emergency_stop(self) -> bool:
        """全局急停（/control/softstop，系统级 module_id=0 / device_id=0）。"""

    @abstractmethod
    async def release_emergency_stop(self) -> bool:
        """急停解除（/control/softstop_release，softstop_node 转发 /arm/cmd_vel [0x04]）。"""

    async def trigger_local_stop(self, *, scope: str, module_id: int,
                                 device_id: int | None = None) -> bool:
        """局部停（模块停 / 单轴停）；不支持的适配器默认拒绝，不静默降级为全局急停。"""
        raise RosDispatchError("当前 ROS 适配层不支持局部停")

    # ---- 原生节点通道（ROS1 专属，默认不可用） ----
    def start_native_node(self) -> None:
        """启动后台通道（rospy 线程 / rosbridge 状态订阅）；无后台通道的适配器默认不启动。"""
        return None

    def stop(self) -> None:
        """结束后台连接（应用关闭时调用）；无后台通道的适配器默认无操作。"""
        return None

    def publish_web_cmd(self, command: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        raise RosDispatchError("当前 ROS 适配层没有原生 ROS 通道（/web_cmd）")

    @property
    def native_status(self) -> Dict[str, Any]:
        return {
            "robot_status": "unknown",
            "battery": 85,
            "node": "ros_mes_api_server",
            "ros_ready": False,
        }

    # ---- ROS 脚本子进程工具（ROS1/ROS2 通用，脚本目录取自 profile） ----
    async def get_hardware_status(self) -> dict:
        """拉起 hardware_node 脚本获取底层硬件状态，5 秒超时强杀防止 Web 接口卡死。"""
        script_path = os.path.join(self.profile.scripts_dir, "hardware_node.py")
        if not os.path.exists(script_path):
            return {"error": "系统找不到指定的 ROS 脚本", "path": script_path}

        try:
            process = await asyncio.create_subprocess_exec(
                PYTHON_CMD, script_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=5.0)
        except asyncio.TimeoutError:
            process.kill()
            return {"error": "Timeout", "details": "hardware_node.py 执行超时，已被系统强制中断。"}
        except Exception as exc:
            return {"error": "未知系统错误", "details": str(exc)}

        if process.returncode == 0:
            output = stdout.decode().strip()
            try:
                return json.loads(output)
            except json.JSONDecodeError:
                return {"status": "success", "raw_data": output}
        return {"error": "ROS 脚本执行失败", "details": stderr.decode().strip()}

    async def test_serial_connection(self) -> dict:
        """拉起 serial_test_node 脚本做串口连通性测试，10 秒超时。"""
        script_path = os.path.join(self.profile.scripts_dir, "serial_test_node.py")
        if not os.path.exists(script_path):
            return {"success": False, "message": "找不到串口测试脚本", "path": script_path}

        try:
            process = await asyncio.create_subprocess_exec(
                PYTHON_CMD, script_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except Exception as exc:
            return {"success": False, "message": f"系统错误: {str(exc)}"}

        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10.0)
        except asyncio.TimeoutError:
            process.kill()
            return {"success": False, "message": "串口测试执行超时，请检查串口连接"}

        if process.returncode == 0:
            output = stdout.decode().strip()
            try:
                return json.loads(output)
            except json.JSONDecodeError:
                return {"success": True, "message": "串口连接正常", "raw": output}
        return {"success": False, "message": f"测试脚本执行失败: {stderr.decode().strip()}"}

    async def stream_robot_data(self) -> AsyncIterator[str]:
        """拉起 web_data_node 脚本并逐行转发其 stdout（大屏实时数据流）。

        WebSocket 断开时 FastAPI 会取消本任务，在 CancelledError 中
        终止底层进程，防止僵尸进程占用机器资源。
        """
        script_path = os.path.join(self.profile.scripts_dir, "web_data_node.py")
        try:
            process = await asyncio.create_subprocess_exec(
                PYTHON_CMD, "-u", script_path,  # -u 关闭输出缓存，保证实时行输出
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            print(f"底层 ROS 数据节点 ({script_path}) 已成功唤醒，正在监听数据...")

            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                decoded_line = line.decode("utf-8").strip()
                if decoded_line:
                    yield decoded_line
        except asyncio.CancelledError:
            print("停止底层 ROS 数据流采集...")
            process.terminate()
            raise
        except Exception as exc:
            print(f"启动 ROS 节点失败: {exc}")
