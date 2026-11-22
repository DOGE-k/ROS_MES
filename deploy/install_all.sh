#!/usr/bin/env bash
# ============================================================
# ROS MES 一键部署脚本（V1.1）
#
# 默认完成：
#   - 系统基础依赖
#   - Python 3.10+ / Node.js 18+
#   - ROS Noetic + rosbridge（可选）
#   - ROS 工作空间编译
#   - 后端虚拟环境与依赖、数据库初始化
#   - 前端 npm 依赖与环境文件
#   - ZLG USBCAN-II 驱动安装与 udev 权限
#   - 最后自动运行 deploy/check_deploy.sh
#
# 用法：
#   bash deploy/install_all.sh              # 完整安装（接真机）
#   bash deploy/install_all.sh --mock-only  # 只装后端/前端，不装 ROS
#   bash deploy/install_all.sh --dry-run    # 只打印步骤，不修改系统
#   bash deploy/install_all.sh --mirror     # pip/npm 使用国内镜像
#
# 注意：
#   - 不要用 sudo 运行本脚本；脚本内部会对需要的步骤调用 sudo。
#   - 默认不覆盖已有数据库、.env、rob_arm.env，只补齐缺失项。
#   - 不支持在项目目录之外随意挪动；建议路径为 ~/robot_ws/src/ROS_MES。
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WORKSPACE_ROOT="$(cd "$PROJECT_ROOT/../.." 2>/dev/null && pwd || true)"
TS="$(date +%Y%m%d_%H%M%S)"

MOCK_ONLY=0
SKIP_ROS_INSTALL=0
USE_MIRROR=0
DRY_RUN=0
LOG_FILE=""

usage() {
    cat <<'EOF'
用法：
  bash deploy/install_all.sh [选项]

选项：
  --mock-only        只安装后端/前端，不装 ROS、不装 CAN 驱动
  --skip-ros-install 已自行装好 ROS，跳过 ROS apt 安装（仍会装 ROS Python 依赖和编译）
  --mirror           pip/npm 使用国内镜像
  --dry-run          只打印将执行的命令，不修改系统
  -h, --help         显示帮助

推荐：
  首次接真机：bash deploy/install_all.sh
  只看页面：  bash deploy/install_all.sh --mock-only
  先预览：    bash deploy/install_all.sh --dry-run
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --mock-only)        MOCK_ONLY=1 ;;
        --skip-ros-install) SKIP_ROS_INSTALL=1 ;;
        --mirror)            USE_MIRROR=1 ;;
        --dry-run)           DRY_RUN=1 ;;
        -h|--help)           usage; exit 0 ;;
        *) echo "错误：未知参数 $1"; usage; exit 1 ;;
    esac
    shift
done

log()  { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }
warn() { printf '[WARN] %s\n' "$*" >&2; }
die()  { printf '[ERROR] %s\n' "$*" >&2; exit 1; }

run() {
    if [ "$DRY_RUN" -eq 1 ]; then
        printf '+ '
        printf '%q ' "$@"
        printf '\n'
    else
        "$@"
    fi
}

run_shell() {
    if [ "$DRY_RUN" -eq 1 ]; then
        printf '+ bash -c %q\n' "$1"
    else
        bash -c "$1"
    fi
}

# ---------------- 0. 前置检查 ----------------
if [ "$DRY_RUN" -eq 0 ] && [ "$EUID" -eq 0 ]; then
    die "不要用 root 运行本脚本，请用普通用户运行；脚本内部会按需调用 sudo。"
fi

[ -d "$PROJECT_ROOT/robot_control_backend" ] || die "项目结构不完整：$PROJECT_ROOT"
[ -d "$PROJECT_ROOT/mes_web/ros_mes_hou" ] || die "缺少后端目录：mes_web/ros_mes_hou"
[ -d "$PROJECT_ROOT/mes_web/ros_mes_front" ] || die "缺少前端目录：mes_web/ros_mes_front"
[ -d "$PROJECT_ROOT/deploy" ] || die "缺少 deploy 目录：$PROJECT_ROOT/deploy"

if [ -f /etc/os-release ]; then
    # shellcheck disable=SC1091
    . /etc/os-release
