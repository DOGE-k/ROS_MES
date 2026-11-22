#!/usr/bin/env bash
# ============================================================
# ROS MES 部署检查脚本（V1.1）
#
# 只读检查，不修改任何文件。用于部署后自检、交接验收、故障定位。
#
# 用法：
#   bash deploy/check_deploy.sh
#   bash deploy/check_deploy.sh --mock-only   # 只检查前后端，跳过 ROS/CAN
#   bash deploy/check_deploy.sh --strict      # WARN 也按失败处理
#
# 退出码：
#   0  没有 FAIL
#   1  存在 FAIL（或 --strict 下存在 WARN）
# ============================================================

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WORKSPACE_ROOT="$(cd "$PROJECT_ROOT/../.." 2>/dev/null && pwd || true)"
BACKEND_DIR="$PROJECT_ROOT/mes_web/ros_mes_hou"
FRONTEND_DIR="$PROJECT_ROOT/mes_web/ros_mes_front"
ROS_ENV="$PROJECT_ROOT/robot_control_backend/rob_arm.env"

MOCK_ONLY=0
STRICT=0

while [ $# -gt 0 ]; do
    case "$1" in
        --mock-only) MOCK_ONLY=1 ;;
        --strict)    STRICT=1 ;;
        -h|--help)
            sed -n '2,18p' "$0"
            exit 0
            ;;
        *) echo "错误：未知参数 $1"; exit 1 ;;
    esac
    shift
done

PASS=0
WARN=0
FAIL=0

ok()   { PASS=$((PASS + 1)); printf '[PASS] %s\n' "$*"; }
warn() { WARN=$((WARN + 1)); printf '[WARN] %s\n' "$*"; }
bad()  { FAIL=$((FAIL + 1)); printf '[FAIL] %s\n' "$*"; }
info() { printf '[INFO] %s\n' "$*"; }
section() { printf '\n===== %s =====\n' "$*"; }

get_env() {
    local file="$1" key="$2"
    grep -E "^${key}=" "$file" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '\r' || true
}

port_open() {
    ss -lnt 2>/dev/null | awk '{print $4}' | grep -q ":$1$"
}

http_ok() {
    command -v curl >/dev/null 2>&1 && curl -fsS --max-time 2 "$1" >/dev/null 2>&1
}

# ---------------- 1. 系统与目录 ----------------
section "1. 系统与目录"

if [ -f /etc/os-release ]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    info "系统：${PRETTY_NAME:-unknown}"
    if [ "${ID:-}" = "ubuntu" ]; then
        ok "操作系统为 Ubuntu"
    else
        bad "操作系统不是 Ubuntu（${ID:-unknown}）"
    fi
    if [ "${VERSION_ID:-}" = "20.04" ]; then
        ok "Ubuntu 版本为 20.04"
    elif [ "$MOCK_ONLY" -eq 1 ]; then
        warn "Ubuntu 版本为 ${VERSION_ID:-unknown}；--mock-only 下可忽略，ROS Noetic 需要 20.04"
    else
        bad "Ubuntu 版本为 ${VERSION_ID:-unknown}，ROS Noetic 需要 20.04"
    fi
else
    bad "缺少 /etc/os-release，无法识别系统"
fi

ARCH="$(uname -m)"
case "$ARCH" in
    x86_64|aarch64) ok "CPU 架构：$ARCH" ;;
    *) warn "CPU 架构：$ARCH（未验证）" ;;
esac

for d in robot_control_backend mes_web deploy; do
    if [ -d "$PROJECT_ROOT/$d" ]; then
        ok "项目目录存在：$d"
    else
        bad "缺少项目目录：$d"
    fi
done

if [ -n "$WORKSPACE_ROOT" ] && [ -d "$WORKSPACE_ROOT/src" ]; then
    ok "ROS 工作空间：$WORKSPACE_ROOT"
else
    warn "未识别到 catkin 工作空间（期望 ~/robot_ws/src/ROS_MES）"
fi

