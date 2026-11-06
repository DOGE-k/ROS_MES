# app/ros/__init__.py
"""ROS 适配层入口：按 ROS_VERSION 环境变量提供当前激活的调度器。

- ROS1（默认）：app/ros/ros1/Ros1Dispatcher
- ROS2：      app/ros/ros2/Ros2Dispatcher

业务端点一律通过 get_ros_dispatcher() 取适配器，不直接 import 具体实现；
测试可用 reset_ros_dispatcher() 清缓存，或直接给端点注入 DummyDispatcher。
"""
from typing import Any, Dict

from app.ros.profile import get_active_profile

_dispatcher = None


def get_ros_dispatcher():
    """返回当前 ROS_VERSION 对应的调度器单例（懒加载，避免循环导入）。"""
    global _dispatcher
    from app.ros.runtime_settings import runtime_settings
    if _dispatcher is not None and _dispatcher.revision != runtime_settings.snapshot()["revision"]:
        _dispatcher.stop()
        _dispatcher = None
    if _dispatcher is None:
        name = get_active_profile().name
        if name == "ros1":
            from app.ros.ros1 import Ros1Dispatcher
            _dispatcher = Ros1Dispatcher()
        else:
            from app.ros.ros2 import Ros2Dispatcher
            _dispatcher = Ros2Dispatcher()
    return _dispatcher


def reset_ros_dispatcher() -> None:
    """清空调度器缓存（测试切换 ROS_VERSION 后调用）。"""
    global _dispatcher
    if _dispatcher is not None:
        _dispatcher.stop()
    _dispatcher = None
