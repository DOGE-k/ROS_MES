# ROS MES 部署指南

本目录包含 ROS MES 系统部署所需的配置文件和脚本。

## 目录结构

```
deploy/
├─ deploy_windows.ps1      # Windows 一键部署脚本（前端 + 后端）
├─ README_DEPLOY.md        # 本文档
└─ config/
   ├─ backend.env          # 后端环境变量配置
   ├─ frontend.env         # 前端环境变量配置
   ├─ rob_arm.env          # ROS 机器人控制参数配置
   └─ ros_requirements.txt # ROS Python 依赖包清单
```

## 系统组成

ROS MES 由三部分组成，部署方式各有不同：

| 组件 | 推荐系统 | 核心技术 |
|------|---------|---------|
| 前端 (ros_mes_front) | Windows/Linux/macOS | Vue 3 + Vite |
| 后端 (ros_mes_hou) | Windows/Linux/macOS | FastAPI + Python |
| 机器人控制 (robot_control_backend) | Ubuntu 20.04 | ROS Noetic + Python |

> **注意**：ROS 必须运行在 Ubuntu 系统上。前端和后端可以运行在 Windows 上，通过 rosbridge 与 ROS 通信。

---

## 一、Windows 快速部署（前端 + 后端）

### 前置要求

- **Node.js** 18.0 或更高版本
  - 下载：https://nodejs.org/
  - 验证：`node --version`
- **Python** 3.8 ~ 3.12
  - 下载：https://www.python.org/downloads/
  - 验证：`python --version`
  - 安装时勾选 "Add Python to PATH"

### 一键部署

1. 将整个 `ROS_MES` 项目复制到新电脑
2. 打开 PowerShell，进入 `deploy` 目录
3. 执行部署脚本：

```powershell
cd 项目路径\deploy
.\deploy_windows.ps1
```

脚本会自动完成：
- ✅ 检查 Node.js 和 Python 环境
- ✅ 部署配置文件
- ✅ 初始化 SQLite 数据库
- ✅ 创建 Python 虚拟环境并安装依赖
- ✅ 安装前端 npm 依赖

### 手动部署

如果脚本执行有问题，也可以按以下步骤手动操作：

#### 1. 配置文件

```powershell
# 复制后端配置
copy deploy\config\backend.env ROS_MES\ros_mes_hou\.env

# 复制前端配置
copy deploy\config\frontend.env ROS_MES\ros_mes_front\.env.development
```

#### 2. 初始化数据库

```powershell
cd ROS_MES
python sqlite_create.py
```

#### 3. 后端安装

```powershell
cd ROS_MES\ros_mes_hou

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
.\venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

#### 4. 前端安装

```powershell
cd ROS_MES\ros_mes_front
npm install
```

### 启动服务

```powershell
# 终端 1：启动后端
cd ROS_MES\ros_mes_hou
.\venv\Scripts\activate
uvicorn app.main:app --reload
# 访问 http://127.0.0.1:8000/docs 查看 API 文档

# 终端 2：启动前端
cd ROS_MES\ros_mes_front
npm run dev
# 访问 http://127.0.0.1:5173
```

### 默认账号

| 用户名 | 密码 | 角色 |
|--------|------|------|
| admin | 123456 | 管理员 |

---

## 二、ROS 环境部署（Ubuntu）

### 前置要求

- **Ubuntu 20.04**（推荐）或 Ubuntu 18.04
- **ROS Noetic**（Ubuntu 20.04）或 ROS Melodic（Ubuntu 18.04）
- **Python 3**（ROS Noetic 默认 Python 3）

### 1. 安装 ROS Noetic

```bash
# 配置软件源
sudo sh -c 'echo "deb http://packages.ros.org/ros/ubuntu $(lsb_release -sc) main" > /etc/apt/sources.list.d/ros-latest.list'

# 添加密钥
sudo apt-key adv --keyserver 'hkp://keyserver.ubuntu.com:80' --recv-key C1CF6E31E6BADE8868B172B4F42ED6FBAB17C654

