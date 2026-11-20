# ROS MES 部署指南（V1.1）

> 版本：**V1.1**（2026-11-20）
> 适用源码：当前 `robot_control_backend/`（ROS1 Noetic）+ `mes_web/`（FastAPI + Vue3）
> V1.0 部署文档（2026-11-02）对应串口/CH340 旧链路，已废止；请以本文为准。
> 新环境逐项验收请使用：[新环境部署检查清单 V1.1](DEPLOY_CHECKLIST_V1.1.md)。

---

## 0. V1.1 相对 V1.0 的变更

| 项目 | V1.0 | V1.1（当前源码） |
|---|---|---|
| 下位机链路 | 串口 / CH340 | **CAN 2.0B / 500kbps / ZLG USBCAN-II** |
| 模块寻址 | 业务模块号直连 | 会话式绑定 `module_id → SEG/ARM`，下发 `position=[100, seg, arm]` |
| 三轴下发 | 绝对角度/串口增量 | **相对增量**，轴节点做软件限位 |
| 伸缩范围 | 0~30mm | **-20 ~ +20mm**（`TELESCOPIC_MIN_MM/MAX_MM`） |
| 反馈话题 | 8 路 | **13 路**（新增状态、到位、停止、故障、限位等） |
| 轴状态 | 依赖固件周期状态字 | `axis_status_aggregator.py` 绑定后按 5Hz 推导发布，空闲按 2Hz 补发位置 |
| 人工校零 | 无 ROS 侧同步 | `POST /finetuning/config` + `/control/axis_zero` 同步三轴软件基准 |
| 微调下发 | 单轴同步接口 | 批次接口 `/control/finetuning/batches` + 发送前检查 + 五段值 |
| 前端无 ROS 调试 | `VITE_DEBUG_NO_ROS=true` | 已废弃；改「个人中心 → 调试设置」由后端运行期配置控制 |
| rosbridge | 需单独 launch | 已包含在 `ros_robot.launch`，端口 **9010** |
| 后端 Python | 3.8 可用 | **必须 3.10+**（与 ROS 的 3.8 隔离） |
| ROS2 | 待移植 | `ros2_robot_control_backend/` 为迁移副本，**现场仍用 ROS1 目录** |

---

## 1. 系统组成与端口

| 组件 | 目录 | 运行环境 | 端口 |
|---|---|---|---|
| ROS 控制节点 | `robot_control_backend/` | Ubuntu 20.04 + ROS Noetic | 11311 / rosbridge **9010** / 点云 Flask **5000** |
| 后端 | `mes_web/ros_mes_hou/` | Python **3.10+** | **8000** |
| 前端 | `mes_web/ros_mes_front/` | Node 18+（推荐 20 LTS） | 开发 **5173** / 生产 80 |
| CAN 适配器 | — | ZLG USBCAN-II + `libusbcan.so` | USB，500000bps |

运行 `ros_robot.launch` 会同时拉起：模块确认、逆解、三轴节点、轴状态聚合、硬件桥、点云处理（Flask 5000）和 rosbridge（9010）。**不需要再单独启动 rosbridge**。

> ROS 节点必须在 Ubuntu 上跑；前端和后端可以放在 Windows/macOS，通过 9010/5000 访问 ROS 机器。

---

## 2. 三种部署拓扑

### 2.1 单机全量（推荐）

一台 Ubuntu 20.04：ROS + 后端 + 前端全部本机。`ROSBRIDGE_URL`、`POINTCLOUD_VIEW_BASE_URL`、`VITE_API_TARGET` 都用 `127.0.0.1`。

### 2.2 双机：Web 在前端机，ROS 在机器人机

- 机器人机（Ubuntu）：只跑 `roslaunch robot_control_backend ros_robot.launch`。
- Web 机（Windows/Ubuntu）：跑后端 + 前端。
- 后端 `.env`：
  ```ini
  ROSBRIDGE_URL=ws://<ROS_IP>:9010
  POINTCLOUD_VIEW_BASE_URL=http://<ROS_IP>:5000
  ```
