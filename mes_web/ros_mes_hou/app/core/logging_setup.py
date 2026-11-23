"""统一日志配置：控制台 + 滚动文件，带请求关联 ID。

规范（测试排错用）：
- 只在本模块配置 logging；业务代码一律 ``logging.getLogger(__name__)``，不 print、不 basicConfig。
- 每条日志都带 ``req=<8位>``。一次动作从 HTTP 请求 → 批次登记 → ROS 下发 → 到位/结论
  共用同一个 ID，出问题直接 ``grep req=xxxxxxxx logs/backend.log`` 就能拉出完整时间线。
- 轮询类 GET 由 RequestLogMiddleware 降到 DEBUG，默认不落 INFO，避免把动作日志淹掉。
- 时间精确到毫秒、级别定宽，方便肉眼对齐和 grep。

环境变量：
- ``LOG_LEVEL``：控制台与 root 级别，默认 INFO
- ``LOG_FILE_LEVEL``：文件级别，默认 INFO（排错可设 DEBUG 保留轮询细节）
- ``LOG_DIR``：日志目录，默认 ``ros_mes_hou/logs``
- ``LOG_FILE_MAX_BYTES`` / ``LOG_FILE_BACKUP_COUNT``：滚动大小与保留份数
"""
from __future__ import annotations

import contextvars
import logging
import logging.config
import os
import sys
import uuid

from app.core.config import settings

REQUEST_ID: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

LOG_FORMAT = "%(asctime)s.%(msecs)03d %(levelname)-5s [%(name)s] req=%(request_id)s %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# uvicorn 自己的 logger 全部交给 root，统一格式、统一落盘；access 行由中间件替代
_UVICORN_LOGGERS = {
    "uvicorn": {"handlers": [], "level": "INFO", "propagate": True},
    "uvicorn.error": {"handlers": [], "level": "INFO", "propagate": True},
    "uvicorn.access": {"handlers": [], "level": "WARNING", "propagate": False},
    "uvicorn.asgi": {"handlers": [], "level": "WARNING", "propagate": True},
}

# 第三方库默认太吵，排错时只会干扰判断
_NOISY_LOGGERS = {
    "websockets": {"level": "WARNING"},
    "websockets.client": {"level": "WARNING"},
    "websockets.server": {"level": "WARNING"},
    "sqlalchemy.engine": {"level": "WARNING"},
    "asyncio": {"level": "WARNING"},
    "multipart": {"level": "WARNING"},
    "httpx": {"level": "WARNING"},
}

_configured = False


def new_request_id() -> str:
    """生成短请求 ID：8 位足够在单次测试里区分，也方便手抄。"""
    return uuid.uuid4().hex[:8]


def bind_request_id(value: str):
    return REQUEST_ID.set(value)


def reset_request_id(token) -> None:
    try:
        REQUEST_ID.reset(token)
    except ValueError:
        # 跨线程/任务 reset 会抛错；排错日志不能因为这个把请求打挂
        pass


def current_request_id() -> str:
    return REQUEST_ID.get()


class RequestIdFilter(logging.Filter):
    """给每条记录补 request_id；显式传入的 extra 优先。"""

    def filter(self, record: logging.LogRecord) -> bool:
        if not getattr(record, "request_id", None):
            record.request_id = REQUEST_ID.get()
        return True


def log_directory() -> str:
    return os.getenv("LOG_DIR") or os.path.join(settings.BACKEND_ROOT, "logs")


def _level_value(name: str) -> int:
    """把 "DEBUG"/"INFO" 这类名字转成数值级别，非法值退回 INFO。"""
    value = logging.getLevelName(name)
    return value if isinstance(value, int) else logging.INFO


def _file_logging_enabled() -> bool:
    """测试跑（unittest/pytest）默认不写文件，避免把用例日志混进现场日志。

    需要连测试也落盘时设 ``LOG_TO_FILE=1``。
    """
    if os.getenv("LOG_TO_FILE", "").strip() == "1":
        return True
    return "unittest" not in sys.modules and "pytest" not in sys.modules


def log_file_path() -> str:
    return os.path.join(log_directory(), "backend.log")


# 请求行专用：状态码放最前面、定宽对齐，一眼能扫 200/409/422/500。
# 业务日志仍用完整字段（时间+级别+模块+req），两者不要混成一种样式。
REQUEST_KIND = "request"

_STATUS_WORDS = {
    200: "OK", 201: "Created", 202: "Accepted", 204: "NoContent", 304: "NotMod",
    400: "BadRequest", 401: "Auth", 403: "Forbidden", 404: "NotFound",
    405: "NoMethod", 409: "Conflict", 422: "BadParams", 429: "RateLimit",
    500: "Error", 502: "Gateway", 503: "Down", 504: "Timeout",
}

_ANSI_COLORS = {2: "32", 3: "36", 4: "33", 5: "31"}

_STATUS_WIDTH = 15  # 最长的 "422 BadParams"(13) 也留出两格，避免和 METHOD 粘在一起


def status_text(status: int) -> str:
    word = _STATUS_WORDS.get(status)
    if not word:
        try:
            from http import HTTPStatus
            word = HTTPStatus(status).phrase
        except Exception:
            word = ""
    word = word[:12]
    return f"{status} {word}".strip()