# 更新软件包索引
sudo apt update

# 安装 ROS Noetic 完整版
sudo apt install ros-noetic-desktop-full -y

# 初始化 rosdep
sudo rosdep init
rosdep update

# 配置环境
echo "source /opt/ros/noetic/setup.bash" >> ~/.bashrc
source ~/.bashrc

# 验证
roscore
```

### 2. 安装 rosbridge

```bash
sudo apt install ros-noetic-rosbridge-server -y
```

### 3. 安装 Python 依赖

```bash
cd ROS_MES/robot_control_backend

# 安装系统依赖
sudo apt install python3-pip python3-serial -y

# 安装 Python 包
pip3 install -r ../../deploy/config/ros_requirements.txt
```

### 4. 部署配置文件

```bash
# 复制 ROS 环境变量配置
cp ../../deploy/config/rob_arm.env rob_arm.env
```

### 5. 创建 ROS 工作空间并编译

```bash
# 创建工作空间
mkdir -p ~/catkin_ws/src
cd ~/catkin_ws/src

# 将 robot_control_backend 链接或复制到 src 目录
ln -s /path/to/ROS_MES/robot_control_backend .

# 编译
cd ~/catkin_ws
catkin_make

# 配置环境
echo "source ~/catkin_ws/devel/setup.bash" >> ~/.bashrc
source ~/.bashrc
```

### 6. 启动 ROS 系统

```bash
# 终端 1：启动 ROS 核心
roscore

# 终端 2：启动 rosbridge（用于和后端通信）
roslaunch rosbridge_server rosbridge_websocket.launch

# 终端 3：启动所有机器人控制节点
roslaunch robot_control_backend ros_robot.launch
```

---

## 三、前后端 + ROS 联调

### 网络配置

假设 ROS 运行在 Ubuntu 机器（IP: 192.168.1.100），前端后端运行在 Windows 机器（IP: 192.168.1.200）：

1. **修改后端配置** (`ros_mes_hou/.env`)：
```
ROSBRIDGE_URL=ws://192.168.1.100:9010
```

2. **修改前端配置** (`ros_mes_front/.env.development`)：
```
VITE_API_TARGET=http://192.168.1.200:8000
VITE_DEBUG_NO_ROS=false
```

3. **确保防火墙开放端口**：
   - ROS: 11311 (roscore), 9010 (rosbridge)
   - 后端: 8000
   - 前端: 5173

### 启动顺序

1. 启动 ROS 核心和节点（Ubuntu）
2. 启动 rosbridge（Ubuntu）
3. 启动后端 FastAPI（Windows/Linux）
4. 启动前端开发服务器（Windows/Linux）

---

## 四、生产环境部署

### 前端构建

```bash
cd ros_mes_front
npm run build
# 产物在 dist/ 目录
```

将 `dist/` 目录部署到 Nginx 或其他静态文件服务器。

### 后端部署

使用 `uvicorn` 或 `gunicorn` 生产模式运行：

```bash
cd ros_mes_hou
.\venv\Scripts\activate

# 单进程
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 多进程（需要安装 gunicorn）
# pip install gunicorn
# gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

### Nginx 反向代理配置示例

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 前端静态文件
    location / {
        root /path/to/dist;
        try_files $uri $uri/ /index.html;
    }

    # 后端 API 代理
    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;

        # WebSocket 支持
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

---

## 五、常见问题

### Q: 启动后端提示 ModuleNotFoundError

A: 确保已激活虚拟环境并安装了依赖：
```powershell
cd ros_mes_hou
.\venv\Scripts\activate
pip install -r requirements.txt
```

### Q: 前端启动后接口请求 404

A: 检查 `.env.development` 中的 `VITE_API_TARGET` 是否指向正确的后端地址。

### Q: ROS 节点启动后无法通信

A: 检查以下几点：
1. `roscore` 是否正常运行
2. 话题名称是否与 `rob_arm.env` 中配置一致
3. ROS_MASTER_URI 环境变量是否正确
4. 防火墙是否开放了 11311 端口