AVAIL_KB="$(df -Pk "$PROJECT_ROOT" | awk 'NR==2 {print $4}')"
if [ "${AVAIL_KB:-0}" -ge 2097152 ]; then
    ok "磁盘可用空间 ≥ 2GB"
elif [ "${AVAIL_KB:-0}" -ge 1048576 ]; then
    warn "磁盘可用空间 1~2GB，建议清理"
else
    bad "磁盘可用空间不足 1GB"
fi

# ---------------- 2. ROS 环境 ----------------
if [ "$MOCK_ONLY" -eq 0 ]; then
    section "2. ROS 环境"

    if [ -f /opt/ros/noetic/setup.bash ]; then
        ok "ROS Noetic 已安装"
        ROS_VER="$(source /opt/ros/noetic/setup.bash >/dev/null 2>&1; rosversion -d 2>/dev/null || true)"
        if [ "$ROS_VER" = "noetic" ]; then
            ok "rosversion：noetic"
        else
            bad "rosversion 异常：${ROS_VER:-空}"
        fi
    else
        bad "未找到 /opt/ros/noetic/setup.bash"
    fi

    if [ -n "$WORKSPACE_ROOT" ] && [ -f "$WORKSPACE_ROOT/devel/setup.bash" ]; then
        ok "工作空间已编译：devel/setup.bash 存在"
        PKG_PATH="$(source /opt/ros/noetic/setup.bash >/dev/null 2>&1; source "$WORKSPACE_ROOT/devel/setup.bash" >/dev/null 2>&1; rospack find robot_control_backend 2>/dev/null || true)"
        if [ -n "$PKG_PATH" ]; then
            ok "rospack 找到 robot_control_backend"
        else
            bad "rospack 找不到 robot_control_backend"
        fi
        if ( source /opt/ros/noetic/setup.bash >/dev/null 2>&1; source "$WORKSPACE_ROOT/devel/setup.bash" >/dev/null 2>&1; rosmsg show robot_control_backend/AxisStatus >/dev/null 2>&1 ); then
            ok "消息 robot_control_backend/AxisStatus 可用"
        else
            bad "消息 robot_control_backend/AxisStatus 不可用"
        fi
    else
        bad "工作空间未编译或路径不对（缺少 devel/setup.bash）"
    fi

    if [ -f /opt/ros/noetic/setup.bash ]; then
        for mod in rospy numpy scipy flask can open3d cryptography; do
            if ( source /opt/ros/noetic/setup.bash >/dev/null 2>&1; python3 -c "import $mod" >/dev/null 2>&1 ); then
                ok "ROS Python 模块：$mod"
            else
                bad "ROS Python 模块缺失：$mod"
            fi
        done
    fi

    if [ -f "$PROJECT_ROOT/robot_control_backend/launch/ros_robot.launch" ]; then
        ok "启动文件 ros_robot.launch 存在"
    else
        bad "缺少 robot_control_backend/launch/ros_robot.launch"
    fi
fi

# ---------------- 3. 后端 ----------------
section "$([ "$MOCK_ONLY" -eq 1 ] && echo '2' || echo '3'). 后端"

if [ -x "$BACKEND_DIR/venv/bin/python" ]; then
    ok "后端 venv 存在"
    PY_VER="$("$BACKEND_DIR/venv/bin/python" -c 'import sys; print(".".join(map(str, sys.version_info[:3])))' 2>/dev/null || true)"
    if "$BACKEND_DIR/venv/bin/python" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3,10) else 1)' 2>/dev/null; then
        ok "后端 Python 版本：${PY_VER:-unknown}"
    else
        bad "后端 Python 版本过低：${PY_VER:-unknown}（需要 3.10+）"
    fi
    if "$BACKEND_DIR/venv/bin/python" -c 'import fastapi, uvicorn, sqlalchemy, pydantic' >/dev/null 2>&1; then
        ok "后端核心依赖可导入（fastapi/uvicorn/sqlalchemy/pydantic）"
    else
        bad "后端核心依赖缺失，请重新安装 requirements.txt"
    fi
    if "$BACKEND_DIR/venv/bin/pip" check >/dev/null 2>&1; then
        ok "pip check 通过"
    else
        warn "pip check 有依赖冲突"
    fi
