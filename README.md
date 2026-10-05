# ROS_MES 智能制造执行系统

面向自适应工装产线的 MES 系统：Web 前端下发任务与微调指令，FastAPI 后端经 rosbridge 与 ROS 机器人控制节点通信，实现图纸管理、工作流编排、任务调度、机械臂姿态微调与压力/陀螺仪实时监控。

## 系统架构

```
┌────────────────────┐   HTTP / WebSocket (/api/*)   ┌──────────────────┐   rosbridge (:9010)   ┌───────────────────────┐
│  ros_mes_front     │ ────────────────────────────► │   ros_mes_hou    │ ────────────────────► │ robot_control_backend │
│  Vue3 + TS + EP    │ ◄──────────────────────────── │  FastAPI + SQLite│ ◄──────────────────── │  ROS 节点（队友维护）  │
│  dev 端口 5173     │                               │   端口 8000      │                       │  机械臂 CAN 控制      │
└────────────────────┘                               └──────────────────┘                       └───────────────────────┘
```

| 目录 | 说明 | 技术栈 |
|---|---|---|
| `ros_mes_front/` | 前端（本侧维护） | Vue 3 · TypeScript · Vite · Element Plus · Pinia |
| `ros_mes_hou/` | 后端（本侧维护） | FastAPI · SQLAlchemy · SQLite · rosbridge-websocket |
| `robot_control_backend/` | ROS 机器人控制节点（**队友维护，本侧不修改**） | ROS · Python |
| `deploy/` | 部署配置与说明（见 `deploy/README_DEPLOY.md`） | — |

## 快速启动

环境要求：Python 3.10+、Node.js 18+。

**1. 初始化数据库**（项目根目录执行，含种子数据；后端启动时也会自动建表）

```bash
python sqlite_create.py        # 生成 ros_database.db
```

**2. 启动后端**（端口 8000）

```bash
cd ros_mes_hou
python -m venv venv
venv\Scripts\activate                  # Windows；Linux/macOS: source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**3. 启动前端**（端口 5173，`/api` 自动代理到 127.0.0.1:8000）

```bash
cd ros_mes_front
npm install
npm run dev
```

**4. 登录**：浏览器访问 http://localhost:5173 ，默认管理员 `admin / 123456`（⚠ 比赛部署前务必修改密码）。

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

- **软件前后端**（本仓库维护范围）：`ros_mes_front/` 与 `ros_mes_hou/` 的全部开发与修复。
- **机器人控制**：`robot_control_backend/` 的 ROS 节点、CAN 通信与消息定义由队友维护；本侧只通过 `docs/ROS_MES_前后端接口字段文档.md` 中记录的话题接口与其对接，不直接修改其代码。