- 前端 `.env.development`：`VITE_API_TARGET=http://<后端IP>:8000`。
- 放行端口：9010、5000、8000、5173（或 80）。

### 2.3 无 ROS 硬件演示

只启动后端 + 前端，在「个人中心 → 调试设置 → ROS 通信与微调」选择模拟连接（`ros_mode=mock`、`drawing_mode=mock`）。不需要 ROS、CAN 适配器和机械臂，适合第一次接手验收页面。

---

## 3. 交付包

在现有机器打包，排除环境目录和缓存：

```bash
cd /home/yang/workspaces/robot_ws/src
rsync -av \
  --exclude 'venv' --exclude 'node_modules' --exclude '__pycache__' \
  --exclude '*.pyc' --exclude '.git' --exclude 'logs' \
  ROS_MES/ 用户名@目标IP:~/robot_ws/src/ROS_MES/
```

- **建议带上** `ros_database.db`：账号、图纸、微调记录都在里面。
- 不带数据库时，新机器首次执行 `sqlite_create.py` 初始化（默认账号 `admin / 123456`）。
- **不要带** `mes_web/ros_mes_hou/venv`、`mes_web/ros_mes_front/node_modules`，换机后重装。
- 交付后修改 `SECRET_KEY` 和默认管理员密码。

---

## 4. 前置环境

### 4.1 Ubuntu + ROS Noetic

```bash
sudo apt update
sudo apt install -y \
  ros-noetic-ros-base ros-noetic-message-generation ros-noetic-rosbridge-server \
  python3-pip python3-serial
python3 -m pip install --user -r ~/robot_ws/src/ROS_MES/deploy/config/ros_requirements.txt
```

要求：

- Ubuntu **20.04**（Noetic 官方支持）。
- `rosbridge_wrapper.py` 里写死了 `/opt/ros/noetic`，不要用 Melodic。
- ROS 节点用系统 Python 3.8；`open3d` 在 3.8 上建议 `0.15.2`（模板已按版本区分）。

### 4.2 后端 Python 3.10+

Noetic 的系统 Python 3.8 **不能**跑当前 FastAPI 依赖。用 Conda 或 deadsnakes 单独建环境，不要替换系统 Python：

```bash
# 方式 A：Conda
conda create -n mes python=3.11 -y

# 方式 B：deadsnakes
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt install -y python3.11 python3.11-venv
```

### 4.3 Node.js

安装 Node 20 LTS（`node -v` 应 ≥ 18）：

```bash
node -v
npm -v
```

### 4.4 ZLG USBCAN-II

1. 把 `libusbcan.so` 放到固定位置并刷新缓存：

   ```bash
   sudo cp libusbcan.so /usr/local/lib/libusbcan.so
   sudo ldconfig
   ```

2. 给适配器 USB 权限（USBCAN-II 为 `0471:1200`）：

   ```bash
   echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="0471", ATTR{idProduct}=="1200", MODE="0666"' \
     | sudo tee /etc/udev/rules.d/99-zlg-usbcan.rules
   sudo udevadm control --reload-rules && sudo udevadm trigger
   ```

3. 确认设备存在：

   ```bash
   lsusb | grep 0471
   ```

> 适配器优先插主板直出的 USB2.0 口，不要用外接 HUB。USB 端口卡死时换物理端口重新插拔。

---

## 5. 配置

### 5.1 ROS：`robot_control_backend/rob_arm.env`

可以直接用 `deploy/config/rob_arm.env` 覆盖现场文件，然后修改以下必改项：

| 键 | 示例 | 说明 |
|---|---|---|
| `DB_PATH` | `/home/新用户/robot_ws/src/ROS_MES/ros_database.db` | **必须改**；绝对路径，且与后端同一个库 |
| `CAN_INTERFACE` | `zlg` | ZLG 适配器固定 `zlg`；SocketCAN 才用 `socketcan` |
| `CAN_CHANNEL` | `0` | 适配器通道 |
| `CAN_BITRATE` | `500000` | 固定 500kbps |
| `ZLG_LIBUSB_PATH` | `/usr/local/lib/libusbcan.so` | **必须改**；也可在 shell 里 export |
| `CAN_DEFAULT_SEG` | `0` | 未绑定模块时的回退 SEG，单工位填 0 |

