#!/usr/bin/env bash
# ============================================================
# ZLG USBCAN-II 驱动安装脚本（V1.1）
#
# 作用：
#   1. 按当前 CPU 架构选择官方预编译的 libusbcan.so；
#   2. 安装 libusb 运行库；
#   3. 拷贝 libusbcan.so 到 /usr/local/lib 并刷新缓存；
#   4. 写入 0471:1200 的 udev 权限规则；
#   5. 校验库能否加载、设备是否被识别。
#
# 注意：libusbcan.so 是 ZLG 官方预编译库，不是本项目编译生成的。
#       驱动包里的 Makefile 只编译 test/test_zuds 示例，不编译该库。
#
# 用法：
#   sudo bash deploy/install_zlg_can.sh
#   sudo bash deploy/install_zlg_can.sh --driver-dir /path/to/usbcan_ii_libusb_x64
#   bash deploy/install_zlg_can.sh --dry-run --driver-dir /path/to/usbcan_ii_libusb_x64
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

DRY_RUN=0
DRIVER_DIR=""

usage() {
    cat <<'EOF'
用法：
  sudo bash deploy/install_zlg_can.sh [--driver-dir <驱动目录>] [--dry-run]

参数：
  --driver-dir  包含 libusbcan.so 的目录。常见取值：
                .../usbcan_ii_libusb_251028/usbcan_ii_libusb_x64
                .../usbcan_ii_libusb_251028/usbcan_ii_libusb_x86
                .../usbcan_ii_libusb_251028/usbcan_ii_libusb_aarch64
  --dry-run     只打印将执行的命令，不修改系统（不需要 sudo）
  -h, --help    显示帮助
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --driver-dir)
            [ $# -ge 2 ] || { echo "错误：--driver-dir 缺少参数"; usage; exit 1; }
            DRIVER_DIR="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "错误：未知参数 $1"
            usage
            exit 1
            ;;
    esac
done

# ---- 1. 识别架构 ----
RAW_ARCH="$(uname -m)"
case "$RAW_ARCH" in
    x86_64|amd64)   ARCH="x64" ;;
    i386|i486|i586|i686) ARCH="x86" ;;
    aarch64|arm64)  ARCH="aarch64" ;;
    *)
        echo "错误：不支持的 CPU 架构：$RAW_ARCH"
        echo "请向 ZLG 获取对应架构的 libusbcan.so。"
        exit 1
        ;;
esac

if [ -z "$DRIVER_DIR" ]; then
    # 优先使用仓库内随附的驱动包
    DRIVER_DIR="$SCRIPT_DIR/drivers/usbcan_ii_libusb_251028/usbcan_ii_libusb_$ARCH"
    # 兼容旧布局：驱动包与 ROS_MES 同级
    if [ ! -f "$DRIVER_DIR/libusbcan.so" ]; then
        DRIVER_DIR="$PROJECT_ROOT/../can驱动/usbcan_ii_libusb_251028/usbcan_ii_libusb_$ARCH"
    fi
fi

LIB_FILE="$DRIVER_DIR/libusbcan.so"

if [ ! -f "$LIB_FILE" ]; then
    echo "错误：找不到驱动库：$LIB_FILE"
    echo ""
    echo "请确认："
    echo "  1. 仓库内驱动包存在：deploy/drivers/usbcan_ii_libusb_251028/；"
    echo "  2. 驱动包目录与当前架构匹配（$RAW_ARCH -> $ARCH）；"
    echo "  3. 或用 --driver-dir 指定实际目录。"
    echo ""
    echo "示例："
    echo "  sudo bash deploy/install_zlg_can.sh"
    echo "  sudo bash deploy/install_zlg_can.sh \\"
    echo "    --driver-dir deploy/drivers/usbcan_ii_libusb_251028/usbcan_ii_libusb_x64"
    exit 1
fi