else
    die "无法识别系统版本（缺少 /etc/os-release）。"
fi

if [ "${ID:-}" != "ubuntu" ]; then
    die "本脚本只支持 Ubuntu，当前：${ID:-unknown}。"
fi

if [ "${VERSION_ID:-}" != "20.04" ]; then
    if [ "$MOCK_ONLY" -eq 1 ]; then
        warn "当前 Ubuntu ${VERSION_ID}，--mock-only 可以继续；ROS Noetic 需要 20.04。"
    else
        die "ROS Noetic 需要 Ubuntu 20.04，当前 ${VERSION_ID}。只跑页面请加 --mock-only。"
    fi
fi

ARCH="$(uname -m)"
case "$ARCH" in
    x86_64|aarch64) : ;;
    *) warn "当前架构 $ARCH 未验证，ROS Noetic 官方主要支持 x86_64/aarch64。" ;;
esac

AVAIL_KB="$(df -Pk "$PROJECT_ROOT" | awk 'NR==2 {print $4}')"
if [ "${AVAIL_KB:-0}" -lt 5242880 ]; then
    warn "项目所在磁盘可用空间不足 5GB，安装 ROS 可能失败。"
fi

if ! getent hosts packages.ros.org >/dev/null 2>&1; then
    warn "无法解析 packages.ros.org，ROS 安装可能失败；请检查网络/DNS。"
fi

if [ "$DRY_RUN" -eq 0 ]; then
    log "请求 sudo 权限（安装系统依赖需要）..."
    sudo -v || die "无法获取 sudo 权限。"
    mkdir -p "$SCRIPT_DIR/logs"
    LOG_FILE="$SCRIPT_DIR/logs/install_${TS}.log"
    exec > >(tee -a "$LOG_FILE") 2>&1
    log "日志文件：$LOG_FILE"
fi

log "项目目录：$PROJECT_ROOT"
log "模式：$([ "$MOCK_ONLY" -eq 1 ] && echo '仅前后端' || echo '完整安装')$([ "$DRY_RUN" -eq 1 ] && echo '（预览）' || echo '')"

# ---------------- 1. 系统基础依赖 ----------------
log "安装系统基础依赖..."
BASE_PKGS=(
    curl gnupg2 lsb-release software-properties-common
    build-essential cmake unzip usbutils
    libusb-1.0-0 libgomp1 libgl1 libglib2.0-0
    python3-pip python3-venv python3-dev libffi-dev libssl-dev
)
run sudo apt-get update
run sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y "${BASE_PKGS[@]}"

# ---------------- 2. Python 3.10+ ----------------
find_python() {
    local c
    for c in python3.12 python3.11 python3.10; do
        if command -v "$c" >/dev/null 2>&1 \
            && "$c" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3,10) else 1)' 2>/dev/null \
            && "$c" -m venv --help >/dev/null 2>&1; then
            printf '%s' "$c"
            return 0
        fi
    done
    if command -v python3 >/dev/null 2>&1 \
        && python3 -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3,10) else 1)' 2>/dev/null \
        && python3 -m venv --help >/dev/null 2>&1; then
        printf 'python3'
        return 0
    fi
    return 1
}

PYTHON_BIN="$(find_python || true)"
if [ -z "$PYTHON_BIN" ]; then
    if [ "${VERSION_ID:-}" = "20.04" ]; then
        log "系统 Python 低于 3.10，安装 Python 3.11..."
        run sudo add-apt-repository ppa:deadsnakes/ppa -y
        run sudo apt-get update
        run sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y python3.11 python3.11-venv python3.11-dev
        PYTHON_BIN="python3.11"
    else
        die "找不到 Python 3.10+，请先安装 Python 3.10 或更高版本。"
    fi
fi
log "后端 Python：$PYTHON_BIN"

# ---------------- 3. Node.js 18+ ----------------
NODE_OK=0
if command -v node >/dev/null 2>&1; then
    NODE_MAJOR="$(node -v | sed 's/^v//' | cut -d. -f1)"
    if [ "${NODE_MAJOR:-0}" -ge 18 ]; then
        NODE_OK=1
    fi