其余限位、话题、聚合节点参数保持默认即可。重点确认：

```ini
ROTATION_MIN_ANGLE=-180.0
ROTATION_MAX_ANGLE=180.0
SWING_MIN_ANGLE=-15.0
MAX_SWING_ANGLE=15.0
TELESCOPIC_MIN_MM=-20.0
TELESCOPIC_MAX_MM=20.0
```

### 5.2 后端：`mes_web/ros_mes_hou/.env`

```bash
cd ~/robot_ws/src/ROS_MES/mes_web/ros_mes_hou
cp ../../deploy/config/backend.env .env
```

| 键 | 必改 | 说明 |
|---|---|---|
| `DATABASE_URL` | 视情况 | 默认 `sqlite:///../../ros_database.db`，相对**启动目录**解析；必须在 `mes_web/ros_mes_hou` 下启动 |
| `ROSBRIDGE_URL` | 跨机必改 | `ws://127.0.0.1:9010` 或 `ws://<ROS_IP>:9010` |
| `POINTCLOUD_VIEW_BASE_URL` | 跨机必改 | `http://127.0.0.1:5000` 或 `http://<ROS_IP>:5000` |
| `ROS_MODULE_SEG_MAP` | **必改** | 业务模块号→SEG，如 `{"17": 0}`；不配置则模块确认拒绝下发 |
| `SECRET_KEY` | **必改** | 用 `python -c "import secrets; print(secrets.token_hex(32))"` 生成 |
| `ROS_VERSION` | 保持 `1` | ROS2 迁移完成前不要改 |
| `BACKEND_CORS_ORIGINS` | 生产必改 | 生产不要用 `*`，填前端地址 |

### 5.3 前端：`mes_web/ros_mes_front/.env.development`

```bash
cd ~/robot_ws/src/ROS_MES/mes_web/ros_mes_front
cp ../../deploy/config/frontend.env .env.development
```

只需确认：

```ini
VITE_API_TARGET=http://127.0.0.1:8000
VITE_USE_MOCK=false
```

跨机时把 `VITE_API_TARGET` 改成后端 IP。V1.0 的 `VITE_DEBUG_NO_ROS`、`VITE_WS_*`、`VITE_ROSBRIDGE_URL` 已废弃，不要再用。

### 5.4 路径一致性

- ROS 的 `DB_PATH` 必须与后端 `DATABASE_URL` 指向**同一个** `ros_database.db`。
- 仓库目录换位置后，必须同步改 `DB_PATH`、`DATABASE_URL`（绝对路径时）并重新 `catkin_make`。
- `roslaunch` 会把 cwd 切到 `~/.ros`，所以 ROS 侧数据库路径必须写绝对路径。

---

## 6. 安装

### 6.1 编译 ROS 工作空间

```bash
cd ~/robot_ws
catkin_make
source devel/setup.bash
```

把下面两行加入 `~/.bashrc`，避免每次手动 source：

```bash
source /opt/ros/noetic/setup.bash
source ~/robot_ws/devel/setup.bash
```

### 6.2 后端

```bash
cd ~/robot_ws/src/ROS_MES/mes_web/ros_mes_hou

# 确认当前 python 是 3.10+（Conda 环境需先 conda activate mes）
# deadsnakes 方案若 python 仍指向 3.8，改用：python3.11 -m venv venv
python --version
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate
```

初始化数据库（**仅首次、且没有带现有 `ros_database.db` 时执行**）：

```bash
cd ~/robot_ws/src/ROS_MES
mes_web/ros_mes_hou/venv/bin/python sqlite_create.py
```

> 已有数据库时不要再跑初始化，避免影响现有账号和数据。

### 6.3 前端