# ---- 2. 校验库架构 ----
if command -v file >/dev/null 2>&1; then
    LIB_DESC="$(file -b "$LIB_FILE" 2>/dev/null || true)"
    echo "驱动库：$LIB_FILE"
    echo "文件类型：$LIB_DESC"
    case "$ARCH" in
        x64)     echo "$LIB_DESC" | grep -q "x86-64" || { echo "错误：该库不是 x86-64，架构不匹配"; exit 1; } ;;
        x86)     echo "$LIB_DESC" | grep -q "Intel 80386" || { echo "错误：该库不是 32 位 x86，架构不匹配"; exit 1; } ;;
        aarch64) echo "$LIB_DESC" | grep -q "ARM aarch64" || { echo "错误：该库不是 ARM aarch64，架构不匹配"; exit 1; } ;;
    esac
else
    echo "提示：未找到 file 命令，跳过架构校验。"
fi

if [ "$DRY_RUN" -eq 0 ] && [ "$EUID" -ne 0 ]; then
    echo "错误：安装需要 root 权限，请用 sudo 运行。"
    echo "预览可加 --dry-run，不需要 sudo。"
    exit 1
fi

run() {
    echo "+ $*"
    if [ "$DRY_RUN" -eq 0 ]; then
        "$@"
    fi
}

echo ""
echo "架构：$RAW_ARCH -> $ARCH"
echo "模式：$([ "$DRY_RUN" -eq 1 ] && echo '预览（不修改系统）' || echo '安装')"
echo ""

# ---- 3. 安装 libusb 运行库与 usbutils ----
if ! ldconfig -p 2>/dev/null | grep -q "libusb-1.0.so.0"; then
    run apt-get update
    run apt-get install -y libusb-1.0-0
fi
if ! command -v lsusb >/dev/null 2>&1; then
    run apt-get update
    run apt-get install -y usbutils
fi

# ---- 4. 安装 libusbcan.so ----
run install -m 0644 "$LIB_FILE" /usr/local/lib/libusbcan.so
run ldconfig

# ---- 5. 安装 udev 权限规则 ----
UDEV_RULE='SUBSYSTEM=="usb", ATTR{idVendor}=="0471", ATTR{idProduct}=="1200", MODE="0666"'
UDEV_FILE="/etc/udev/rules.d/99-zlg-usbcan.rules"

echo "+ 写入 $UDEV_FILE"
echo "  $UDEV_RULE"
if [ "$DRY_RUN" -eq 0 ]; then
    printf '%s\n' "$UDEV_RULE" > "$UDEV_FILE"
    chmod 0644 "$UDEV_FILE"
fi

run udevadm control --reload-rules
run udevadm trigger

# ---- 6. 校验 ----
if [ "$DRY_RUN" -eq 0 ]; then
    echo ""
    echo "校验库加载..."
    if python3 -c "import ctypes; ctypes.CDLL('/usr/local/lib/libusbcan.so'); print('libusbcan.so 加载成功')"; then
        :
    else
        echo "警告：libusbcan.so 加载失败，请检查 libusb-1.0 是否安装。"
    fi

    echo ""
    if lsusb 2>/dev/null | grep -q "0471:1200"; then
        echo "已识别 ZLG 设备："
        lsusb | grep "0471:1200"
    else
        echo "提示：当前未识别到 0471:1200 设备。"
        echo "     请重新插拔 USBCAN-II，优先使用主板直出的 USB2.0 口。"
    fi
fi

# ---- 7. 后续步骤 ----
STATUS_TEXT="安装完成"
if [ "$DRY_RUN" -eq 1 ]; then
    STATUS_TEXT="预览结束（未修改系统）"
fi

cat <<EOF

============================================================
$STATUS_TEXT。还需要做两件事：

1. 在 rob_arm.env 中设置（没有该行就新增）：
   ZLG_LIBUSB_PATH=/usr/local/lib/libusbcan.so

2. 重新插拔 USBCAN-II，然后检查：
   lsusb | grep 0471

如果之前启动过 ROS 节点，请重启 roslaunch。
============================================================
EOF