### Q: rosbridge 连接失败

A: 确认 rosbridge 已启动并监听 9010 端口：
```bash
roslaunch rosbridge_server rosbridge_websocket.launch
# 默认端口 9090，如需修改：
# roslaunch rosbridge_server rosbridge_websocket.launch port:=9010
```

### Q: 串口无法打开（Windows）

A: 
1. 在设备管理器中确认串口号（如 COM3）
2. 修改 `rob_arm.env` 中的 `SERIAL_PORT=COM3`
3. 确认已安装 CH340/CP2102 等 USB 转串口驱动

---

## 六、配置文件说明

### backend.env

| 变量 | 说明 | 默认值 |
|------|------|--------|
| API_STR | API 前缀 | /api |
| DATABASE_URL | SQLite 数据库路径 | sqlite:///../ros_database.db |
| BACKEND_CORS_ORIGINS | CORS 允许的源 | * |
| ROSBRIDGE_URL | rosbridge WebSocket 地址 | ws://127.0.0.1:9010 |
| SECRET_KEY | JWT 密钥（务必修改） | 占位字符串 |
| ACCESS_TOKEN_EXPIRE_MINUTES | Token 过期时间（分钟） | 1440 |
| HOST | 监听地址 | 0.0.0.0 |
| PORT | 监听端口 | 8000 |

### frontend.env

| 变量 | 说明 | 默认值 |
|------|------|--------|
| VITE_API_TARGET | 后端 API 地址 | http://127.0.0.1:8000 |
| VITE_USE_MOCK | 使用 Mock 数据 | false |
| VITE_DEBUG_NO_ROS | 无 ROS 调试模式 | false |

### rob_arm.env

详细参数见配置文件注释，主要包括：
- 硬件转换参数（编码器分辨率、伸缩系数等）
- 编码器限位范围
- 模块和设备 ID 映射
- 串口配置
- ROS 话题名称映射
- 时序控制参数
- 点云处理参数
- IMU 陀螺仪参数
- 压力传感器参数

---

## 七、依赖包完整清单

### 前端 (npm)

**核心框架：**
- vue@^3.5.30 — 前端框架
- vue-router@^5.0.4 — 路由管理
- pinia@^3.0.4 — 状态管理
- typescript@~5.9.3 — 类型系统
- vite@^6.3.5 — 构建工具

**UI 组件：**
- element-plus@^2.13.6 — UI 组件库
- @element-plus/icons-vue@^2.3.2 — 图标库
- @vitejs/plugin-vue@^5.2.4 — Vue 插件

**工具库：**
- axios@^1.14.0 — HTTP 请求
- echarts@^6.0.0 — 数据可视化
- dayjs@^1.11.20 — 日期处理
- qs@^6.15.0 — 查询字符串解析

### 后端 (pip)

**Web 框架：**
- fastapi==0.136.1 — Web 框架
- uvicorn==0.46.0 — ASGI 服务器
- starlette==1.0.0 — 底层框架

**数据库：**
- SQLAlchemy==2.0.49 — ORM
- python-dotenv==1.2.2 — 环境变量加载

**认证安全：**
- python-jose==3.5.0 — JWT 处理
- passlib==1.7.4 — 密码哈希
- bcrypt==4.0.1 — bcrypt 后端
- cryptography==48.0.0 — 加密库

**数据校验：**
- pydantic==2.13.3 — 数据验证
- pydantic_core==2.46.3 — Pydantic 核心

**文件处理：**
- python-multipart==0.0.27 — 多部分表单解析

**实时通信：**
- websockets==15.0.1 — WebSocket 库

### ROS Python 依赖

- numpy — 数值计算
- scipy — 科学计算（KDTree 等）
- open3d — 点云处理
- pyserial — 串口通信
- python-can — CAN 总线通信（可选）
- flask — 内嵌 Web 服务
- python-dotenv — 环境变量加载
- websockets — WebSocket 通信
