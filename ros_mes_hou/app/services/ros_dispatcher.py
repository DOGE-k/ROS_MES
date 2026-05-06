"""ROS 指令下发适配层。

当前仓库还没有真正的 ROS bridge/ROS topic 客户端代码，因此这里先做一个统一适配层：
1. 后端接口不再只是 print，而是统一走 dispatch，前后端接口闭环。
2. 默认 mock 模式会记录日志并返回成功，便于前端联调。
3. 以后接入 ROS 时，只需要设置环境变量 ROS_DISPATCH_COMMAND，或替换本文件内部实现即可。

ROS_DISPATCH_COMMAND 示例：
  export ROS_DISPATCH_COMMAND="python /path/to/ros_bridge.py"

后端会把 action 和 payload 以 JSON 形式通过 stdin 传给该命令。
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class RosDispatchError(RuntimeError):
    """ROS 下发失败。"""


class RosDispatcher:
    def __init__(self) -> None:
        self.command = os.getenv("ROS_DISPATCH_COMMAND", "").strip()
        self.timeout = float(os.getenv("ROS_DISPATCH_TIMEOUT", "5"))

    def dispatch(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        message = {
            "action": action,
            "payload": payload,
            "timestamp": datetime.now().isoformat(),
        }

        if not self.command:
            logger.info("ROS mock dispatch: %s", message)
            return {
                "sent": True,
                "mode": "mock",
                "action": action,
                "payload": payload,
                "message": "ROS_DISPATCH_COMMAND 未配置，已进入 mock 下发模式",
            }

        try:
            completed = subprocess.run(
                self.command,
                input=json.dumps(message, ensure_ascii=False),
                text=True,
                shell=True,
                capture_output=True,
                timeout=self.timeout,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            logger.exception("ROS command failed")
            raise RosDispatchError(exc.stderr or str(exc)) from exc
        except subprocess.TimeoutExpired as exc:
            logger.exception("ROS command timeout")
            raise RosDispatchError("ROS 下发超时") from exc

        return {
            "sent": True,
            "mode": "command",
            "action": action,
            "payload": payload,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }


ros_dispatcher = RosDispatcher()