else
    bad "后端 venv 不存在：$BACKEND_DIR/venv"
fi

if [ -f "$BACKEND_DIR/.env" ]; then
    ok "后端 .env 存在"
    for key in DATABASE_URL ROSBRIDGE_URL SECRET_KEY ROS_MODULE_SEG_MAP; do
        val="$(get_env "$BACKEND_DIR/.env" "$key")"
        if [ -n "$val" ]; then
            ok "后端配置项：$key"
        else
            bad "后端缺少配置项：$key"
        fi
    done

    SECRET="$(get_env "$BACKEND_DIR/.env" "SECRET_KEY")"
    if [ "${#SECRET}" -lt 16 ] || printf '%s' "$SECRET" | grep -qiE 'change|your-secret|todo|example'; then
        warn "SECRET_KEY 仍是占位值或过短，正式使用前请更换"
    else
        ok "SECRET_KEY 已设置"
    fi

    SEG_MAP="$(get_env "$BACKEND_DIR/.env" "ROS_MODULE_SEG_MAP")"
    if python3 -c 'import json,sys; json.loads(sys.argv[1])' "$SEG_MAP" >/dev/null 2>&1; then
        ok "ROS_MODULE_SEG_MAP 是合法 JSON"
    else
        bad "ROS_MODULE_SEG_MAP 不是合法 JSON：$SEG_MAP"
    fi
else
    bad "后端 .env 不存在：$BACKEND_DIR/.env"
fi

if [ -x "$BACKEND_DIR/venv/bin/python" ]; then
    DB_CHECK="$("$BACKEND_DIR/venv/bin/python" - "$PROJECT_ROOT/ros_database.db" <<'PY' 2>/dev/null
import sqlite3, sys
try:
    con = sqlite3.connect(sys.argv[1])
    tables = [r[0] for r in con.execute("select name from sqlite_master where type='table'")]
    if "users" not in tables:
        print("missing users table")
        raise SystemExit(1)
    count = con.execute("select count(*) from users").fetchone()[0]
    print(f"users={count}")
except Exception as exc:
    print(exc)
    raise SystemExit(1)
PY
)"
    if [ $? -eq 0 ] && [ -n "$DB_CHECK" ]; then
        ok "数据库可读：$DB_CHECK"
    else
        bad "数据库不可用或缺少 users 表：${DB_CHECK:-unknown}"
    fi
else
    warn "无后端 venv，跳过数据库读取检查"
fi

if [ -f "$PROJECT_ROOT/ros_database.db" ]; then
    if [ -w "$PROJECT_ROOT/ros_database.db" ]; then
        ok "数据库文件可写"
    else
        bad "数据库文件不可写：$PROJECT_ROOT/ros_database.db"
    fi
else
    bad "数据库文件不存在：$PROJECT_ROOT/ros_database.db"
fi

# 前后端数据库路径一致性
if [ -f "$BACKEND_DIR/.env" ] && [ -x "$BACKEND_DIR/venv/bin/python" ]; then
    BACKEND_DB="$("$BACKEND_DIR/venv/bin/python" - "$BACKEND_DIR" <<'PY' 2>/dev/null
import re, sys
from pathlib import Path
base = Path(sys.argv[1])
text = (base / ".env").read_text(encoding="utf-8", errors="ignore")
m = re.search(r"^DATABASE_URL=(.*)$", text, re.M)
if not m:
    raise SystemExit(1)
url = m.group(1).strip()
prefix = "sqlite:///"
if not url.startswith(prefix):
    raise SystemExit(2)
raw = url[len(prefix):]
p = Path(raw)
if not p.is_absolute():
    p = base / p
print(p.resolve())
PY
)"
    ROS_DB="$(get_env "$ROS_ENV" "DB_PATH")"
    if [ -n "$BACKEND_DB" ] && [ -n "$ROS_DB" ]; then
        if [ "$(realpath -m "$BACKEND_DB")" = "$(realpath -m "$ROS_DB")" ]; then
            ok "前后端使用同一个数据库文件"
        else
            bad "前后端数据库不一致：backend=$BACKEND_DB ros=$ROS_DB"
        fi
    else
        warn "无法比较前后端数据库路径（缺少 DATABASE_URL 或 DB_PATH）"
    fi
