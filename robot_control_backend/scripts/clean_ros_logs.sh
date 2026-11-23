#!/usr/bin/env bash
# ======================================================================
# clean_ros_logs.sh  —  清理 ROS MES 项目内 N 天前的 ROS 日志
#
# 仅针对 robot_control_backend 产生的 ROS 日志（ros_logs/、logs/），
# 不涉及前后端业务日志。按文件 mtime 判断过期，正在运行的节点日志
# 因 mtime 较新不会被误删；latest 指针与 roscore-*.pid 受保护。
#
# 用法：
#   bash scripts/clean_ros_logs.sh                # 清理 30 天前的日志
#   bash scripts/clean_ros_logs.sh --days 7       # 清理 7 天前
#   bash scripts/clean_ros_logs.sh --dry-run      # 仅预览，不实际删除
#   bash scripts/clean_ros_logs.sh --quiet        # 静默输出（适合 cron）
#   bash scripts/clean_ros_logs.sh --help         # 显示帮助
# ======================================================================
set -euo pipefail

DAYS=30
DRY_RUN=0
QUIET=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --days)
      [[ -n "${2:-}" ]] || { echo "[clean_logs] --days 需要一个数值参数" >&2; exit 1; }
      DAYS="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --quiet)   QUIET=1; shift ;;
    -h|--help)
      sed -n '2,15p' "$0"; exit 0 ;;
    *) echo "[clean_logs] 未知参数: $1（用 --help 查看用法）" >&2; exit 1 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROS_PKG_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"   # robot_control_backend/
ROS_LOG_DIR="$ROS_PKG_DIR/ros_logs"           # ROS 节点日志（每次 launch 生成 UUID 子目录）
ROSBRIDGE_LOG_DIR="$ROS_PKG_DIR/logs"         # rosbridge_websocket.log

log()  { [[ $QUIET -eq 0 ]] && echo "[clean_logs] $*"; }
warn() { echo "[clean_logs][WARN] $*" >&2; }

# 收集待扫描目录（存在才加入）
declare -a TARGET_DIRS=()
[[ -d "$ROS_LOG_DIR" ]] && TARGET_DIRS+=("$ROS_LOG_DIR")
[[ -d "$ROSBRIDGE_LOG_DIR" ]] && TARGET_DIRS+=("$ROSBRIDGE_LOG_DIR")
# ROS 全局默认日志目录：未设置 ROS_LOG_DIR 时 roscore/rosout 写这里
if [[ -d "${HOME}/.ros/log" ]]; then
  TARGET_DIRS+=("${HOME}/.ros/log")
fi

if [[ ${#TARGET_DIRS[@]} -eq 0 ]]; then
  warn "未发现任何 ROS 日志目录，退出"
  exit 0
fi

log "保留天数: ${DAYS}  模式: $([[ $DRY_RUN -eq 1 ]] && echo 预览 || echo 删除)"

total_files=0
total_dirs=0
total_bytes=0

for dir in "${TARGET_DIRS[@]}"; do
  log "扫描: $dir"

  # 1) 旧会话子目录（UUID 命名，整个目录一并删除）
  #    ! -name latest 保护 latest 指针；-maxdepth 1 只处理一级子目录
  while IFS= read -r -d '' d; do
    sz=$(du -sb "$d" 2>/dev/null | awk '{print $1}') || sz=0
    total_bytes=$((total_bytes + sz))
    total_dirs=$((total_dirs + 1))
    if [[ $DRY_RUN -eq 1 ]]; then
      log "  [预览] 将删除目录: ${d#$ROS_PKG_DIR/} ($((sz/1024)) KB)"
    else
      rm -rf "$d"
      log "  已删除目录: ${d#$ROS_PKG_DIR/} ($((sz/1024)) KB)"
    fi
  done < <(find "$dir" -mindepth 1 -maxdepth 1 -type d -mtime +"$DAYS" ! -name latest -print0 2>/dev/null)

  # 2) 目录根部散放的旧 .log 文件（latest、*.pid 不匹配 *.log，天然受保护）
  while IFS= read -r -d '' f; do
    sz=$(stat -c %s "$f" 2>/dev/null) || sz=0
    total_bytes=$((total_bytes + sz))
    total_files=$((total_files + 1))
    if [[ $DRY_RUN -eq 1 ]]; then
      log "  [预览] 将删除文件: ${f#$ROS_PKG_DIR/}"
    else
      rm -f "$f"
      log "  已删除文件: ${f#$ROS_PKG_DIR/}"
    fi
  done < <(find "$dir" -maxdepth 1 -type f -name "*.log" -mtime +"$DAYS" -print0 2>/dev/null)
done

if [[ $DRY_RUN -eq 1 ]]; then
  log "预览完成：将删除 ${total_files} 个文件、${total_dirs} 个目录，释放约 $((total_bytes/1024)) KB"
else
  log "清理完成：删除 ${total_files} 个文件、${total_dirs} 个目录，释放约 $((total_bytes/1024)) KB"
fi