fi
if [ "$NODE_OK" -eq 0 ]; then
    log "安装 Node.js 20..."
    run_shell "curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -"
    run sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y nodejs
fi

# ---------------- 4. ROS Noetic ----------------
if [ "$MOCK_ONLY" -eq 0 ]; then
    if [ ! -f /opt/ros/noetic/setup.bash ] && [ "$SKIP_ROS_INSTALL" -eq 0 ]; then
        log "安装 ROS Noetic（desktop-full + rosbridge）..."
        if [ ! -f /usr/share/keyrings/ros-archive-keyring.gpg ]; then
            run_shell "sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg"
        fi
        if [ ! -f /etc/apt/sources.list.d/ros-latest.list ]; then
            run_shell "echo 'deb [signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros/ubuntu focal main' | sudo tee /etc/apt/sources.list.d/ros-latest.list >/dev/null"
        fi
        run sudo apt-get update
        run sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y \
            ros-noetic-desktop-full ros-noetic-rosbridge-server ros-noetic-message-generation
    fi

    if [ -f /opt/ros/noetic/setup.bash ]; then
        log "安装 ROS 节点 Python 依赖..."
        run python3 -m pip install --user --upgrade pip
        run python3 -m pip install --user -r "$PROJECT_ROOT/deploy/config/ros_requirements.txt"

        if ! dpkg -s ros-noetic-rosbridge-server >/dev/null 2>&1; then
            log "补齐 rosbridge_server..."
            run sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y ros-noetic-rosbridge-server
        fi

        if [ -d "$WORKSPACE_ROOT/src" ]; then
            log "编译 ROS 工作空间：$WORKSPACE_ROOT"
            run bash -c "source /opt/ros/noetic/setup.bash && cd \"$WORKSPACE_ROOT\" && catkin_make"
        else
            warn "未找到 catkin 工作空间结构，跳过 catkin_make。期望路径：~/robot_ws/src/ROS_MES"
        fi

        if ! grep -q "/opt/ros/noetic/setup.bash" "$HOME/.bashrc" 2>/dev/null; then
            log "写入 ~/.bashrc：ROS 环境"
            run_shell "printf '\nsource /opt/ros/noetic/setup.bash\n' >> '$HOME/.bashrc'"
        fi
        if [ -n "$WORKSPACE_ROOT" ] && [ -f "$WORKSPACE_ROOT/devel/setup.bash" ] \
            && ! grep -q "$WORKSPACE_ROOT/devel/setup.bash" "$HOME/.bashrc" 2>/dev/null; then
            log "写入 ~/.bashrc：工作空间环境"
            run_shell "printf '\nsource %s/devel/setup.bash\n' '$WORKSPACE_ROOT' >> '$HOME/.bashrc'"
        fi
    else
        warn "未找到 /opt/ros/noetic/setup.bash，跳过 ROS 依赖与编译。"
    fi
fi

# ---------------- 5. 后端 ----------------
BACKEND_DIR="$PROJECT_ROOT/mes_web/ros_mes_hou"
BACKEND_ENV="$BACKEND_DIR/.env"
BACKEND_TEMPLATE="$PROJECT_ROOT/deploy/config/backend.env"

[ -f "$BACKEND_DIR/requirements.txt" ] || die "缺少后端 requirements.txt"
[ -f "$BACKEND_TEMPLATE" ] || die "缺少后端配置模板：$BACKEND_TEMPLATE"

if [ ! -f "$BACKEND_ENV" ]; then
    log "创建后端 .env..."
    run cp "$BACKEND_TEMPLATE" "$BACKEND_ENV"
else
    log "保留现有后端 .env"
fi

# 只在仍是占位值时生成 SECRET_KEY
SECRET_VAL="$(grep -E '^SECRET_KEY=' "$BACKEND_ENV" 2>/dev/null | tail -1 | cut -d= -f2- || true)"
if [ -z "$SECRET_VAL" ] || [ "${#SECRET_VAL}" -lt 16 ] \
    || printf '%s' "$SECRET_VAL" | grep -qiE 'change|your-secret|todo|example'; then
    NEW_SECRET="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
    log "生成新的 SECRET_KEY..."
    run cp "$BACKEND_ENV" "$BACKEND_ENV.bak.$TS"
    if grep -q '^SECRET_KEY=' "$BACKEND_ENV" 2>/dev/null; then
        run sed -i "s|^SECRET_KEY=.*|SECRET_KEY=$NEW_SECRET|" "$BACKEND_ENV"
    else
        run_shell "printf '\nSECRET_KEY=%s\n' '$NEW_SECRET' >> '$BACKEND_ENV'"
    fi