fi

# ---------------- 4. ROS 配置与 CAN ----------------
if [ "$MOCK_ONLY" -eq 0 ]; then
    section "4. ROS 配置与 CAN"

    if [ -f "$ROS_ENV" ]; then
        ok "rob_arm.env 存在"
        for key in DB_PATH CAN_INTERFACE CAN_CHANNEL CAN_BITRATE; do
            val="$(get_env "$ROS_ENV" "$key")"
            if [ -n "$val" ]; then
                ok "ROS 配置项：$key=$val"
            else
                bad "ROS 缺少配置项：$key"
            fi
        done

        ROS_DB="$(get_env "$ROS_ENV" "DB_PATH")"
        if [ -n "$ROS_DB" ] && [ -f "$ROS_DB" ]; then
            ok "ROS DB_PATH 指向的文件存在"
        else
            bad "ROS DB_PATH 指向的文件不存在：${ROS_DB:-空}"
        fi

        IFACE="$(get_env "$ROS_ENV" "CAN_INTERFACE")"
        BITRATE="$(get_env "$ROS_ENV" "CAN_BITRATE")"
        if [ "$BITRATE" = "500000" ]; then
            ok "CAN 波特率：500000"
        else
            bad "CAN 波特率应为 500000，当前：${BITRATE:-空}"
        fi

        if [ "$IFACE" = "zlg" ]; then
            ZLG_PATH="$(get_env "$ROS_ENV" "ZLG_LIBUSB_PATH")"
            if [ -n "$ZLG_PATH" ] && [ -f "$ZLG_PATH" ]; then
                ok "ZLG 库路径存在：$ZLG_PATH"
                if ZLG_PATH="$ZLG_PATH" python3 -c 'import ctypes, os; ctypes.CDLL(os.environ["ZLG_PATH"])' >/dev/null 2>&1; then
                    ok "libusbcan.so 可加载"
                else
                    bad "libusbcan.so 加载失败，检查 libusb-1.0-0 或架构"
                fi
            else
                bad "ZLG_LIBUSB_PATH 未设置或文件不存在：${ZLG_PATH:-空}"
            fi

            if [ -f /etc/udev/rules.d/99-zlg-usbcan.rules ]; then
                ok "udev 规则存在：99-zlg-usbcan.rules"
            else
                warn "缺少 udev 规则，普通用户可能无法打开 USB 设备"
            fi

            if command -v lsusb >/dev/null 2>&1; then
                if lsusb | grep -q "0471:1200"; then
                    ok "已识别 ZLG USBCAN-II（0471:1200）"
                else
                    warn "未识别到 0471:1200；请检查适配器是否插好、换 USB2.0 口"
                fi
            else
                warn "未安装 lsusb，跳过设备识别检查"
            fi
        elif [ "$IFACE" = "socketcan" ]; then
            warn "CAN_INTERFACE=socketcan；请确认 can0 已由系统配置"
            if command -v ip >/dev/null 2>&1 && ip link show can0 >/dev/null 2>&1; then
                ok "SocketCAN 接口 can0 存在"
            else
                warn "未找到 can0"
            fi
        else
            warn "未知 CAN_INTERFACE：${IFACE:-空}"
        fi
    else
        bad "rob_arm.env 不存在：$ROS_ENV"
    fi
fi

# ---------------- 5. 前端 ----------------
section "$([ "$MOCK_ONLY" -eq 1 ] && echo '3' || echo '5'). 前端"

if command -v node >/dev/null 2>&1; then
    NODE_MAJOR="$(node -v | sed 's/^v//' | cut -d. -f1)"
    if [ "${NODE_MAJOR:-0}" -ge 18 ]; then
        ok "Node.js 版本：$(node -v)"
    else
        bad "Node.js 版本过低：$(node -v)（需要 18+）"
    fi
else
    bad "未安装 Node.js"
fi

if command -v npm >/dev/null 2>&1; then
    ok "npm 版本：$(npm -v)"
