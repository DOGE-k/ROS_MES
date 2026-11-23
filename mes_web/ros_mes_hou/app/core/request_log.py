"""请求级日志中间件：一个请求一行，按路由分级，带耗时和关联 ID。

为什么不用 uvicorn 的 access log：
- 它无法区分"前端 2 秒一次的轮询"和"操作员真的下发了一次运动"，
  两者混在一起时日志等于没用；
- 它没有请求关联 ID，一次微调要跨 HTTP → 批次 → ROS 才能拼出时间线。

分级规则：
- 轮询类 GET（急停状态、局部停列表、批次查询、静态资源）→ DEBUG，只在 LOG_FILE_LEVEL=DEBUG 时落盘
- 写操作（POST/PATCH/PUT/DELETE）→ INFO
- 慢请求（默认 >1000ms）→ WARNING
- 5xx 或未处理异常 → ERROR（异常带栈）

用纯 ASGI 实现而不是 BaseHTTPMiddleware：后者会包一层 StreamingResponse，
对本项目的 WebSocket 与流式反馈没有必要，也可能改变响应行为。
"""
from __future__ import annotations

import logging
import os
import time

from app.core.logging_setup import REQUEST_KIND, bind_request_id, new_request_id, reset_request_id

logger = logging.getLogger(__name__)

# 前端轮询路径：默认不落 INFO。新增轮询接口时加到这里，别让日志被刷掉。
QUIET_PREFIXES = (
    "/api/control/emergency_stop/status",
    "/api/control/stop/holds",
    "/api/control/finetuning/batches/active",
    "/api/control/hardware/realtime",
    "/api/ws/",
    "/api/uploads/",
    "/api/openapi.json",
    "/docs",
    "/favicon.ico",
)

# 只读且不轮询的 GET 也按 INFO 记录，方便看页面到底调了哪些接口
_READ_METHODS = ("GET", "HEAD", "OPTIONS")


def _polling_visible() -> bool:
    """LOG_POLLING=1 时连轮询也按 INFO 打出来，用于确认页面在不在正常查询。"""
    return os.getenv("LOG_POLLING", "").strip() == "1"


def _slow_threshold_ms() -> float:
    try:
        return float(os.getenv("LOG_SLOW_REQUEST_MS", "1000"))
    except ValueError:
        return 1000.0


def _fields(method, target, status, elapsed, request_id, note) -> dict:
    """交给 RouterFormatter 渲染成 `时:分:秒.毫秒  200 OK  GET  路径  耗时  rid=`。"""
    return {
        "kind": REQUEST_KIND,
        "method": method,
        "target": target,
        "status": status,
        "elapsed_ms": elapsed,
        "request_id": request_id,
        "note": note,
    }


class RequestLogMiddleware:
    def __init__(self, app, quiet_prefixes=QUIET_PREFIXES):
        self.app = app
        self.quiet_prefixes = tuple(quiet_prefixes)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {key.lower(): value for key, value in (scope.get("headers") or [])}
        incoming = headers.get(b"x-request-id", b"").decode("latin-1").strip()
        request_id = incoming[:16] or new_request_id()
        token = bind_request_id(request_id)

        method = scope.get("method", "?")
        path = scope.get("path", "?")
        query = (scope.get("query_string") or b"").decode("latin-1")
        target = f"{path}?{query}" if query else path
        quiet = (method in _READ_METHODS and target.startswith(self.quiet_prefixes)
                 and not _polling_visible())
        started = time.perf_counter()
        status_code = {"value": 0}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_code["value"] = int(message.get("status", 0))
                message["headers"] = list(message.get("headers") or []) + [
                    (b"x-request-id", request_id.encode("latin-1", "ignore"))
                ]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            elapsed = (time.perf_counter() - started) * 1000
            logger.exception("%s %s -> 未处理异常 %.1fms", method, target, elapsed,
                             extra=_fields(method, target, 500, elapsed, request_id, "未处理异常"))
            raise
        else:
            elapsed = (time.perf_counter() - started) * 1000
            self._emit(method, target, status_code["value"], elapsed, quiet, request_id)
        finally:
            reset_request_id(token)

    def _emit(self, method, target, status, elapsed, quiet, request_id):
        # 级别决定要不要落下来；显示格式统一由 RouterFormatter 拼（状态码在最前）
        if status >= 500:
            level, note = logging.ERROR, "服务端错误"
        elif elapsed >= _slow_threshold_ms():
            level, note = logging.WARNING, "慢请求"
        elif quiet and status < 400:
            # 轮询成功才降级；轮询路径返回 401/409 说明登录态或联锁变了，必须留 INFO
            level, note = logging.DEBUG, ""
        elif status >= 400:
            # 4xx 是测试里最需要看到的：409 重复下发、422 参数不合法都在这里
            level, note = logging.INFO, "已拒绝"
        else:
            level, note = logging.INFO, ""
        logger.log(
            level, "%s %s -> %s %.1fms", method, target, status or "?", elapsed,
            extra=_fields(method, target, status or 0, elapsed, request_id, note),
        )
