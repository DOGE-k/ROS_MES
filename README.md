# ROS_MES 智能制造执行系统

面向自适应工装产线的 MES 系统：Web 前端下发任务与微调指令，FastAPI 后端经 rosbridge 与 ROS 机器人控制节点通信，实现图纸管理、工作流编排、任务调度、机械臂姿态微调与压力/陀螺仪实时监控。

## 系统架构

```
┌────────────────────┐   HTTP / WebSocket (/api/*)   ┌──────────────────┐   rosbridge (:9010)   ┌───────────────────────┐
│  ros_mes_front     │ ────────────────────────────► │   ros_mes_hou    │ ────────────────────► │ robot_control_backend │
│  Vue3 + TS + EP    │ ◄──────────────────────────── │  FastAPI + SQLite│ ◄──────────────────── │  ROS 机器人控制节点   │
│  dev 端口 5173     │                               │   端口 8000      │                       │  机械臂 CAN 控制      │
└────────────────────┘                               └──────────────────┘                       └───────────────────────┘
```

| 目录 | 说明 | 技术栈 |
|---|---|---|
| `mes_web/` | 前后端总目录 | — |
| `mes_web/docs/` | 前后端专属接口、更新记录与接入状态；入口见 `mes_web/AGENTS.md` | — |
| `mes_web/ros_mes_front/` | Web 前端 | Vue 3 · TypeScript · Vite · Element Plus · Pinia |
| `mes_web/ros_mes_hou/` | 业务后端 | FastAPI · SQLAlchemy · SQLite · rosbridge-websocket |
| `robot_control_backend/` | ROS 机器人控制节点 | ROS · Python |
| `docs/` | 双方共享的接口契约、ROS/CAN 资料、跨系统报告及整仓历史归档 | — |
| `deploy/` | 部署配置与说明（见 `deploy/README_DEPLOY.md`） | — |
| `sqlite_create.py` | 数据库初始化脚本（建表 + 种子数据，生成仓库根 `ros_database.db`） | Python · SQLite |

> 后端内置 ROS1/ROS2 适配层：`backend.env` 中 `ROS_VERSION=1`（默认）或 `2` 切换，协议差异集中在 `mes_web/ros_mes_hou/app/ros/profile.py`。

## 快速启动

Windows 本地已验证环境：标准 Python 3.12、Node.js 20。创建虚拟环境时使用 `py -3.12`，避免 PATH 中的 MSYS2 Python 被选中。

**1. 首次准备后端环境**（项目根目录执行；已有可用虚拟环境时无需重复创建）

```powershell
cd mes_web\ros_mes_hou
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
cd ..\..
```

**2. 首次初始化数据库**（项目根目录执行，含种子数据；已有数据库时无需重复执行）

```powershell
.\mes_web\ros_mes_hou\venv\Scripts\python.exe .\sqlite_create.py
```

后端启动时会创建缺失的表，初始数据由仓库根的 `sqlite_create.py` 插入（数据库固定生成在仓库根，与后端 `DATABASE_URL` 默认值一致）。

**3. 日常启动后端**（终端一，端口 8000）

```powershell
cd mes_web\ros_mes_hou
.\venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload --port 8000
```

**4. 日常启动前端**（终端二，从项目根目录执行；端口 5173，`/api` 自动代理到 127.0.0.1:8000）

```bash
cd mes_web/ros_mes_front
npm install                   # 首次安装或依赖变更后执行
npm run dev
```

**5. 登录**：浏览器访问 http://localhost:5173 ，默认管理员 `admin / 123456`（⚠ 比赛部署前务必修改密码）。

> 无 ROS 环境调试：前端 `.env.development` 中 `VITE_DEBUG_NO_ROS=true` 时，模块下发/微调等走前端模拟，无需机器人在线。

## 文档索引

| 文档 | 说明 |
|---|---|
| [mes_web/AGENTS.md](mes_web/AGENTS.md) | **前后端开发入口**：任务定位、维护范围、按需阅读与验证；规则只适用于前后端任务 |
| [前后端接口字段文档](mes_web/docs/ROS_MES_前后端接口字段文档.md) | REST、前后端 WebSocket、数据库、鉴权与页面流程 |
| [前后端改动记录](mes_web/docs/ROS_MES_前后端改动记录.md) | 前后端更新和验证结果的唯一日志 |
| [后端与 ROS 接口对接状态清单](mes_web/docs/后端与ROS接口对接状态清单.md) | 本侧接入/使用状态、证据、缺口；不替代共享协议 |
| [前后端命名规范](mes_web/docs/ROS_MES_前后端命名规范.md) | 前后端新代码的兼容及命名约定 |
| [三轴版 V2.1 共享契约](docs/ROS_MES_前后端ROS接口清单_三轴版_V2.1.md) | 双方对接的话题、消息、编号和握手约定 |
| [模块确认命令](docs/机械臂模块确认命令.md)、[保护事件说明](docs/模块确认与保护事件技术说明.md) | ROS/固件及 CAN 协议资料 |
| [全流程测试报告](docs/ROS_MES_全流程测试报告.md)、[真机 CAN 联调记录](docs/can_real_device_debug_report.md) | 跨系统历史证据，保留各自测试日期与环境 |
| `mes_web/docs/archive/` | 前后端历史适配、审查和 UI 原型 |
| `docs/archive/` | 整仓 V1.0 代码快照（包含 ROS 与部署内容），继续保留共享归档 |

## 团队分工

本仓库由团队共同维护，按模块分工协作：

- **前后端开发**：负责 `mes_web/ros_mes_front/` 与 `mes_web/ros_mes_hou/` 的页面交互、业务接口、数据库及与 ROS 的通信对接。
- **机器人控制开发**：负责 `robot_control_backend/` 的 ROS 节点、机械臂控制、CAN 通信与消息定义。
- **联调与接口约定**：双方共用根 `docs/` 的三轴版契约及 ROS/CAN 资料；前后端业务接口和本侧接入状态维护在 `mes_web/docs/`。涉及共享话题、消息字段或协议的变更，由相关模块负责人协同确认。各模块入口说明其任务范围，不替代其他团队的开发规则。