else
    bad "未安装 npm"
fi

if [ -d "$FRONTEND_DIR/node_modules" ]; then
    ok "前端 node_modules 存在"
else
    bad "前端 node_modules 不存在，请运行 npm install"
fi

if [ -f "$FRONTEND_DIR/.env.development" ] || [ -f "$FRONTEND_DIR/.env" ]; then
    ok "前端环境文件存在"
    FE_ENV="$FRONTEND_DIR/.env.development"
    [ -f "$FE_ENV" ] || FE_ENV="$FRONTEND_DIR/.env"
    TARGET="$(get_env "$FE_ENV" "VITE_API_TARGET")"
    if [ -n "$TARGET" ]; then
        ok "VITE_API_TARGET=$TARGET"
    else
        warn "未设置 VITE_API_TARGET"
    fi
else
    bad "缺少前端 .env.development/.env"
fi

# ---------------- 6. 服务与端口 ----------------
section "$([ "$MOCK_ONLY" -eq 1 ] && echo '4' || echo '6'). 服务与端口"

for p in 8000 5173 9010 5000; do
    if port_open "$p"; then
        ok "端口 $p 正在监听"
    else
        warn "端口 $p 未监听（服务可能尚未启动）"
    fi
done

if http_ok "http://127.0.0.1:8000/docs"; then
    ok "后端 HTTP 可访问（/docs）"
else
    warn "后端 /docs 暂不可访问（可能未启动）"
fi

if http_ok "http://127.0.0.1:5173/"; then
    ok "前端 HTTP 可访问"
else
    warn "前端暂不可访问（可能未启动）"
fi

if [ "$MOCK_ONLY" -eq 0 ] && [ -f /opt/ros/noetic/setup.bash ]; then
    NODES="$(source /opt/ros/noetic/setup.bash >/dev/null 2>&1; timeout 3 rosnode list 2>/dev/null || true)"
    if [ -n "$NODES" ]; then
        ok "ROS master 正在运行"
        for n in stm32_bridge axis_status_aggregator arm_sequence_controller feedback_node; do
            if printf '%s\n' "$NODES" | grep -q "$n"; then
                ok "ROS 节点在线：$n"
            else
                warn "ROS 节点未在线：$n"
            fi
        done
        TOPICS="$(source /opt/ros/noetic/setup.bash >/dev/null 2>&1; timeout 3 rostopic list 2>/dev/null || true)"
        for t in /hardware/axis_status /hardware/rotation_feedback /control/adjust_rotation_cmd; do
            if printf '%s\n' "$TOPICS" | grep -qx "$t"; then
                ok "ROS 话题存在：$t"
            else
                warn "ROS 话题不存在：$t"
            fi
        done
    else
        warn "ROS master 未运行（roslaunch 可能尚未启动）"
    fi
fi

# ---------------- 7. 权限 ----------------
section "$([ "$MOCK_ONLY" -eq 1 ] && echo '5' || echo '7'). 文件权限"

for path in "$BACKEND_DIR/venv" "$FRONTEND_DIR/node_modules"; do
    if [ -e "$path" ]; then
        OWNER="$(stat -c '%U' "$path" 2>/dev/null || echo unknown)"
        if [ "$OWNER" = "$(id -un)" ]; then
            ok "属主正确：$path"
        else
            bad "属主为 $OWNER（当前用户 $(id -un)）：$path，可能由 sudo 安装导致"
        fi
    fi
done

# ---------------- 8. 汇总 ----------------
section "检查汇总"
printf 'PASS=%d  WARN=%d  FAIL=%d\n' "$PASS" "$WARN" "$FAIL"

if [ "$FAIL" -gt 0 ]; then
    echo "结果：存在 FAIL，请按上面的 FAIL 项处理。"
    exit 1
fi

if [ "$STRICT" -eq 1 ] && [ "$WARN" -gt 0 ]; then
    echo "结果：--strict 下 WARN 视为失败。"
    exit 1
fi

echo "结果：检查通过（WARN 项请结合服务是否已启动判断）。"
exit 0