fi

if [ -d "$BACKEND_DIR/venv" ] && [ ! -x "$BACKEND_DIR/venv/bin/python" ]; then
    warn "现有 venv 不完整，将重建（只删除 venv，不动数据库和配置）。"
    run rm -rf "$BACKEND_DIR/venv"
fi

if [ -d "$BACKEND_DIR/venv" ] && [ -x "$BACKEND_DIR/venv/bin/python" ]; then
    if ! "$BACKEND_DIR/venv/bin/python" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3,10) else 1)' 2>/dev/null; then
        warn "现有 venv 不是 Python 3.10+，将重建（只删除 venv，不动数据库和配置）。"
        run rm -rf "$BACKEND_DIR/venv"
    fi
fi

if [ ! -d "$BACKEND_DIR/venv" ]; then
    log "创建后端虚拟环境..."
    run "$PYTHON_BIN" -m venv "$BACKEND_DIR/venv"
fi

log "安装后端 Python 依赖..."
run "$BACKEND_DIR/venv/bin/python" -m pip install --upgrade pip
PIP_ARGS=(-r "$BACKEND_DIR/requirements.txt")
if [ "$USE_MIRROR" -eq 1 ]; then
    PIP_ARGS+=(-i https://pypi.tuna.tsinghua.edu.cn/simple)
fi
run "$BACKEND_DIR/venv/bin/pip" install "${PIP_ARGS[@]}"

if [ ! -f "$PROJECT_ROOT/ros_database.db" ]; then
    log "初始化数据库..."
    run bash -c "cd \"$PROJECT_ROOT\" && \"$BACKEND_DIR/venv/bin/python\" sqlite_create.py"
else
    log "保留现有数据库：$PROJECT_ROOT/ros_database.db"
fi

# ---------------- 6. 前端 ----------------
FRONTEND_DIR="$PROJECT_ROOT/mes_web/ros_mes_front"
FRONTEND_TEMPLATE="$PROJECT_ROOT/deploy/config/frontend.env"

[ -f "$FRONTEND_DIR/package.json" ] || die "缺少前端 package.json"
[ -f "$FRONTEND_TEMPLATE" ] || die "缺少前端配置模板：$FRONTEND_TEMPLATE"

if [ ! -f "$FRONTEND_DIR/.env.development" ] && [ ! -f "$FRONTEND_DIR/.env" ]; then
    log "创建前端环境文件..."
    run cp "$FRONTEND_TEMPLATE" "$FRONTEND_DIR/.env.development"
fi

log "安装前端 npm 依赖..."
if [ "$USE_MIRROR" -eq 1 ]; then
    run_shell "cd \"$FRONTEND_DIR\" && npm config set registry https://registry.npmmirror.com"
fi
run_shell "cd \"$FRONTEND_DIR\" && npm install --no-audit --no-fund"

# ---------------- 7. ROS 配置与 ZLG 驱动 ----------------
if [ "$MOCK_ONLY" -eq 0 ]; then
    ROS_ENV="$PROJECT_ROOT/robot_control_backend/rob_arm.env"
    if [ -f "$ROS_ENV" ]; then
        ROS_BACKUP_DONE=0
        backup_ros_env() {
            if [ "$ROS_BACKUP_DONE" -eq 0 ]; then
                run cp "$ROS_ENV" "$ROS_ENV.bak.$TS"
                ROS_BACKUP_DONE=1
            fi
        }

        log "补齐 ROS 配置（保留已有值）..."
        CURRENT_DB_PATH="$(grep -E '^DB_PATH=' "$ROS_ENV" 2>/dev/null | tail -1 | cut -d= -f2- || true)"
        TARGET_DB_PATH="$PROJECT_ROOT/ros_database.db"
        if [ "$CURRENT_DB_PATH" != "$TARGET_DB_PATH" ]; then
            backup_ros_env
            if grep -q '^DB_PATH=' "$ROS_ENV"; then
                run sed -i "s|^DB_PATH=.*|DB_PATH=$TARGET_DB_PATH|" "$ROS_ENV"
            else
                run_shell "printf '\nDB_PATH=%s\n' '$TARGET_DB_PATH' >> '$ROS_ENV'"
            fi
        fi

        CURRENT_ZLG="$(grep -E '^ZLG_LIBUSB_PATH=' "$ROS_ENV" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '\r' || true)"
        if [ -z "$CURRENT_ZLG" ] || [ ! -f "$CURRENT_ZLG" ]; then
            backup_ros_env
            if grep -q '^ZLG_LIBUSB_PATH=' "$ROS_ENV"; then
                run sed -i "s|^ZLG_LIBUSB_PATH=.*|ZLG_LIBUSB_PATH=/usr/local/lib/libusbcan.so|" "$ROS_ENV"
            else
                run_shell "printf '\nZLG_LIBUSB_PATH=/usr/local/lib/libusbcan.so\n' >> '$ROS_ENV'"
            fi
        fi
        if ! grep -q '^CAN_INTERFACE=' "$ROS_ENV"; then
            backup_ros_env
            run_shell "printf '\nCAN_INTERFACE=zlg\n' >> '$ROS_ENV'"
        fi
        if ! grep -q '^CAN_CHANNEL=' "$ROS_ENV"; then
            backup_ros_env
            run_shell "printf '\nCAN_CHANNEL=0\n' >> '$ROS_ENV'"
        fi
        if ! grep -q '^CAN_BITRATE=' "$ROS_ENV"; then
            backup_ros_env
            run_shell "printf '\nCAN_BITRATE=500000\n' >> '$ROS_ENV'"
        fi

        CAN_IFACE="$(grep -E '^CAN_INTERFACE=' "$ROS_ENV" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d ' ' || true)"
        if [ "${CAN_IFACE:-zlg}" = "zlg" ]; then
            if [ -f "$SCRIPT_DIR/install_zlg_can.sh" ]; then
                log "安装 ZLG USBCAN-II 驱动..."
                if [ "$DRY_RUN" -eq 1 ]; then
                    run bash "$SCRIPT_DIR/install_zlg_can.sh" --dry-run
                else
                    run sudo bash "$SCRIPT_DIR/install_zlg_can.sh"
                fi
            else
                warn "缺少 deploy/install_zlg_can.sh，跳过驱动安装。"
            fi
        else
            warn "CAN_INTERFACE=$CAN_IFACE，不是 zlg，跳过 ZLG 驱动安装。"
        fi
    else
        warn "缺少 rob_arm.env，跳过 ROS 配置与驱动安装。"
    fi
fi

# ---------------- 8. 结果与检查 ----------------
if [ "$DRY_RUN" -eq 1 ]; then
    log "预览结束，未修改系统。"
    exit 0
fi

log "安装步骤完成。"
if [ -f "$SCRIPT_DIR/check_deploy.sh" ]; then
    log "运行部署检查..."
    CHECK_ARGS=()
    if [ "$MOCK_ONLY" -eq 1 ]; then
        CHECK_ARGS+=(--mock-only)
    fi
    bash "$SCRIPT_DIR/check_deploy.sh" "${CHECK_ARGS[@]}" || warn "检查脚本存在未通过项，请按输出处理。"
fi

cat <<EOF

============================================================
安装完成。启动顺序：

1) ROS（接真机时）：
   source /opt/ros/noetic/setup.bash
   source ${WORKSPACE_ROOT:-$HOME/robot_ws}/devel/setup.bash
   roslaunch robot_control_backend ros_robot.launch

2) 后端：
   cd $PROJECT_ROOT/mes_web/ros_mes_hou
   source venv/bin/activate
   python start_server.py

3) 前端：
   cd $PROJECT_ROOT/mes_web/ros_mes_front
   npm run dev -- --host 0.0.0.0

浏览器：http://127.0.0.1:5173
默认账号：admin / 123456（仅新建数据库时有效）
============================================================
EOF
