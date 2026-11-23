#!/usr/bin/env bash
# ======================================================================
# start_ros.sh  —  ROS MES 启动包装
#   1) 自动加载 ROS 环境与工作空间（若尚未 source）
#   2) 清理 30 天前的 ROS 日志（失败不阻断启动）
#   3) 启动 ros_robot.launch
# 额外参数会透传给 roslaunch（如 --screen 已在 launch 内设置）。
# ======================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 1. 加载 ROS 发行版环境（若尚未加载）
if [[ -z "${ROS_DISTRO:-}" ]]; then
  for f in /opt/ros/noetic/setup.bash /opt/ros/melodic/setup.bash /opt/ros/kinetic/setup.bash; do
    if [[ -f "$f" ]]; then
      # shellcheck disable=SC1090
      source "$f"
      break
    fi
  done
fi

# 2. 加载工作空间：从脚本所在目录向上查找 devel/ 或 install/
ws="$SCRIPT_DIR"
ws_found=0
while [[ "$ws" != "/" ]]; do
  for f in "$ws/devel/setup.bash" "$ws/install/setup.bash"; do
    if [[ -f "$f" ]]; then
      # shellcheck disable=SC1090
      source "$f"
      ws_found=1
      break 2
    fi
  done
  ws="$(dirname "$ws")"
done
if [[ $ws_found -eq 0 ]]; then
  echo "[start_ros][WARN] 未找到工作空间 devel/setup.bash，请先手动 catkin_make 并 source" >&2
fi

# 3. 清理 30 天前日志（清理失败不阻断 ROS 启动）
bash "$SCRIPT_DIR/scripts/clean_ros_logs.sh" --days 30 || true

# 4. 启动
exec roslaunch robot_control_backend ros_robot.launch "$@"