```bash
cd ~/robot_ws/src/ROS_MES/mes_web/ros_mes_front
npm install
```

### 6.4 只在 Windows 跑前后端

可以直接执行仓库内的一键脚本（仅处理前端 + 后端，不处理 ROS）：

```powershell
cd ROS_MES\deploy
.\deploy_windows.ps1
```

脚本要求 Python **3.10+** 和 Node 18+。ROS 部分仍需在 Ubuntu 上按 4.1、6.1 部署。

---

## 7. 启动

### 终端 1：ROS

```bash
source /opt/ros/noetic/setup.bash
source ~/robot_ws/devel/setup.bash
roslaunch robot_control_backend ros_robot.launch
```

该 launch 会启动全部节点、点云 Flask（5000）和 rosbridge（9010）。若 9010 未监听，先看该终端是否有 `rosbridge` 启动失败日志。

### 终端 2：后端

```bash
cd ~/robot_ws/src/ROS_MES/mes_web/ros_mes_hou
source venv/bin/activate
python start_server.py
# 等价于：uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 终端 3：前端（开发模式）

```bash
cd ~/robot_ws/src/ROS_MES/mes_web/ros_mes_front
npm run dev -- --host 0.0.0.0
```

浏览器打开 `http://<前端机IP>:5173`，默认账号 `admin / 123456`。

> **不要**在 ROS 终端里激活后端的 venv：后端 venv 没有 `rospy`，会导致 ROS 节点导入失败。ROS 和后端始终用各自的 Python。

---

## 8. 部署后验证

### 8.1 基础链路

```bash
# ROS 节点与话题
rostopic list | grep -E 'axis_status|feedback|module_status|axis_zero'

# 聚合节点绑定后应约 5Hz；未绑定模块时没有输出属正常
rostopic hz /hardware/axis_status

# 后端
curl -s http://127.0.0.1:8000/docs >/dev/null && echo "backend OK"

# 端口
ss -lntp | grep -E '9010|5000|8000|5173'

# CAN 适配器
lsusb | grep 0471
```

### 8.2 页面顺序

1. 登录，进入「个人中心 → 调试设置」，确认为真实 ROS 连接。
2. 模块管理：确认模块。**模块已绑定时上电不会广播 UID，需要给模块断电重启**。
3. 上传图纸，确认三视图（5000 端口）。
4. 微调页：确认三轴有效空闲状态，再下发小增量。
5. 检查批次结果五段值与到位事件。

### 8.3 真机首轮检查

- 轴 1（旋转）历史上存在“指令被接受但电机不动作”的硬件问题，首轮先单轴小增量验证。
- 摆动轴上行软限位约 2.65°，到限位后继续正向指令不会产生位移。
- 伸缩轴到机械限位后继续同方向下发会触发驱动器空转并打满 CAN，必须立即发单轴停止。
- 禁止下发全 0 急停指令，会锁死系统，只能重新上电恢复。

---

## 9. 生产部署（可选）

前端构建：

```bash
cd ~/robot_ws/src/ROS_MES/mes_web/ros_mes_front
npm run build
# 产物在 dist/
```

Nginx 最小配置（同机）：

```nginx
server {
    listen 80;
    root /home/新用户/robot_ws/src/ROS_MES/mes_web/ros_mes_front/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

后端生产启动：

```bash
cd ~/robot_ws/src/ROS_MES/mes_web/ros_mes_hou
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

`WORKERS` 保持 1：批次状态、停止锁存等运行态在进程内维护，多 worker 会不一致。

---

## 10. 跨机网络

| 端口 | 所在机器 | 用途 |
|---|---|---|
| 9010 | ROS 机 | rosbridge WebSocket（后端连接） |
| 5000 | ROS 机 | 点云三视图 Flask（后端代理） |
| 8000 | Web 机 | FastAPI |
| 5173 / 80 | Web 机 | 前端 |

需要同步修改：

