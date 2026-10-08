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
| `ros_mes_front/` | Web 前端 | Vue 3 · TypeScript · Vite · Element Plus · Pinia |
| `ros_mes_hou/` | 业务后端 | FastAPI · SQLAlchemy · SQLite · rosbridge-websocket |
| `robot_control_backend/` | ROS 机器人控制节点 | ROS · Python |
| `deploy/` | 部署配置与说明（见 `deploy/README_DEPLOY.md`） | — |

## 快速启动

Windows 本地已验证环境：标准 Python 3.12、Node.js 20。创建虚拟环境时使用 `py -3.12`，避免 PATH 中的 MSYS2 Python 被选中。

**1. 首次准备后端环境**（项目根目录执行；已有可用虚拟环境时无需重复创建）

```powershell
cd ros_mes_hou
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
cd ..
```

**2. 首次初始化数据库**（项目根目录执行，含种子数据；已有数据库时无需重复执行）

```powershell
.\ros_mes_hou\venv\Scripts\python.exe .\sqlite_create.py
```

后端启动时会创建缺失的表，初始数据由 `sqlite_create.py` 插入。

**3. 日常启动后端**（终端一，端口 8000）

```powershell
cd ros_mes_hou
.\venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload --port 8000
```

**4. 日常启动前端**（终端二，从项目根目录执行；端口 5173，`/api` 自动代理到 127.0.0.1:8000）

```bash
cd ros_mes_front
npm install                   # 首次安装或依赖变更后执行
npm run dev
```

**5. 登录**：浏览器访问 http://localhost:5173 ，默认管理员 `admin / 123456`（⚠ 比赛部署前务必修改密码）。

> 无 ROS 环境调试：前端 `.env.development` 中 `VITE_DEBUG_NO_ROS=true` 时，模块下发/微调等走前端模拟，无需机器人在线。

## 文档索引

| 文档 | 说明 |
|---|---|
| [docs/ROS_MES_前后端接口字段文档.md](docs/ROS_MES_前后端接口字段文档.md) | 前后端全部 API、WebSocket、ROS 话题与消息字段（**对接必读**） |
| [docs/ROS_MES_前后端命名规范.md](docs/ROS_MES_前后端命名规范.md) | 前后端命名规范与速查卡（**新代码必读**） |
| [docs/ROS_MES_前后端改动记录.md](docs/ROS_MES_前后端改动记录.md) | 交接日志：边改边记录，含遗留问题与版本待办 |
| [docs/ROS_MES_前端V1.0到V1.1修改清单.md](docs/ROS_MES_前端V1.0到V1.1修改清单.md) | 前端 V1.1 适配执行记录（26 项核对结论） |
| `docs/archive/` | 已归档：优化建议报告、UI 改版原型、V1.0 版本代码备份 |

## 团队分工

本仓库由团队共同维护，按模块分工协作：

- **前后端开发**：负责 `ros_mes_front/` 与 `ros_mes_hou/` 的页面交互、业务接口、数据库及与 ROS 的通信对接。
- **机器人控制开发**：负责 `robot_control_backend/` 的 ROS 节点、机械臂控制、CAN 通信与消息定义。
- **联调与接口约定**：前后端与 ROS 端通过 `docs/ROS_MES_前后端接口字段文档.md` 中记录的话题与消息进行对接；涉及话题、消息字段或交互流程的变更，由相关模块负责人协同确认并同步更新文档。
