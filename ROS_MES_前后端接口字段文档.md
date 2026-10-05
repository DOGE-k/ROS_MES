# ROS_MES 前后端接口字段文档

> 对应 `robot_control_backend` 的 msg/topic 接口定义，本文档汇总 **软件前后端**（`ros_mes_hou` 后端 + `ros_mes_front` 前端）对外的全部接口与字段定义。
>
> - 代码基线：v1.1（commit `b03b57a`，2026-10-05 整理）
> - 范围：仅 `ros_mes_hou/`（FastAPI 后端）与 `ros_mes_front/`（Vue3 前端）；`robot_control_backend/` 不在本侧维护范围，其消息定义见 `robot_control_backend/msg/*.msg`
> - 字段名均与代码保持一致（保留原始英文命名）

---

## 目录

1. [系统架构与运行配置](#一系统架构与运行配置)
2. [通用约定](#二通用约定)
3. [认证机制](#三认证机制)
4. [数据库表字段定义](#四数据库表字段定义)
5. [后端 API 接口清单](#五后端-api-接口清单)
6. [WebSocket 接口](#六websocket-接口)
7. [前后端 ↔ ROS 通信字段](#七前后端--ros-通信字段)
8. [前端清单（页面 / 类型 / 状态存储）](#八前端清单)
9. [已知不一致与注意事项](#九已知不一致与注意事项)

---

## 一、系统架构与运行配置

```
┌──────────────────┐   HTTP / WS (/api/*)    ┌──────────────────┐   rosbridge WS (:9010)   ┌───────────────────────┐
│  ros_mes_front   │ ──────────────────────► │   ros_mes_hou    │ ───────────────────────► │ robot_control_backend │
│  Vue3 + Vite:5173│ ◄────────────────────── │  FastAPI :8000   │ ◄─────────────────────── │  (ROS 节点，他人维护)  │
└──────────────────┘                         └──────────────────┘                          └───────────────────────┘
                                                        │ SQLite: ros_database.db
                                                        │ 点云视图服务: http://localhost:5000
```

### 后端配置（`app/core/config.py`，均可通过环境变量覆盖）

| 配置项 | 环境变量 | 默认值 | 说明 |
|---|---|---|---|
| API 前缀 | `API_STR` | `/api` | 所有路由挂载前缀 |
| 数据库 | `DATABASE_URL` | `sqlite:///<项目根>/ros_database.db` | SQLite |
| CORS 来源 | `BACKEND_CORS_ORIGINS` | `*`（逗号分隔） | 用 Authorization 头，不用 Cookie，`*` 时关闭 credentials |
| JWT 密钥 | `MES_SECRET_KEY` | `your-secret-key-very-secure` | **部署时必须改** |
| Token 有效期 | `MES_TOKEN_EXPIRE_MINUTES` | `60`（分钟） | JWT 过期时间 |
| rosbridge 地址 | `ROSBRIDGE_URL` | `ws://localhost:9010` | 指令下发/反馈订阅 |
| 点云视图服务 | `POINTCLOUD_VIEW_BASE_URL` | `http://localhost:5000` | `/get_view/{view}` 图片代理 |
| 外部下发命令 | `ROS_DISPATCH_COMMAND` | 空（=mock 模式） | `ros_dispatcher.py` 遗留方案 |
| 外部下发超时 | `ROS_DISPATCH_TIMEOUT` | `5`（秒） | 同上 |

### 前端配置

| 配置项 | 值 | 说明 |
|---|---|---|
| dev 端口 | `5173`（host 0.0.0.0） | `vite.config.ts` |
| API 代理 | `/api` → `VITE_API_TARGET`（默认 `http://127.0.0.1:8000`），`ws: true` | HTTP 与 WebSocket 均转发 |
| axios 实例 | `baseURL: "/api"`，`timeout: 15000` | `src/utils/request.ts` |
| `VITE_USE_MOCK` | `false` | true 时跳过登录检查、仪表盘走本地 mock |
| `VITE_DEBUG_NO_ROS` | `true` | 无 ROS 环境调试：模块下发/图纸下发/微调/列表走前端模拟 |

---

## 二、通用约定

- **路由前缀**：所有接口实际路径 = `/api` + 子路由前缀（如 `/user`）+ 端点路径。
- **响应包装**：绝大多数接口返回 `{ "code": int, "message": str, "data": <载荷> }`；部分老接口（finetuning 系列）顶层即字段。出错时 FastAPI 标准 422/400/401/403/404/502 等，错误信息在 `detail`。
- **静态文件**：`/api/uploads/avatars/<文件名>`（头像）、`/api/uploads/drawings/<文件名>`（图纸 JSON）可直接 GET。
- **软删除**：业务表普遍带 `del_flag`，删除类接口均为软删除（`del_flag=True`）。
- **兼容别名**：多处请求体同时接受 `device_id`/`Device_ID`、`module_id`/`Device_ID` 等别名（unit/sensor/finetuning 的 schema 内做兜底转换）。
- **前端 token 白名单**：`request.ts` 中以下路径不携带 `Authorization` 头：`/login`、`/register`、`/send_ros`、`/get_ros_status`、`/module`、`/coordination`、`/finetuning`、`/device`（子串匹配）。

---

## 三、认证机制

- **方式**：OAuth2 Bearer Token。`OAuth2PasswordBearer(tokenUrl="/api/login")`。
- **JWT**：`jose`，算法 `HS256`，payload `{"sub": <Username>, "exp": ...}`。
- **密码**：passlib bcrypt 哈希。
- **依赖两级**：
  - `get_current_user`：解码 JWT → 查用户（须 `del_flag == False`、`Islock == False`）；
  - `get_current_admin`：在 `get_current_user` 基础上要求 `Type_ID == 1`。
- **WebSocket 认证**：`/api/ws/ws/robot_status` 通过 query 参数 `?token=<JWT>` 校验。

### 认证矩阵

| 级别 | 接口 |
|---|---|
| 免认证 | `POST /login`、`POST /register`、`GET /dashboard/stats`、`/finetuning/**`、`POST /module/`、`POST /control/finetuning`、WS `/control/feedback/ws`、`/coordination/**`、`/ros/**`、`/model/**`、`/device/**`、`/unit/**`、`/sensors/**`、`GET /api/uploads/**` |
| 登录即可 | `/user/me`、`GET /user/`、`POST /user/password`、`POST /user/avatar`、`PUT /user/profile/me`、`/drawing/**`、`/work/**`、`/workflow/**`、`/task/**`、`GET /control/serial_test`、`GET /control/hardware/realtime`、`POST /control/emergency_stop` |
| 管理员 | `POST /user/`、`PUT /user/{id}`、`DELETE /user/{id}`、`PUT /user/{id}/lock`、`/unlock`、`/role`、`POST /user/import`、`GET /user/export` |

---

## 四、数据库表字段定义

SQLite，共 17 张表（`app/db/models.py`；建库种子数据见根目录 `sqlite_create.py`）。时间字段均为 `DateTime(timezone=True)`，默认 `now()`；布尔在 SQLite 中存 0/1。

### 4.1 Users — 用户表

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| User_ID | Integer | 主键 |
| Username | Text | NOT NULL，账号 |
| Password | Text | NOT NULL，bcrypt 哈希 |
| Type_ID | Integer | NOT NULL；1=管理员 2=操作员 |
| Creator_ID | Integer | NOT NULL，FK → Users.User_ID（自引用） |
| Createtime | DateTime | NOT NULL |
| Islock | Boolean | NOT NULL，默认 False |
| Locktime | DateTime | 可空 |
| Name | String(20) | 可空，昵称 |
| Headimage | String(255) | 可空，头像文件名 |
| Birthday | DateTime | 可空 |
| Sex | Integer | 可空；0 保密 / 1 男 / 2 女 |
| Modifytime / del_flag / Notes | — | 通用字段 |

### 4.2 fine_tuning — 微调记录表

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| id | Integer | 主键 |
| module_id | Integer | NOT NULL，联合 FK → Unit(Module_ID) |
| unit_id | Integer | NOT NULL，联合 FK → Unit(Unit_ID) |
| module_address | Integer | 可空 |
| module_descript | Text | 可空 |
| parameter_name | String(100) | NOT NULL；rotation / swing / telescopic |
| old_value | Float | 可空 |
| new_value | Float | NOT NULL |
| creater_id | Integer | NOT NULL，FK → Users |
| create_time / notes / del_flag | — | 通用字段 |

### 4.3 fine_tuning_config — 微调配置快照表

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| id | Integer | 主键 |
| module_id / unit_id / sensor_id | Integer | NOT NULL，索引；联合 FK → Unit / sensors |
| config_json | Text | NOT NULL，整份配置 JSON |
| creater_id | Integer | NOT NULL，FK → Users |
| create_time / notes / del_flag | — | 通用字段 |

### 4.4 Drawings / DrawingsVersion — 图纸与版本表

| 表 | 字段 | 说明 |
|---|---|---|
| Drawings | Drawing_ID(PK)、Drawingname(Text,NOT NULL)、Drawingdescripte(Text,NOT NULL)、Drawingfile(Text,NOT NULL 文件路径)、Creator_ID(FK→Users)、Createtime、Modifytime、NewVersion_ID(FK→DrawingsVersion)、del_flag、Notes | 图纸主表 |
| DrawingsVersion | DrawingsVersion_ID(PK)、Drawing_ID(FK→Drawings)、Drawingfile(Text)、Creator_ID(FK→Users)、Createtime、Modify_ID(FK→Users)、Modifytime、del_flag、Notes | 每次导入生成新版本 |

### 4.5 works — 工作表

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| Work_ID | Integer | 主键 |
| Workname | Text | NOT NULL |
| WorkDescript | Text | 可空 |
| Drawing_ID | Integer | 可空，FK → Drawings |
| Module_ID | Integer | 可空，FK → Module |
| unit_id | Integer | 可空，FK → Unit.id |
| sensor_id | Integer | 可空，FK → sensors.id |
| data | Text | 可空（JSON 字符串） |
| creater_id | Integer | NOT NULL，FK → Users |
| Createtime / Modifytime / del_flag / Notes | — | 通用字段 |

### 4.6 workflows / work_flow_relations — 工作流与顺序关系

| 表 | 字段 | 说明 |
|---|---|---|
| workflows | Workflow_ID(PK)、Workflowname(Text,NOT NULL)、WorkflowDescript、creater_id(FK→Users)、Createtime、Modifytime、del_flag、Notes | 工作流主表 |
| work_flow_relations | work_flow_relation_ID(PK)、Workflow_ID(FK→workflows)、Work_ID(FK→works)、flow_seq(Integer,NOT NULL 执行顺序)、creater_id、Createtime、Modifytime、del_flag、Notes | 按数组顺序写入，flow_seq 从 1 起 |

### 4.7 Type / Module / Unit / sensors — 设备四层

| 表 | 字段 | 说明 |
|---|---|---|
| Type（型号） | Type_ID(PK)、Typename(Text,NOT NULL)、Typedescripte、creater_id、Createtime、del_flag、Notes | 自适应工装型号 |
| Module（模块） | Module_ID(PK)、Type_ID(FK→Type,NOT NULL)、Moduledescript、ModuleAddress(Text,NOT NULL 坐标编码)、creater_id、Createtime、del_flag、Notes | ModuleAddress = (x<<4)\|y，即 module_id = x*16+y |
| Unit（机械臂） | id(PK 代理主键)、Unit_ID(Integer 业务臂号，如 32/64/96)、UnitDescript、Module_ID(FK→Module)、creater_id、Createtime、del_flag、Notes；UniqueConstraint(Module_ID, Unit_ID) | 联合键被微调/传感器表引用 |
| sensors（传感器） | id(PK 代理主键)、sensor_ID(Integer 业务号)、sensordescript、IsRead(Integer)、Module_ID、Unit_ID、Unit_address(Integer)、creater_id、Createtime、del_flag、Notes；FK (Module_ID,Unit_ID)→Unit；Unique(Module_ID,sensor_ID) | 每臂 8 类：旋转/摆动/伸缩电机、旋转/偏转/伸缩编码器、压力、陀螺仪 |

### 4.8 Tasks / TasksTracing — 任务与跟踪

| 表 | 字段 | 说明 |
|---|---|---|
| Tasks | Task_ID(PK)、Taskname(Text,NOT NULL)、Taskdescripte、Workflow_ID(FK→workflows)、Drawing_ID(FK→Drawings)、creater_id(FK→Users)、Createtime、TaskAssignment_id(FK→Users 指派人)、Status(String(20),默认"0")、Modifytime、del_flag、Notes | Status："0"就绪 "1"运行 "2"暂停 "3"结束 |
| TasksTracing | TasksTracing_ID(PK)、Task_ID(FK→Tasks)、operate_type(Integer)、Workflow_ID(FK→workflows)、operater_ID(FK→Users)、operate_time、Notes | operate_type：0 启动 / 1 暂停 / 2 唤醒 / 3 结束 / 4 进度备注 / 5 调度 / 6 删除 |

### 4.9 其余表

| 表 | 字段 | 说明 |
|---|---|---|
| sensor_log | Createtime+sensor_id(复合主键)、creater_id(FK→Users)、Work_ID(FK→works)、isread、data(Text)、del_flag、Notes | 传感器数据日志 |
| calculation | Createtime(PK)、creater_id、Work_ID(FK→works)、Module_ID(FK→Module)、Unit_ID、device_ID、isread、coord(Text)、position(Text)、del_flag、Notes | 计算解析数据日志 |
| point_data | Createtime(PK)、creater_id、Module_ID(FK→Module)、point(Text,NOT NULL)、arms_address(Text,NOT NULL)、del_flag、Notes | 点云解析数据 |

> 注意：`schemas/device.py`、`schemas/model.py` 中的 `Device_*`/`Model_*` 命名是 **Module 表 / Type 表的对外别名**，数据库中没有独立的 Devices/Model 表。

### 4.10 种子数据（sqlite_create.py）

- 默认账号：`admin`(User_ID=1)、`system`(User_ID=2)，密码均为 `123456`。
- Type_ID=1「自适应工装型号」；Module_ID=17；机械臂 Unit_ID=32/64/96（一/二/三号臂）；每臂 8 个传感器（电机 33/34/35…、编码器 41/42/43…、压力 49/81/113、陀螺仪 50/82/114）。

---

## 五、后端 API 接口清单

共 60+ 端点，按子路由分组。`data` 指响应包装中的载荷字段。

### 5.1 认证 `/login`、`/register`

#### POST `/api/login` — 登录（免认证）

- 请求：`application/x-www-form-urlencoded`（OAuth2 标准表单）：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| username | str | ✔ | 账号 |
| password | str | ✔ | 密码 |

- 响应 `data`：

| 字段 | 类型 | 说明 |
|---|---|---|
| account | str | 用户名 |
| name | str | 姓名（无则取账号） |
| typeId | int | 1 管理员 / 2 操作员 |
| token | str | JWT |
| tokenType | str | `"bearer"` |
| headImage | str | `/api/uploads/avatars/...` 或 `""` |
| updateTime | str | ISO 时间 |

- 错误：401 账号或密码错误；403 账号被锁定。

#### POST `/api/register` — 注册（免认证）

- 请求体 JSON：`username`(str, ≥3 位)、`password`(str, ≥6 位)。
- 响应 `data`：`{"account": "<username>"}`；新用户 `Type_ID=2`。
- 错误：400 该用户名已被注册（已删除的用户名可重新注册）。

### 5.2 用户 `/user`

统一用户序列化字段（`user_to_dict`）：
`id, account, username, name, typeId, typeLabel("管理员"/"操作员"), headImage, isLock, birthday, sex, creatorId, createtime, locktime, modifytime, delFlag, notes`

| 端点 | 认证 | 请求字段 | 响应 data |
|---|---|---|---|
| GET `/api/user/me` | 登录 | 无 | user_to_dict |
| GET `/api/user/` | 登录 | query：`keyword`(模糊搜账号)、`type_id`(0=全部) | `user_to_dict[]` |
| POST `/api/user/` | 管理员 | body：`username`(≥3)、`password`(≥6)、`type_id`(默认2)、`name`? | user_to_dict |
| POST `/api/user/password` | 登录 | body：`old_password`、`new_password`(≥6) | null |
| POST `/api/user/avatar` | 登录 | multipart：`file`(image/*，≤2MB) | user_to_dict |
| PUT `/api/user/profile/me` | 登录 | body 可选：`name`、`birthday`(ISO 字符串)、`sex`、`type_id`(仅管理员本人生效) | user_to_dict |
| PUT `/api/user/{user_id}` | 管理员 | body 可选：`username`、`type_id`、`password`(≥6)、`name` | user_to_dict |
| DELETE `/api/user/{user_id}` | 管理员 | 无 | `{"id": user_id}`（软删除；不能删自己/admin） |
| PUT `/api/user/{user_id}/lock` | 管理员 | 无 | user_to_dict（不能锁自己/管理员） |
| PUT `/api/user/{user_id}/unlock` | 管理员 | 无 | user_to_dict |
| PUT `/api/user/{user_id}/role` | 管理员 | body：`type_id`(仅允许 1/2) | user_to_dict |
| POST `/api/user/import` | 管理员 | multipart：`file`(.csv，表头 `username`,`password`，可选 `type_id`) | `{successCount, failCount, failList:[{row,reason}], users[]}` |
| GET `/api/user/export` | 管理员 | 无 | CSV 文件流（users_export.csv） |

### 5.3 仪表盘 `/dashboard`

#### GET `/api/dashboard/stats` — 免认证，无参数

响应 `data` 为 7 个统计项，每项 `{label, value, unit, trend}`：
`deviceStatus`(设备状态)、`taskCount`(今日任务数)、`faultCount`(恒 0)、`onlineUsers`(用户总数)、`responseTime`(固定 23ms)、`concurrency`、`deviceConnections`(模块+机械臂+传感器总数)。

### 5.4 微调 `/finetuning`（免认证）

#### POST `/api/finetuning/` — 写入微调记录并返回渲染点

请求体 `FineTuningCreate`（校验器兜底：`Device_ID`→`device_id`；`new_value`→`position`）：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| module_id | int | ✔ | 模块号 |
| unit_id | int | ✔ | 机械臂号 |
| device_id / Device_ID | int | 可选 | 轴号（别名兼容） |
| position / new_value | float | 二者至少一个 | 目标位置 |
| parameter_name | str | 可选 | 缺省自动生成 `module_<m>_unit_<u>_position` |
| old_value | float | 可选 | 缺省取最近一次 new_value |

响应 `FineTuningApiResponse`：`{code, message, data, dispatch}`，`data` 固定两个元素：
`{device_id, position, type:"axis", parameter_name}` 与 `{device_id:-1, position:0.0, type:"pressure"}`。

#### GET `/api/finetuning/` — 微调记录列表

- query：`skip`(0)、`limit`(100)、`module_id?`、`unit_id?`。
- 响应 `FineTuningResponse[]`：`id, module_id, unit_id, module_address?, module_descript?, parameter_name, old_value?, new_value, creater_id, create_time?, notes?, del_flag`（按时间倒序）。

#### POST `/api/finetuning/config` — 保存配置快照

- 请求体 `FineTuningConfigCreate`：`module_id`(✔)、`unit_id`(✔)、`sensor_id`(可由 `device_id` 或 `devices[0]` 兜底)、`device_id?`、`x/y/z`(float, 默认0)、`devices: [{device_id?, sensor_id?, unit_id?, parameter_name?, label?, initial=0, adjust=0, current=0}]`。
- 响应 `data`：`{id, module_id, unit_id, sensor_id, config:<整份请求体>, creater_id, create_time, notes, del_flag}`。

### 5.5 图纸 `/drawing`（登录即可）

统一序列化字段：
- `drawing_to_dict`：`drawingId, drawingName, drawingDescription, drawingFile, creatorId, createTime, modifyTime, latestVersionId, delFlag, notes`
- `version_to_dict`：`versionId, drawingId, drawingFile, creatorId, createTime, modifyId, modifyTime, delFlag, notes`

| 端点 | 方法 | 请求字段 | 响应 data |
|---|---|---|---|
| `/api/drawing/` | GET | query：`keyword?`（名称/描述/Notes 模糊） | drawing[] |
| `/api/drawing/{drawing_id}` | GET | 路径 int | drawing |
| `/api/drawing/{drawing_id}/versions` | GET | 路径 int | version[]（倒序） |
| `/api/drawing/{drawing_id}/file` | GET | 路径 int | `{content(前10000字符), fullLength, truncated}` |
| `/api/drawing/import` | POST | FormData：`drawing_name`(✔)、`drawing_description`(默认"")、`drawing_id?`(有则追加新版本)、`file`(.json ✔) | drawing |
| `/api/drawing/{drawing_id}` | PUT | FormData：`drawing_name?`、`drawing_description?`、`notes?` | drawing |
| `/api/drawing/{drawing_id}` | DELETE | 路径 int | `{"drawingId": id}`（软删除） |

### 5.6 模块锁定 `/module`（免认证）

#### POST `/api/module/` — 坐标锁定并下发确认指令

- 请求体 JSON，字段别名兼容：
  - x：`x` / `X` / `targetX` / `moduleX` / `col` / `position.x`
  - y：`y` / `Y` / `targetY` / `moduleY` / `row` / `position.y`
  - 可选：`module_id`（缺省按 `x*16+y` 推算）、`device_id`
- x/y 缺失 → 422。
- 响应：`{code:200, message:"module locked and confirmation command dispatched", data:{x,y,module_id,device_id,position,raw}, dispatch:<rosbridge结果>}`；rosbridge 失败 502。

### 5.7 控制 `/control`

#### POST `/api/control/finetuning` — 微调下发（免认证）

- 请求体同 `FineTuningCreate`，但 `parameter_name` 必须是 `rotation` / `swing` / `telescopic` 之一（映射三个 adjust topic）；V2 校验：`device_id` ∈ 1~20（轴号）、`module_id` > 0。
- 写库 + 经 rosbridge 下发，失败 502。
- 响应同 5.4 POST `/finetuning/`（`message: "微调下发成功"`）。

#### GET `/api/control/serial_test` — 串口测试（登录）

- 无参数。响应 `data`：`{success: bool, message: str, ...}`（10 秒超时）。

#### GET `/api/control/hardware/realtime` — 硬件实时状态（登录）

- 无参数。响应 `HardwareFeedback`：`joints: float[]`、`status: str`、`timestamp: float`（5 秒超时）。

#### POST `/api/control/emergency_stop` — 全局急停（登录）

- 无参数。经 rosbridge 向 `/control/softstop` 发布 `module_id=0, device_id=0, position=[0x01]`。
- 响应 `EmergencyStopResponse`：`success: bool`、`message: str`、`timestamp: datetime`；失败 500。

### 5.8 协同 `/coordination`（免认证）

#### GET `/api/coordination/views/{view_name}` — 点云三视图图片

- 路径参数 `view_name`：仅 `top` / `front` / `side`，否则 404。
- 代理转发点云服务 `/get_view/{view}` 的图片（PNG），服务不可达 502。

#### POST `/api/coordination/send` — 下发目标图纸并等待点云生成

- 请求体 JSON（全部必填，缺失/类型错 422）：

| 字段 | 类型 |
|---|---|
| device_id | int |
| module_id | int |
| unit_id | int |
| unit_row_id | int |
| drawing_id | int |

- 响应：`{code:200, message:"...", data:{五元组}, dispatch:<rosbridge结果>, views:{"front":"/api/coordination/views/front","side":...,"top":...}}`；点云生成超时 504。

### 5.9 ROS 直发 `/ros`（免认证）

| 端点 | 请求 | 响应 data |
|---|---|---|
| GET `/api/ros/send_ros?msg=<str>` | query：`msg`(必填) | dispatch 结果；rospy 不可用 503 |
| GET `/api/ros/get_ros_status` | 无 | `{robot_status: str, battery: int, node: "ros_mes_api_server", ros_ready: bool}` |

### 5.10 工作 `/work`（登录）⚠ 参数走 **query string**，不是 JSON body

`work_to_dict` 字段：`Work_ID, Workname, WorkDescript, Drawing_ID, Module_ID, Device_id(=Module_ID), unit_id, sensor_id, data, creater_id, Createtime, Modifytime, del_flag, Notes`

| 端点 | 方法 | 请求字段（query） |
|---|---|---|
| `/api/work/create` | POST | `Workname`(✔)、`WorkDescript=""`、`Drawing_ID?`、`Module_ID?`、`Device_id?`(Module_ID 别名)、`unit_id?`、`sensor_id?`、`data`(JSON 字符串，非法 400)、`Notes=""` |
| `/api/work/list` | GET | `keyword?`（Workname 模糊） |
| `/api/work/{work_id}` | PUT | 同 create，全部可选 |
| `/api/work/{work_id}` | DELETE | 无 |

### 5.11 工作流 `/workflow`（登录）⚠ 同样走 **query string**

`workflow_to_dict` 字段：`Workflow_ID, Workflowname, WorkflowDescript, creater_id, Createtime, Modifytime, del_flag, Notes`

| 端点 | 方法 | 请求字段（query） | 响应特有 |
|---|---|---|---|
| `/api/workflow/create` | POST | `Workflowname`(✔)、`WorkflowDescript=""`、`Notes=""`、`work_ids='[]'`（**JSON 数组字符串**，如 `"[1,2,3]"`，按序写 flow_seq） | — |
| `/api/workflow/list` | GET | 无 | 每项附 `work_count` |
| `/api/workflow/{id}` | GET | 无 | 附 `works: [work_to_dict + flow_seq]`（已删工作显示 `Workname:"(已删除)"`） |
| `/api/workflow/{id}` | PUT | 同 create 可选（给 `work_ids` 时旧关系软删重建） | — |
| `/api/workflow/{id}` | DELETE | 无 | `{"Workflow_ID": id}`（含关系软删） |

### 5.12 任务 `/task`（登录，请求体为 JSON）

请求体模型：
- `TaskCreate`：`Taskname`(✔)、`Taskdescripte?`、`Workflow_ID?`、`Drawing_ID?`、`TaskAssignment_id?`、`Notes?`
- `TaskUpdate`：同上全 Optional
- `ProgressCreate`：`Notes`(✔)

`task_to_dict` 字段：`Task_ID, Taskname, Taskdescripte, Workflow_ID, Drawing_ID, creater_id, Createtime, TaskAssignment_id, Status, Modifytime, del_flag, Notes`；列表/详情追加 `DrawingName, WorkflowName, AssigneeName, WorksSubset:[{Work_ID, Workname, WorkDescript, flow_seq}]`。

| 端点 | 方法 | 请求 | 响应/说明 |
|---|---|---|---|
| `/api/task/create` | POST | body TaskCreate | Status 初始 "0" |
| `/api/task/list` | GET | query：`keyword?`、`status?('0'~'3')`、`drawing_id?`、`workflow_id?` | 按创建时间倒序 |
| `/api/task/{task_id}` | GET / PUT / DELETE | body TaskUpdate / 无 | DELETE 软删除（tracing 6） |
| `/api/task/{task_id}/start` | POST | 无 | 仅 0/2 → 1 |
| `/api/task/{task_id}/pause` | POST | 无 | 仅 1 → 2 |
| `/api/task/{task_id}/resume` | POST | 无 | 仅 2 → 1 |
| `/api/task/{task_id}/finish` | POST | 无 | 1/2 → 3 |
| `/api/task/{task_id}/dispatch` | POST | 无 | 仅 "0" 可调度；其余运行中任务置 "2"，本任务置 "1" |
| `/api/task/{task_id}/tracing` | GET | 无 | `[{TasksTracing_ID, Task_ID, operate_type, Workflow_ID, operater_ID, operate_time, Notes, OperatorName}]` 倒序 |
| `/api/task/{task_id}/works` | GET | 无 | `WorksSubset[]` |
| `/api/task/{task_id}/progress` | POST | body：`Notes`(✔) | 写 tracing type=4；前端把工件记录 JSON 字符串化存入 Notes |

### 5.13 设备四层 CRUD：`/model`、`/device`、`/unit`、`/sensors`（均免认证）

> 同一路径靠 HTTP 方法区分 GET/POST/PUT/DELETE；`by_xxx` 与 `tree` 路由须注册在通配路由之前（代码已如此）。

#### 型号 `/model`

`serialize_model` 字段：`Model_ID, Modelname, Modeldescripte, creater_id, Createtime, del_flag, Notes, Type_ID, Typename, Typedescripte`

| 端点 | 方法 | 请求字段 |
|---|---|---|
| `/api/model/` | GET | 无 |
| `/api/model/tree` | GET | 无（四级设备树，见下） |
| `/api/model/{model_id}` | GET | 路径 int |
| `/api/model/` | POST | body：`Modelname`(✔)、`Modeldescripte?`、`Notes?` |
| `/api/model/{model_id}` | PUT | body 同上可选 |
| `/api/model/{model_id}` | DELETE | 路径 int |

`/api/model/tree` 节点结构（`TreeNode`）：

| 层级 | 节点字段 |
|---|---|
| model | `{id:"model-<Type_ID>", label, type:"model", raw_id, children}` |
| device | `{id:"device-<Module_ID>", label, type:"device", raw_id, module_id, children}` |
| unit | `{id:"unit-<id>", label, type:"unit", raw_id, arm_type(=Unit_ID), module_id, device_id, children}` |
| sensor | `{id:"sensor-<id>", label, type:"sensor", raw_id, sensor_type(=sensor_ID), module_id, device_id}` |

#### 模块 `/device`（Module 表别名）

`serialize_device` 字段：`Device_ID(=Module_ID), Model_ID(=Type_ID), DeviceAddress(int), Devicedescript, creater_id, Createtime, del_flag, Notes, Module_ID, Type_ID, ModuleAddress, Moduledescript`

| 端点 | 方法 | 请求字段 |
|---|---|---|
| `/api/device/` | GET | 无 |
| `/api/device/by_model/{model_id}` | GET | 路径 int |
| `/api/device/{device_id}` | GET | 路径 int |
| `/api/device/` | POST | body：`Model_ID`(✔)、`DeviceAddress`(✔，=(x<<4)\|y)、`Devicedescript?`、`Notes?`、`creater_id=1`；同型号坐标冲突 409 |
| `/api/device/{device_id}` | PUT | body 前 4 字段可选；坐标冲突 409 |
| `/api/device/{device_id}` | DELETE | 路径 int |

#### 机械臂 `/unit`

响应为 ORM 序列化：`id, Unit_ID, UnitDescript, Module_ID, creater_id, Createtime, del_flag, Notes`

| 端点 | 方法 | 请求字段 |
|---|---|---|
| `/api/unit/` | GET | 无 |
| `/api/unit/by_device/{device_id}` | GET | 路径 int |
| `/api/unit/{unit_id}` | GET | 路径 int |
| `/api/unit/` | POST | body：`Unit_ID`(✔ 臂号)、`Module_ID?`/`Device_ID?`(二选一，validator 兜底)、`UnitDescript?`、`Notes?`；同模块下 Unit_ID 重复 409 |
| `/api/unit/{unit_id}` | PUT | body 可选 |
| `/api/unit/{unit_id}` | DELETE | 路径 int |

#### 传感器 `/sensors`

响应为 ORM 序列化：`id, sensor_ID, sensordescript, IsRead, Module_ID, Unit_ID, Unit_address, creater_id, Createtime, del_flag, Notes`

| 端点 | 方法 | 请求字段 |
|---|---|---|
| `/api/sensors/` | GET | 无 |
| `/api/sensors/by_unit/{unit_id}` | GET | 路径 int |
| `/api/sensors/{sensor_id}` | GET | 路径 int |
| `/api/sensors/` | POST | body：`sensor_ID`(✔)、`Unit_ID`(✔)、`Unit_address`(✔)、`Module_ID?`/`Device_ID?`(兜底)、`unit_row_id?`、`sensordescript?`、`IsRead=1`、`Notes?`；同模块下 sensor_ID 重复 409 |
| `/api/sensors/{sensor_id}` | PUT | body 同上可选 |
| `/api/sensors/{sensor_id}` | DELETE | 路径 int |

---

## 六、WebSocket 接口

### 6.1 WS `/api/ws/ws/robot_status` — 大屏机器人状态推送

> 注意：api.py 前缀 `/ws` + 路由 `/ws/robot_status` 造成路径中出现两层 `/ws`。

- 连接：`ws://<host>/api/ws/ws/robot_status?token=<JWT>`；token 缺失/无效 → `close(1008)`。
- 方向：仅服务端 → 客户端，`send_text` 推送。
- 消息：子进程 `web_data_node.py` stdout 的每行原始 JSON。⚠ 该脚本当前整文件被注释，**连接成功但无消息推送**。注释中历史格式：
  `{time_id, header:{secs,nsecs}, module_id, device_id, position, data_type:"axis_encoder"|"pressure_sensor"|"unknown", id?, feedback_type?}`

### 6.2 WS `/api/control/feedback/ws` — 微调实时硬件反馈（免认证）

- 前端唯一使用的 WS；服务端连接 rosbridge 并订阅 5 个话题（见第七节），归一化后 `send_json`。
- 消息字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| time_id | float | `time.time()` 时间戳 |
| topic | str | 来源 ROS 话题 |
| header | dict | `{secs, nsecs}` |
| module_id | int | 模块号 |
| device_id | int | 轴号 1~20 / 臂级 21~25 |
| position | float/list | 反馈位置值 |
| data_type | str | `rotation_axis_encoder` / `swing_axis_encoder` / `telescope_axis_encoder` / `pressure_sensor` / `imu_pose` / `unknown` |
| feedback_type | str | 中文标签，如 "臂1旋转轴编码器" |
| raw | dict | rosbridge 原始 msg |
| id | str/int | 仅原 msg 含 `id` 时附带 |
| swing_angle / rotation_angle / x / y / z | float | 仅 `data_type=="imu_pose"` 时附带 |

- 异常帧：`{"data_type":"error", "message":"<描述>"}`。

---

## 七、前后端 ↔ ROS 通信字段

后端有四条通信链路，主力是 **rosbridge_gateway（A）**：

| 链路 | 文件 | 方式 |
|---|---|---|
| A. rosbridge 网关 | `rosbridge_gateway.py` | WebSocket `ws://localhost:9010`，advertise+publish 协议 |
| B. 子进程直跑脚本 | `ros_control.py` | 直接运行 `robot_control_backend/scripts/*.py` 抓 stdout |
| C. 通用适配层 | `ros_dispatcher.py` | 环境变量外部命令 / mock（遗留） |
| D. rospy 常驻节点 | `ros_service.py` | ROS1 节点 `ros_mes_api_server` |

### 7.1 链路 A：下发的 topic（rosbridge）

| action | topic | 消息类型 | 触发接口 |
|---|---|---|---|
| fine_tuning（rotation） | `/control/adjust_rotation_cmd` | `robot_control_backend/RotationCmd` | POST /control/finetuning |
| fine_tuning（swing） | `/control/adjust_swing_cmd` | `robot_control_backend/SwingCmd` | 同上 |
| fine_tuning（telescopic） | `/control/adjust_telescopic_cmd` | `robot_control_backend/TelescopicCmd` | 同上 |
| drawing_path | `/frontend_pointcloud_topic` | `std_msgs/String` | POST /coordination/send |
| module_confirm | `/control/module_cmd` | `robot_control_backend/IntCmd` | POST /module/ |

ROS message JSON 字段（对应 robot_control_backend 的 msg 定义）：

- 轴指令（RotationCmd/SwingCmd/TelescopicCmd）：
  `{"header": {"stamp": {"secs": int, "nsecs": int}, "frame_id": ""}, "module_id": int, "device_id": int(1~20), "position": [float]}`
- IntCmd（模块确认）：
  `{"header": {...}, "module_id": int, "device_id": 0, "position": [100]}`
- String（图纸路径）：`{"data": "{\"file_path\": \"<相对 robot_control_backend/scripts 的路径>\"}"}`

**模块确认回包**：发布前先订阅 `/hardware/module_confirm_success` 与 `/hardware/web_module_cmd`；要求回包 `module_id` 匹配且 `device_id==0` 且 `position` 非空——`position[0]==1` 判定失败（抛 RosbridgeError），`position[0]==100` 判定成功。

### 7.2 链路 A：订阅的 topic（反馈流）

| topic | data_type | device_id 约定 |
|---|---|---|
| `/hardware/rotation_feedback` | rotation_axis_encoder | J1 旋转轴 = 1,5,9,13,17 |
| `/hardware/swing_feedback` | swing_axis_encoder | J2 摆动轴 = 2,6,10,14,18 |
| `/hardware/telescope_feedback` | telescope_axis_encoder | J4 伸缩轴 = 4,8,12,16,20 |
| `/hardware/sensor_feedback` | pressure_sensor | 臂级 = 21~25 |
| `/hardware/imu_angles` | imu_pose | 臂级 21~25 时覆盖 |

原始消息字段：`device_id, module_id, header(stamp), position`；IMU 另有 `swing_angle, rotation_angle, x, y, z`。归一化输出字段见 6.2。

### 7.3 链路 B：子进程脚本（ros_control.py）

| 函数 | 脚本 | 超时 | 用途 |
|---|---|---|---|
| `get_hardware_status()` | `hardware_node.py` | 5s | GET /control/hardware/realtime |
| `test_serial_connection()` | `serial_test_node.py` | 10s | GET /control/serial_test |
| `stream_real_robot_data()` | `web_data_node.py` | — | WS /ws/ws/robot_status（脚本当前已注释） |
| `trigger_emergency_stop()` | — | 2s | 直发 `/control/softstop`：`{header, module_id:0, device_id:0, position:[0x01]}` |

### 7.4 链路 D：rospy 节点（ros_service.py）

- 发布：`/web_cmd`（std_msgs/String），内容 `{"command": str, "payload": dict}`；登录后的 `/ros/send_ros` 即 `command="send_ros", payload={"msg": ...}`。
- 订阅：`/robot_status`（std_msgs/String），JSON dict 则合并进 `latest_status`，否则存 `robot_status` 字符串。

---

## 八、前端清单

### 8.1 路由与页面（`src/router/routes.ts`）

| 路由 | 组件 | 功能 | 核心字段 |
|---|---|---|---|
| `/login` | LoginPage | 登录 | 表单 `account`/`password`，提交映射为 `username`/`password`（form-urlencoded） |
| `/register` | RegisterPage | 注册 | `account, password(≥6), repassword` → 提交 `username, password` |
| `/Dashboard` | DashboardPage | 仪表盘 7 卡片 | `deviceStatus, taskCount, faultCount, onlineUsers, responseTime, concurrency, deviceConnections` |
| `/HardWorkPage` | HardWorkPage | 设备四层树管理 | 型号 `Modelname…`；模块 `DeviceAddress=(x<<4)\|y`；机械臂 `Unit_ID`(32/64/96)；传感器 8 类 `sensor_ID/Unit_address/IsRead` |
| `/ModuleManagement` | ModuleManagement | 8×8 矩阵锁定模块 | `inputX/inputY`(1-8) → `module_id=x*16+y`；先查 `/device/` 取 `Device_ID` 再 `POST /module/`；成功跳微调页 |
| `/FineTuningPage` | FineTuningPage | 微调 + 压力/IMU 监控 | 强制选 `unitRowId`/`drawingId`；三轴 `rotation/swing/telescopic`（deviceId 41/42/43）；WS 实时反馈 |
| `/DrawingManage` | DrawingManage | 图纸导入/预览/版本 | 导入 FormData `drawing_name/drawing_description/drawing_id?/file(.json)` |
| `/WorkflowManage` | WorkflowManage | 工作 + 工作流编排（双 Tab） | 工作五级联动（图纸/型号/设备/单元/传感器）；`work_ids=JSON.stringify(ids)` |
| `/TaskManagement` | TaskManage | 任务全生命周期 | 状态 '0'~'3'；工件记录 JSON 存入 progress 的 `Notes`（`piece_code, code_type, grab_time, fixture_position{x,y,z}, robot_track, detect_result, operator`） |
| `/UserManagement` | UserManagement | 用户管理（admin） | 新增/编辑 `username,name,password,type_id(1/2)`；CSV 导入导出 |
| `/Profile` | Profile | 个人中心 | `name, birthday, sex(0/1/2)`；改密 `old_password, new_password` |
| `/RosTestPage` | RosTestPage | ROS 联调测试页（免登录白名单） | 各接口示例 payload |

布局组件：`MainPage`（顶栏串口测试按钮）、`AsidePage`（侧边菜单 + 长按 2 秒急停 `POST /control/emergency_stop`）。

路由守卫：无 `localStorage.token` 跳 `/login`；`meta.requiresAdmin` 且 `role !== "admin"` 跳 `/HardWorkPage`；白名单 `/login`、`/register`、`/RosTestPage`。

### 8.2 前端 TS 类型（`src/api/types.ts`）

核心类型字段（与后端对齐部分）：

- `ApiResponse<T>`：`{code, message, data}`
- `FineTuningItem`：`id, module_id, unit_id, module_address?, module_descript?, parameter_name, old_value?, new_value, creater_id, create_time?, notes?, del_flag`
- `DrawingItem`：`drawingId, drawingName, drawingDescription, drawingFile, creatorId, createTime, modifyTime, latestVersionId?, delFlag, notes`
- `WorkItem`：`Work_ID, Workname, WorkDescript, Drawing_ID?, Module_ID?, Device_id?, unit_id?, sensor_id?, data, creater_id, Createtime, Modifytime, del_flag, Notes`
- `WorkflowItem` / `WorkflowDetail`：工作流字段 + `work_count?` / `works:(WorkItem & {flow_seq})[]`
- `TaskItem`：任务字段 + `DrawingName?, WorkflowName?, AssigneeName?, WorksSubset?`
- `TaskTracingItem`：`TasksTracing_ID, Task_ID, operate_type, Workflow_ID, operater_ID, operate_time, Notes, OperatorName?`
- `DashboardStats`：7 个 `{label, value, unit, trend}` 键
- `TreeNode`（rosApi.ts 内）：`{id, label, type:'model'|'device'|'unit'|'sensor', raw_id, arm_type?, sensor_type?, module_id?, device_id?, children?}`

### 8.3 状态存储（Pinia + localStorage）

- `useUserStore`：`account, nickname, role, token, avatar, updateTime`（同步写 localStorage 同名 key）；`role = typeId===1 ? "admin" : ...`；`isAdmin()`、`isLogin()`、`clearUser()`。
- `useLayoutSettingStore`：`fold`（菜单折叠）。
- localStorage 其他读取：路由守卫读 `token`/`role`；request.ts 读 `token`。

### 8.4 前端 WS 连接

- 仅 FineTuningPage 连接 `ws(s)://{location.host}/api/control/feedback/ws`（vite 代理转发后端），消息为纯 JSON（非 rosbridge 协议），字段见 6.2。
- 前端**不直连** rosbridge。

---

## 九、已知不一致与注意事项

1. **work/workflow 写接口参数走 query string** 而非 JSON body（`POST /work/create`、`PUT /workflow/{id}` 等），与其它模块风格不一致；`work_ids` 是 JSON 数组字符串。
2. **命名混用**：`Module_ID` 与 `Device_id` 在 works 表和前端表单中混用（同一含义）；后端多处接受 `Device_ID`/`device_id` 双别名。
3. **types.ts 的 `UserInfo` 与实际登录响应不一致**：类型定义为 `username/role/email/phone...`，后端实际返回 `account/name/typeId/headImage...`；store 内部另有一套登录结构。
4. ** WS 路径双层 `/ws`**：`/api/ws/ws/robot_status`（前缀 + 路径叠加），对接时容易写错。
5. **`web_data_node.py` 已整体注释**：`/api/ws/ws/robot_status` 连接成功但不会推送任何数据。
6. **遗留死代码**：`AddItem.vue`（调用不存在的 `/hardware` 接口，未挂载路由）；`GET /finetuning/`、`GET /finetuning/config`、`GET /drawing/{id}`、`GET /task/{id}` 已在后端实现/前端封装但页面未调用。
7. **认证缺口（待办）**：`/coordination`、`/module`、`/model`、`/device`、`/unit`、`/sensors`、`/finetuning`、`/control/finetuning`、`/dashboard/stats` 目前免认证；前端 request.ts 白名单与之配套。若后端加鉴权，需同步缩减前端白名单，否则会断。
8. **微调写库 `creater_id`**：`/control/finetuning` 免认证路径下 `creater_id=1` 写死，不区分实际操作人。
9. **同路径多方法**：`/model`、`/device`、`/unit`、`/sensors` 的 GET 与 POST/PUT/DELETE 同路径，靠方法区分；前端封装时注意路径次序（`tree`、`by_xxx` 必须先于通配路由注册）。
10. **任务工件记录**不是独立接口：JSON 字符串塞在 `POST /task/{id}/progress` 的 `Notes` 里。