- 后端 `.env`：`ROSBRIDGE_URL`、`POINTCLOUD_VIEW_BASE_URL`。
- 前端 `.env.development`：`VITE_API_TARGET`。
- 防火墙/安全组放行上述端口。
- 生产环境把 `BACKEND_CORS_ORIGINS` 改成实际前端地址。

---

## 11. 常见故障

| 现象 | 原因 | 处理 |
|---|---|---|
| ROS 节点启动即报 `KeyError: 'DB_PATH'` | `rob_arm.env` 缺少 `DB_PATH` | 补上绝对路径；不要用旧版模板 |
| 后端启动报 `ModuleNotFoundError` / pydantic 版本错误 | 用了 Python 3.8 | 用 3.10+ 的 venv/conda |
| ROS 节点报 `No module named rospy` | 在 ROS 终端激活了后端 venv | 退出 venv，重新 source ROS |
| `VCI_OpenDevice` 失败 | `libusbcan.so` 路径错/无权限/USB 端口异常 | 改 `ZLG_LIBUSB_PATH`、`ldconfig`、udev 规则、换 USB 口 |
| 后端起不来但 8000 被占用 | 旧进程未退出 | `ss -lntp \| grep 8000` 后结束旧进程 |
| 前端请求 404/跨域 | `VITE_API_TARGET` 或 CORS 错 | 改成后端实际 IP，配置 `BACKEND_CORS_ORIGINS` |
| rosbridge 连接失败 | 9010 未启动/防火墙 | 看 roslaunch 日志，放行 9010 |
| 模块确认 502 | 模块已绑定未广播 UID / SEG 映射缺失 | 模块断电重启；配置 `ROS_MODULE_SEG_MAP` |
| 发送前检查一直 `blocked` | 没有新鲜 `axis_status` / `base_valid=0` | 确认聚合节点在跑、模块已绑定、无故障/限位/急停 |
| 伸缩杆不动或行程极小 | 到机械限位 / 未在已知位置归零 | 先反向退出限位；校零后确认基准 |
| 点云三视图打不开 | 5000 不通/ROS 机 IP 错/open3d 未装 | 改 `POINTCLOUD_VIEW_BASE_URL`，检查 ROS 日志 |
| 数据库数据对不上 | ROS 与后端指向了不同 db | 统一 `DB_PATH` 与 `DATABASE_URL` |

---

## 12. 升级与运维

- **升级顺序**：停前端 → 停后端 → 停 roslaunch → 备份 `ros_database.db` → 替换代码 → 处理配置差异 → `catkin_make` → 按第 7 节顺序启动。
- **配置差异**：每次升级对比 `robot_control_backend/rob_arm.env` 与 `deploy/config/rob_arm.env`，不要直接覆盖现场配置。
- **日志**：roslaunch 终端输出各节点日志；后端 uvicorn 标准输出；前端浏览器控制台。
- **备份**：至少备份 `ros_database.db`、`mes_web/ros_mes_hou/app/uploads/`（如有）和现场 `rob_arm.env`、后端 `.env`。

---

## 13. 文件索引

| 文件 | 用途 |
|---|---|
| `deploy/config/rob_arm.env` | ROS 硬件/运动参数模板（V1.1） |
| `deploy/config/backend.env` | 后端 `.env` 模板 |
| `deploy/config/frontend.env` | 前端 `.env.development` 模板 |
| `deploy/config/ros_requirements.txt` | ROS 节点 Python 依赖 |
| `deploy/deploy_windows.ps1` | Windows 前后端一键部署（不含 ROS） |
| `deploy/DEPLOY_CHECKLIST_V1.1.md` | 新环境部署逐项检查清单 |
| `robot_control_backend/launch/ros_robot.launch` | 真机全量启动入口 |
| `mes_web/ros_mes_hou/requirements.txt` | 后端依赖 |
| `sqlite_create.py` | 首次数据库初始化 |

更详细的接口与话题定义见 [三轴版 V2.1 契约](../docs/ROS_MES_前后端ROS接口清单_三轴版_V2.1.md)，端到端流程见 [前端图纸到微调下发全流程说明](../docs/前端图纸到微调下发全流程说明.md)。