class RouterFormatter(logging.Formatter):
    """请求行短格式 + 业务日志完整格式。"""

    def __init__(self, *args, color: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.color = color

    def format(self, record):
        if getattr(record, "kind", "") == REQUEST_KIND:
            return self._format_request(record)
        return super().format(record)

    def _format_request(self, record) -> str:
        status = int(getattr(record, "status", 0) or 0)
        # 状态码固定在最前（第 14 列起）：即使终端太窄折行，"200 OK" 也永远在行首可见
        text = f"{status_text(status):<{_STATUS_WIDTH}}"
        if self.color and status:
            code = _ANSI_COLORS.get(status // 100)
            if code:
                text = f"\x1b[{code}m{text}\x1b[0m"
        target = getattr(record, "target", "?")
        if len(target) > 34:
            target = target[:33] + "…"
        note = getattr(record, "note", "")
        line = (f"{self.formatTime(record, '%H:%M:%S')}.{int(record.msecs):03d} "
                f"{text}{getattr(record, 'method', '?'):<5}{target:<35}"
                f"{getattr(record, 'elapsed_ms', 0.0):.1f}ms  rid={getattr(record, 'request_id', '-')}")
        if note:
            line = f"{line}  ← {note}"
        # 异常必须带栈，否则 request 行会吞掉 traceback
        if record.exc_info:
            line = f"{line}\n{self.formatException(record.exc_info)}"
        return line


def _console_supports_color() -> bool:
    """控制台给状态码上色（2xx 绿 / 4xx 黄 / 5xx 红）。文件永不带上色转义。"""
    try:
        if sys.stderr.isatty():
            return True
    except Exception:
        pass
    if os.name == "nt":
        # PTY / 被包装时 isatty() 可能是 False，但确实是 Windows 控制台，照样支持 ANSI
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            mode = ctypes.c_uint32()
            return bool(kernel32.GetConsoleMode(kernel32.GetStdHandle(-12), ctypes.byref(mode)))
        except Exception:
            return False
    return False


def setup_logging(level: str | None = None, force: bool = False) -> None:
    """配置 root logger。重复调用只生效一次，除非 force=True（测试用）。"""
    global _configured
    if _configured and not force:
        return

    console_level = (level or os.getenv("LOG_LEVEL") or "INFO").upper()
    file_level = (os.getenv("LOG_FILE_LEVEL") or console_level).upper()
    directory = log_directory()
    os.makedirs(directory, exist_ok=True)
    # root 必须放到两者中更细的级别，否则 LOG_FILE_LEVEL=DEBUG 时 DEBUG 记录在
    # logger 层就被 INFO 拦掉，根本到不了文件 handler。
    root_level = min(_level_value(console_level), _level_value(file_level))
    handlers = ["console", "file"] if _file_logging_enabled() else ["console"]
    # 颜色只给控制台；文件里绝不写 ANSI 转义，否则 grep 会带上乱码
    color_env = os.getenv("LOG_COLOR", "auto").strip().lower()
    if color_env in ("0", "never", "false"):
        use_color = False
    elif color_env in ("1", "always", "true"):
        use_color = True
    else:
        use_color = _console_supports_color()

    config = {
        "version": 1,
        # 不能关掉已存在的 logger：uvicorn 先配过一次，这里接管而不是禁用
        "disable_existing_loggers": False,
        "filters": {"request_id": {"()": RequestIdFilter}},
        "formatters": {
            "standard": {"()": RouterFormatter, "format": LOG_FORMAT, "datefmt": LOG_DATE_FORMAT},
            "console": {"()": RouterFormatter, "format": LOG_FORMAT, "datefmt": LOG_DATE_FORMAT,
                        "color": use_color},
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
                "formatter": "console",
                "filters": ["request_id"],
                "level": console_level,
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": log_file_path(),
                "maxBytes": int(os.getenv("LOG_FILE_MAX_BYTES", str(10 * 1024 * 1024))),
                "backupCount": int(os.getenv("LOG_FILE_BACKUP_COUNT", "5")),
                "encoding": "utf-8",
                "delay": True,
                "formatter": "standard",
                "filters": ["request_id"],
                "level": file_level,
            },
        },
        "root": {"handlers": handlers, "level": root_level},
        "loggers": {**_UVICORN_LOGGERS, **_NOISY_LOGGERS},
    }
    logging.config.dictConfig(config)
    _configured = True


def describe_logging() -> str:
    if not _file_logging_enabled():
        return f"控制台 {os.getenv('LOG_LEVEL', 'INFO').upper()}（测试运行，不写文件）"
    return (f"控制台 {os.getenv('LOG_LEVEL', 'INFO').upper()} / 文件 "
            f"{os.getenv('LOG_FILE_LEVEL', os.getenv('LOG_LEVEL', 'INFO')).upper()} → {log_file_path()}")


def ensure_utf8_streams() -> None:
    """Windows 控制台默认 GBK，中文和 emoji 会 UnicodeEncodeError，直接打断业务日志。"""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
