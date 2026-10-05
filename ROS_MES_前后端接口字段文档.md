# ROS_MES 前后端接口字段文档

> **基准**：以《ROS_MES_前后端ROS接口清单》（2026-10-05，团队基准文档）的章节结构与内容为准；本文档在其基础上逐项对照 v1.1 代码（commit `b03b57a`）核对修正，并在末尾补充基准未覆盖的**业务管理接口、数据库表字段与认证矩阵**。
>
> - 范围：`ros_mes_hou/`（FastAPI 后端）+ `ros_mes_front/`（Vue3 前端）；`robot_control_backend/` 的 msg 定义由队友维护，此处仅作对接参照
> - 与基准的三处核对修正见 [8.9 与基准文档的差异核对](#89-与基准文档的差异核对)
> - 字段名均与代码一致

---

## 目录

1. [整体架构](#1-整体架构)
2. [REST API 接口（前端→后端→ROS）](#2-rest-api-接口前端后端ros)
3. [WebSocket 接口（双向实时推送）](#3-websocket-接口双向实时推送)
4. [ROS 话题与服务映射](#4-ros-话题与服务映射)
5. [消息格式定义](#5-消息格式定义)
6. [device_id 与 module_id 编码规则](#6-device_id-与-module_id-编码规则)
7. [前端调用位置汇总](#7-前端调用位置汇总)
8. [注意事项与潜在问题](#8-注意事项与潜在问题)
9. [业务管理接口（基准补充）](#9-业务管理接口基准补充)
10. [数据库表字段（基准补充）](#10-数据库表字段基准补充)
11. [认证矩阵（基准补充）](#11-认证矩阵基准补充)
- [附录：关键文件索引](#附录关键文件索引)

---

## 1. 整体架构

```
前端 (Vue3 + TypeScript)
    │
    ├── REST API (Axios, baseURL: /api)
    │       │
    │       ▼
    │   FastAPI 后端 (ros_mes_hou, 端口 8000)
    │       │
    │       ├── rosbridge_gateway.py → rosbridge_websocket (ws://localhost:9010)
    │       │       │
    │       │       ▼
    │       │   ROS 话题发布/订阅
    │       │
    │       ├── ros_service.py → rospy 直接发布 (旧版 /web_cmd)
    │       │
    │       └── ros_control.py → 子进程调用 ROS 脚本 / WebSocket 急停
    │
    └── WebSocket (原生 WebSocket API)
            │
            ├── /api/control/feedback/ws → rosbridge 反馈流
            └── /api/ws/ws/robot_status → web_data_node 数据流
```

**关键配置：**

| 配置 | 值 | 环境变量 |
|---|---|---|
| 前端开发代理 | `/api` → `http://127.0.0.1:8000`（支持 WebSocket 代理） | `VITE_API_TARGET` |
| rosbridge 地址 | `ws://localhost:9010` | `ROSBRIDGE_URL` |
| 后端 API 前缀 | `/api` | `API_STR` |
| JWT 密钥 / 有效期 | 默认占位值 / 60 分钟（**部署时必须改密钥**） | `MES_SECRET_KEY` / `MES_TOKEN_EXPIRE_MINUTES` |
| 点云视图服务 | `http://localhost:5000` | `POINTCLOUD_VIEW_BASE_URL` |
| 数据库 | SQLite `ros_database.db`（项目根） | `DATABASE_URL` |
| 无 ROS 调试模式 | `VITE_DEBUG_NO_ROS=true`（前端模拟数据） | — |

---

## 2. REST API 接口（前端→后端→ROS）

> 所有接口均通过 `baseURL: /api` 访问，统一返回格式：`{ code, message, data }`

### 2.1 ROS 通用测试接口

| 序号 | 接口路径 | 方法 | 鉴权 | 对应 ROS 话题 | 用途 |
|------|---------|------|------|-------------|------|
| 1 | `/ros/send_ros` | GET | 否（白名单） | `/web_cmd` (std_msgs/String) | 通用 ROS 消息下发测试 |
| 2 | `/ros/get_ros_status` | GET | 否（白名单） | `/robot_status` 订阅 | 获取 ROS 节点运行状态 |

**接口 1：发送 ROS 消息**
- 请求参数：`msg: string`（Query 参数）
- 响应：`{"code":200, "message":"已发送到 ROS：xxx", "data":{"topic":"/web_cmd", "command":"send_ros", "payload":{"msg":"xxx"}}}`
- 后端实现：`app/services/ros_service.py` → `publish_ros_command()`
- 发布内容：JSON 字符串 `{"command": "send_ros", "payload": {"msg": "..."}}`

**接口 2：获取 ROS 状态**
- 请求参数：无
- 响应：`{"code":200, "message":"获取 ROS 状态成功", "data":{"robot_status":"unknown", "battery":85, "node":"ros_mes_api_server", "ros_ready":true/false}}`
- 后端实现：`app/services/ros_service.py` → `latest_status` 全局变量

---

### 2.2 模块锁定与确认接口

| 序号 | 接口路径 | 方法 | 鉴权 | 对应 ROS 话题 | 用途 |
|------|---------|------|------|-------------|------|
| 3 | `/module/` | POST | 否（白名单） | `/control/module_cmd` (IntCmd) | 锁定目标模块并下发确认指令 |

**接口 3：模块锁定下发**
- 请求体（支持多种字段名，兼容前端不同版本）：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `x` | int | ✔（或别名） | X 坐标 (1~8)；别名 `X/targetX/moduleX/col` 或 `position.x` |
| `y` | int | ✔（或别名） | Y 坐标 (1~8)；别名 `Y/targetY/moduleY/row` 或 `position.y` |
| `module_id` | int | 可选 | 默认 `x*16+y` |
| `device_id` | int | 可选 | 设备 ID |
| `position` | int | 可选 | 位置（前端传 0）；也可传对象 `{x, y}` |

- 响应：

```json
{
  "code": 200,
  "message": "module locked and confirmation command dispatched",
  "data": { "x": 1, "y": 2, "module_id": 18, "device_id": 1, "position": 0, "raw": {} },
  "dispatch": {
    "sent": true, "mode": "rosbridge", "action": "module_confirm",
    "confirmed": true/false, "confirm_topic": "/hardware/module_confirm_success"
  }
}
```

- ROS 消息（IntCmd）：`module_id`（前端计算 `x*16+y`）、`device_id=0`（模块级指令）、`position=[100]`（确认标识）
- 确认机制：发布后订阅 `/hardware/module_confirm_success` 与 `/hardware/web_module_cmd`；回包 `position[0]==100` 成功、`position[0]==1` 失败（HTTP 502）
- x/y 缺失 → 422

---

### 2.3 坐标协调（目标图纸下发）接口

| 序号 | 接口路径 | 方法 | 鉴权 | 对应 ROS 话题 | 用途 |
|------|---------|------|------|-------------|------|
| 4 | `/coordination/send` | POST | 否（白名单） | `/frontend_pointcloud_topic` (std_msgs/String) | 下发目标图纸路径，触发生成点云 |
| 5 | `/coordination/views/{view_name}` | GET | 否 | （点云视图服务代理） | 获取点云三视图 |

**接口 4：目标图纸下发**
- 请求体（全部必填，缺失/类型错 422）：

| 字段 | 类型 |
|---|---|
| `device_id` | int |
| `module_id` | int |
| `unit_id` | int |
| `unit_row_id` | int |
| `drawing_id` | int |

- 响应：`{"code":200, "message":"target drawing path dispatched and pointcloud views are ready", "data":{五元组}, "dispatch":{...}, "views":{"front":"/api/coordination/views/front","side":"...","top":"..."}}`
- ROS 消息（std_msgs/String）：`data` = JSON 字符串 `{"file_path": "相对 robot_control_backend/scripts 的图纸路径"}`
- 流程：校验参数 → 查库取图纸路径 → 转相对路径 → rosbridge 发布 → 等待点云三视图生成（最长 5 秒，超时 504）

**接口 5：点云视图代理**
- 路径参数：`view_name` ∈ {`top`, `front`, `side`}（其他值 404）
- 响应：图片二进制（`image/png`）；点云服务不可达 502

---

### 2.4 微调控制接口

| 序号 | 接口路径 | 方法 | 鉴权 | 对应 ROS 话题 | 用途 |
|------|---------|------|------|-------------|------|
| 6 | `/control/finetuning` | POST | 否（白名单） | `/control/adjust_rotation_cmd`<br>`/control/adjust_swing_cmd`<br>`/control/adjust_telescopic_cmd` | 单轴微调指令下发（V2 主路径，写库+下发） |
| 7 | `/finetuning/` | POST | 否（白名单）⚠修正 | （仅数据库，不下发 ROS） | 微调记录保存（旧路径，仅写库） |
| 8 | `/finetuning/config` | POST | 否（白名单）⚠修正 | （仅数据库） | 保存微调配置快照 |
| 9 | `/finetuning/config` | GET | 否（白名单）⚠修正 | （仅数据库） | 查询微调配置 |

> ⚠ **修正**：基准文档将 7/8/9 标为"鉴权：是"。经核对 `app/api/endpoints/finetuning.py` 无 `get_current_user` 依赖，且前端 `request.ts` 白名单对 `/finetuning` 不带 token 调用——实际**全部免认证**。

**接口 6：微调控制（主路径）**
- 请求体：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `module_id` | int | ✔ | 模块编号（V2 要求 > 0） |
| `device_id` | int | ✔ | 轴号 1~20；兼容别名 `Device_ID` 自动映射 |
| `unit_id` | int | ✔ | 机械臂 ID |
| `parameter_name` | str | ✔ | `"rotation"` \| `"swing"` \| `"telescopic"` |
| `position` | float | ✔ | 调整量（度/mm）；兼容别名 `new_value` 自动映射 |

- 响应：

```json
{
  "code": 200, "message": "微调下发成功",
  "data": [
    { "device_id": 1, "position": 5.0, "type": "axis", "parameter_name": "rotation" },
    { "device_id": -1, "position": 0.0, "type": "pressure" }
  ],
  "dispatch": { }
}
```

- ROS 消息映射：

| parameter_name | ROS 话题 | 消息类型 |
|---------------|---------|---------|
| `rotation` | `/control/adjust_rotation_cmd` | `robot_control_backend/RotationCmd` |
| `swing` | `/control/adjust_swing_cmd` | `robot_control_backend/SwingCmd` |
| `telescopic` | `/control/adjust_telescopic_cmd` | `robot_control_backend/TelescopicCmd` |

- 消息格式：`{"header":{"stamp":{"secs":int,"nsecs":int},"frame_id":""}, "module_id":int, "device_id":int, "position":[float]}`
- V2 约束：`device_id` ∈ 1~20（轴号空间），`module_id` > 0；rosbridge 失败 502
- payload 附带 `business` 字段（`{module_id, device_id, unit_id}`，仅回传前端，不进 ROS 消息）
- `parameter_name` 不在三者内 / 越界 → `RosbridgeError`

**接口 7/8/9 字段**：
- POST `/finetuning/`：`module_id`(✔)、`unit_id`(✔)、`device_id/Device_ID`?、`position/new_value`(至少其一)、`parameter_name`?（缺省自动生成 `module_<m>_unit_<u>_position`）、`old_value`?（缺省取最近一次 new_value）→ 返回 `FineTuningResponse[]`（GET 列表：`id, module_id, unit_id, module_address?, module_descript?, parameter_name, old_value?, new_value, creater_id, create_time?, notes?, del_flag`）
- POST `/finetuning/config`：`module_id`(✔)、`unit_id`(✔)、`sensor_id`(可由 `device_id`/`devices[0]` 兜底)、`device_id?`、`x/y/z=0`、`devices:[{device_id?, sensor_id?, unit_id?, parameter_name?, label?, initial=0, adjust=0, current=0}]` → 整份 JSON 存 `config_json`
- GET `/finetuning/`：query `skip=0, limit=100, module_id?, unit_id?`

---

### 2.5 硬件控制与状态接口

| 序号 | 接口路径 | 方法 | 鉴权 | 对应 ROS 话题/方式 | 用途 |
|------|---------|------|------|-------------------|------|
| 10 | `/control/serial_test` | GET | 是 | 子进程调用 `serial_test_node.py` | 串口连接测试 |
| 11 | `/control/hardware/realtime` | GET | 是 | 子进程调用 `hardware_node.py` | 获取实时硬件状态 |
| 12 | `/control/emergency_stop` | POST | 是 | `/control/softstop` (IntCmd) | 触发全局急停 |

**接口 10：串口连接测试**
- 响应：`{"code":200, "message":"串口测试完成", "data":{"success":true, "connected":true, "message":"串口连接正常", "bytes_received":128}}`
- 实现：`ros_control.py` → `test_serial_connection()`，异步子进程，超时 10 秒

**接口 11：实时硬件状态**
- 响应模型 `HardwareFeedback`：`{"joints":[float...], "status":str, "timestamp":float}`
- 实现：`ros_control.py` → `get_hardware_status()`，超时 5 秒

**接口 12：紧急停止**
- 响应（非标准包装）：`{"success":bool, "message":str, "timestamp":datetime}`；失败 500
- ROS 消息（IntCmd）：`module_id=0, device_id=0, position=[0x01]`（系统级急停）
- 实现：直连 rosbridge WebSocket 发布（无 advertise），超时 2 秒

---

## 3. WebSocket 接口（双向实时推送）

### 3.1 微调反馈 WebSocket

| 项目 | 内容 |
|------|------|
| 连接地址 | `ws(s)://{host}/api/control/feedback/ws` |
| 鉴权 | 否（无需 token） |
| 方向 | 服务端 → 客户端（单向推送） |
| 数据来源 | rosbridge 订阅 5 个反馈话题 |
| 后端文件 | `app/api/endpoints/control.py` + `app/services/rosbridge_gateway.py` |
| 前端文件 | `FineTuningPage.vue`（vite 代理转发，前端不直连 rosbridge） |

**订阅的 ROS 反馈话题：**

| 话题名 | 消息类型 | 数据内容 |
|--------|---------|---------|
| `/hardware/rotation_feedback` | RotationCmd | 旋转轴编码器反馈 |
| `/hardware/swing_feedback` | SwingCmd | 摆动轴编码器反馈 |
| `/hardware/telescope_feedback` | TelescopicCmd | 伸缩轴编码器反馈 |
| `/hardware/sensor_feedback` | SensorCmd | 压力传感器反馈 |
| `/hardware/imu_angles` | TuoLuoYi（由 GyroFeedback 衍生）⚠修正 | 陀螺仪姿态反馈 |

> ⚠ **修正**：基准文档将 `/hardware/imu_angles` 类型标为 "GyroFeedback (衍生)"。实际发布者是 `tuo_luo_yi.py`，订阅 `/hardware/gyroscope_feedback`(GyroFeedback) 换算后以 **`robot_control_backend/TuoLuoYi`** 类型发布到 `/hardware/imu_angles`。

**推送数据格式（归一化后）：**

```json
{
  "time_id": 1234567890.123,
  "topic": "/hardware/rotation_feedback",
  "header": { "secs": 12345, "nsecs": 67890 },
  "module_id": 17,
  "device_id": 1,
  "position": 45.5,
  "data_type": "rotation_axis_encoder",
  "feedback_type": "臂1旋转轴编码器",
  "raw": { }
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `time_id` | float | `time.time()` 时间戳 |
| `topic` | str | 来源 ROS 话题 |
| `header` | dict | `{secs, nsecs}` |
| `module_id` | int | 模块号 |
| `device_id` | int | 轴号 1~20 / 臂级 21~25 |
| `position` | float/list | 反馈位置值 |
| `data_type` | str | 见下表 |
| `feedback_type` | str | 中文标签（"臂N旋转轴编码器"等） |
| `raw` | dict | rosbridge 原始 msg |
| `id` | str/int | 仅原 msg 含 `id` 时附带 |

**data_type 分类：**

| data_type | 说明 | device_id 范围 |
|-----------|------|---------------|
| `rotation_axis_encoder` | 旋转轴编码器 | 1, 5, 9, 13, 17 |
| `swing_axis_encoder` | 摆动轴编码器 | 2, 6, 10, 14, 18 |
| `telescope_axis_encoder` | 伸缩轴编码器 | 4, 8, 12, 16, 20 |
| `pressure_sensor` | 压力传感器 | 21~25（臂级） |
| `imu_pose` | 陀螺仪姿态 | 21~25（IMU 话题上的臂级） |
| `error` | 连接错误 | -（附 `message` 字段） |

**IMU 姿态额外字段（data_type == "imu_pose" 时）：** `swing_angle, rotation_angle, x, y, z`（float）

**前端消费：** 编码器（`device_id` 33/34/35 或 41/42/43 → 三轴下标 0/1/2）更新 `current`；压力更新 `device[3].current`；IMU 更新 `imuFeedback{swingAngle, rotationAngle, x, y, z}`。

### 3.2 机器人状态 WebSocket（大屏）

| 项目 | 内容 |
|------|------|
| 连接地址 | `ws://{host}/api/ws/ws/robot_status?token={jwt_token}`（⚠ 双层 `/ws`：路由前缀 + 路径叠加） |
| 鉴权 | 是（JWT Token，Query 参数传递；缺失/无效 → `close(1008)`） |
| 方向 | 服务端 → 客户端（单向推送，`send_text`） |
| 数据来源 | 子进程执行 `web_data_node.py` 标准输出 |
| 后端文件 | `app/api/endpoints/ws_stream.py` |

> ⚠ **注意**：`web_data_node.py` 当前**整文件被注释**（约 240 行），实际运行时连接成功但**无任何消息推送**。注释代码中的历史格式：`{time_id, header:{secs,nsecs}, module_id, device_id, position, data_type:"axis_encoder"|"pressure_sensor"|"unknown", id?, feedback_type?}`

---

## 4. ROS 话题与服务映射

### 4.1 前端→后端→ROS（发布方向）

| 业务功能 | 后端接口 | ROS 话题 | 消息类型 | 方向 |
|---------|---------|---------|---------|------|
| 通用测试 | `/ros/send_ros` | `/web_cmd` | std_msgs/String | 发布 |
| 模块确认 | `/module/` | `/control/module_cmd` | robot_control_backend/IntCmd | 发布 |
| 目标图纸 | `/coordination/send` | `/frontend_pointcloud_topic` | std_msgs/String | 发布 |
| 旋转微调 | `/control/finetuning` (rotation) | `/control/adjust_rotation_cmd` | robot_control_backend/RotationCmd | 发布 |
| 摆动微调 | `/control/finetuning` (swing) | `/control/adjust_swing_cmd` | robot_control_backend/SwingCmd | 发布 |
| 伸缩微调 | `/control/finetuning` (telescopic) | `/control/adjust_telescopic_cmd` | robot_control_backend/TelescopicCmd | 发布 |
| 全局急停 | `/control/emergency_stop` | `/control/softstop` | robot_control_backend/IntCmd | 发布 |
| 压力触发 | （控制节点自动） | `/control/sensor_cmd` | robot_control_backend/IntCmd | 发布 |

### 4.2 ROS→后端→前端（订阅/反馈方向）

| 反馈类型 | ROS 话题 | 消息类型 | 推送方式 | 前端接收 |
|---------|---------|---------|---------|---------|
| 旋转轴反馈 | `/hardware/rotation_feedback` | RotationCmd | WebSocket 反馈流 | FineTuningPage |
| 摆动轴反馈 | `/hardware/swing_feedback` | SwingCmd | WebSocket 反馈流 | FineTuningPage |
| 伸缩轴反馈 | `/hardware/telescope_feedback` | TelescopicCmd | WebSocket 反馈流 | FineTuningPage |
| 压力传感器 | `/hardware/sensor_feedback` | SensorCmd | WebSocket 反馈流 | FineTuningPage |
| 陀螺仪姿态 | `/hardware/imu_angles` | TuoLuoYi（GyroFeedback 衍生） | WebSocket 反馈流 | FineTuningPage |
| 模块确认成功 | `/hardware/module_confirm_success` | IntCmd | REST 同步等待 | ModuleManagement |
| 模块确认失败 | `/hardware/web_module_cmd` | IntCmd | REST 同步等待 | ModuleManagement |
| 机器人状态 | `/robot_status` | std_msgs/String | REST 轮询 | RosTestPage |
| 大屏数据流 | （web_data_node 输出，当前已注释） | - | WebSocket 大屏流 | Dashboard |

### 4.3 ROS 内部话题（控制层，robot_control_backend 内部）

| 话题名 | 类型 | 发布者 | 订阅者 | 用途 |
|-------|------|--------|--------|------|
| `/control/kinematics_rotation_cmd` | RotationCmd | kinematics_node | control_node | 逆解旋转指令输入 |
| `/control/kinematics_swing_cmd` | SwingCmd | kinematics_node | control_node | 逆解摆动指令输入 |
| `/control/kinematics_telescopic_cmd` | TelescopicCmd | kinematics_node | control_node | 逆解伸缩指令输入 |
| `/control/kinematics_rotation_cmd_sequenced` | RotationCmd | control_node | rotation_node | 时序旋转指令输出 |
| `/control/kinematics_swing_cmd_sequenced` | SwingCmd | control_node | swing_node | 时序摆动指令输出 |
| `/control/kinematics_telescopic_cmd_sequenced` | TelescopicCmd | control_node | telescopic_node | 时序伸缩指令输出 |
| `/arm/cmd_vel` | IntCmd | feedback_node | hardware_node | 指令汇聚下发 |

---

## 5. 消息格式定义

> 以下定义摘自 `robot_control_backend/msg/*.msg`（队友维护），已逐字段核对一致；对接以 msg 文件为最终权威。

### 5.1 IntCmd.msg —— 整型指令/反馈

```
std_msgs/Header header    # 标准头（时间戳 + 坐标系）
uint8 module_id           # 模块编号 (SEG)
uint16 device_id          # 寻址单元 AXIS：
                          #   0 = 系统级指令
                          #   1~20 = 轴号（4轴ID布局，5臂）
                          #   21~25 = 臂级传感器（臂号 = device_id - 20）
int32[] position          # 位置/数据数组
```

使用场景：模块确认（`/control/module_cmd`，`position=[100]`）、急停（`/control/softstop`，`module_id=0, device_id=0, position=[0x01]`）、压力触发（`/control/sensor_cmd`）、指令汇聚（`/arm/cmd_vel`）。

### 5.2 RotationCmd.msg —— 旋转轴指令/反馈

```
std_msgs/Header header
uint8 module_id           # 模块编号
uint16 device_id          # 旋转轴 J1：AXIS = 1, 5, 9, 13, 17
float64[] position        # 相对增量角度，单位：度；正 = 逆时针
```

### 5.3 SwingCmd.msg —— 摆动轴指令/反馈

```
std_msgs/Header header
uint8 module_id           # 模块编号
uint16 device_id          # 摆动轴 J2：AXIS = 2, 6, 10, 14, 18
float64[] position        # 相对增量角度，单位：度（按 ±MAX_SWING_ANGLE 裁剪为绝对目标）
```

### 5.4 TelescopicCmd.msg —— 伸缩轴指令/反馈

```
std_msgs/Header header
uint8 module_id           # 模块编号
uint16 device_id          # 伸缩轴 J4：AXIS = 4, 8, 12, 16, 20（J3 空置）
float64[] position        # 指令：相对增量 mm；反馈：角度（度）
```

> mm↔度换算由 telescopic_node/kinematics_node 完成。

### 5.5 SensorCmd.msg —— 压力传感器

```
std_msgs/Header header
uint8 id                  # 自增 ID，防止重复
uint8 module_id           # 模块编号
uint16 device_id          # 臂级 AXIS：21~25（臂号 = device_id - 20）
float64[] position        # 压力数据，单位：N（牛顿）
```

### 5.6 Feedback.msg —— CAN 原始反馈

```
std_msgs/Header header
uint8 module_id           # 模块编号
uint16 device_id          # 1~20 = 轴号，21~25 = 臂级
float64[] position        # 绝对角度（0.01°），V2 不再使用编码器计数
```

> hardware_node 发布的原始 CAN 数据，feedback_node 换算为度后转发到各 `*_feedback` 话题。

### 5.7 GyroFeedback.msg —— 陀螺仪反馈（IMU 原始量）

```
std_msgs/Header header
uint8 module_id
uint16 device_id          # 臂级 IMU：AXIS = 21~25
float32 accel_x/y/z       # 线性加速度 (m/s^2)
float32 gyro_x/y/z        # 角速度 (°/s)
```

### 5.8 TuoLuoYi.msg —— IMU 姿态（`/hardware/imu_angles` 实际类型）

```
std_msgs/Header header
uint8 module_id
uint16 device_id          # 臂级 IMU AXIS：21~25
float64 swing_angle       # 摆动角（度），前倾为正
float64 rotation_angle    # 旋转角（度），顺时针为正
float64 x/y/z             # 末端世界坐标 (cm)
```

### 5.9 Heartbeat.msg —— 节点心跳

```
std_msgs/Header header
uint8 module_id           # 模块号 (SEG)
uint16 node_id            # CAN NODE 号（0=广播 1=主控 2~21=驱动），与轴/臂级寻址区分
uint8 state               # 0=BOOT 1=IDLE 2=RUN 3=FAULT
uint32 run_axis_mask      # 运行轴掩码（bit0..bit19 对应轴1~轴20）
uint32 base_valid_mask    # 基准有效掩码
```

### 5.10 CmdAck.msg —— 命令应答

```
std_msgs/Header header
uint8 module_id
uint16 device_id          # 轴号 1~20
uint8 ack_msg             # 对应的下行命令 MSG 号
uint8 result              # 0=接受 1=轴忙 2=基准无效 3=参数越界 4=轴故障 5=急停锁存
uint8 detail              # 详细信息（越界轴号等）
```

---

## 6. device_id 与 module_id 编码规则

### 6.1 device_id（AXIS 寻址单元）

V2 中 `device_id` 直接等于 CAN ID 的 AXIS 寻址单元（不再使用 `node*100+axis` 复合编码）：

```
0           → 系统级指令（急停/急停解除/模块安全停）

轴级 1~20   → 4轴ID布局，5臂 × 4轴地址（每臂：J1旋转 / J2摆动 / J3空置 / J4伸缩）
  臂1: 1(旋转) 2(摆动) 3(空置) 4(伸缩)      臂4: 13 / 14 / 15 / 16
  臂2: 5 / 6 / 7 / 8                        臂5: 17 / 18 / 19 / 20
  臂3: 9 / 10 / 11 / 12

臂级 21~25  → 压力传感器 + IMU（同一 device_id，按话题区分）
  臂号 = device_id - 20
```

**计算规则：**
- 臂索引：`arm_idx = (device_id - 1) // 4`（0~4，共 5 臂）
- 关节类型：`device_id % 4` → 1=旋转, 2=摆动, 0=伸缩, 3=空置(J3)
- 臂级传感器：`device_id - 20` = 臂号

**前端残留映射（FineTuningPage.vue 硬编码）：**

```typescript
const feedbackDeviceIndex: Record<number, number> = {
  33: 0, 34: 1, 35: 2,   // 旧版 V1 编码残留
  41: 0, 42: 1, 43: 2,   // 前端模拟/测试用
};
```

> ⚠ 前端硬编码 `deviceId: 41/42/43` 与 V2 的 1~20 轴号规范不一致，仅在 noRosDebug 模式下使用；真实 ROS 环境需从设备树动态获取正确轴号。

### 6.2 module_id（模块编号）

**V2 规则：module_id 由前端计算并透传，后端不再写死默认值。**

```typescript
// ModuleManagement.vue，x, y ∈ [1, 8]，8x8 模块矩阵
const xyToModuleId = (x: number, y: number): number => x * 16 + y;
```

示例：(1,1)→17、(1,2)→18、(2,3)→35、(8,8)→136。

配置文件旧默认值 `ROS_COMM_MODULE_ID=17` 已废弃（V2 不使用）。

**module_id 传递链路：** 前端计算 → `/control/module_cmd`（IntCmd.module_id）→ 微调指令（RotationCmd/SwingCmd/TelescopicCmd.module_id）→ 反馈回流（由 CAN 帧 SEG 位域决定，前端按 device_id 匹配）。

---

## 7. 前端调用位置汇总

### 7.1 API 封装层（`src/api/rosApi.ts`）

| API 函数 | 后端接口 | 调用页面 | 用途 |
|---------|---------|---------|------|
| `sendRosMessage(msg)` | GET /ros/send_ros | RosTestPage | 测试 ROS 消息下发 |
| `getRosStatus()` | GET /ros/get_ros_status | RosTestPage | 获取 ROS 状态 |
| `createModule(data)` | POST /module/ | ModuleManagement, RosTestPage | 模块锁定确认 |
| `sendCoordination(data)` | POST /coordination/send | FineTuningPage, RosTestPage | 目标图纸下发 |
| `sendFineTuning(data)` | POST /control/finetuning | FineTuningPage, RosTestPage | 单轴微调 |
| `testSerialConnection()` | GET /control/serial_test | MainPage（顶栏） | 串口测试 |
| `saveFineTuningConfig(data)` | POST /finetuning/config | FineTuningPage | 保存微调配置 |
| `getFineTuningConfig(params)` | GET /finetuning/config | - | 查询微调配置 |
| `getDeviceListApi()` | GET /device/ | ModuleManagement, FineTuningPage | 获取设备列表 |
| `getUnitsByDeviceApi(deviceId)` | GET /unit/by_device/{id} | FineTuningPage | 获取机械臂列表 |
| `getDrawingListApi()` | GET /drawing/ | FineTuningPage 等 | 获取图纸列表 |

### 7.2 WebSocket 连接位置

| 连接 URL | 所在文件 | 用途 |
|---------|---------|------|
| `/api/control/feedback/ws` | `FineTuningPage.vue` | 实时反馈流（编码器/压力/IMU） |
| `/api/ws/ws/robot_status?token=...` | ws_stream 端点定义，前端暂未明确调用 | 大屏机器人状态流 |

### 7.3 核心页面调用流程

**模块管理（ModuleManagement.vue）：** 8x8 矩阵选坐标 → `module_id = x*16+y` → `getDeviceListApi()` 匹配设备取 `Device_ID` → `createModule({x, y, module_id, device_id, position:0})` → 成功跳转 FineTuningPage（携带 query）

**微调页面（FineTuningPage.vue）：** 从 route.query 取 `module_id/device_id/x/y` → 并行 `getUnitsByDeviceApi()` + `getDrawingListApi()` → 强制弹窗选机械臂/图纸 → `sendCoordination()` 下发图纸获取点云视图 → 建立 WS `/api/control/feedback/ws` → 调整三轴 `sendFineTuning()`（rotation/swing/telescopic）→ WS 实时更新 → `saveFineTuningConfig()` 保存

**其他页面**：`AsidePage` 长按 2 秒急停 → `POST /control/emergency_stop`；`RosTestPage` 免登录联调各接口。

---

## 8. 注意事项与潜在问题

### 8.1 device_id 编码不一致

| 位置 | device_id 范围 | 说明 |
|------|---------------|------|
| ROS 消息定义 (V2) | 1~20 (轴级), 21~25 (臂级) | 规范定义 |
| rosbridge_gateway.py 校验 | 1~20（微调接口） | V2 严格校验 |
| FineTuningPage.vue 默认值 | 41, 42, 43 | 前端硬编码，与规范不一致 |
| FineTuningPage.vue 映射表 | 33, 34, 35 / 41, 42, 43 | 旧 V1 编码残留 |
| noRosDebug 模拟 | 41/42/43 (轴), 50 (IMU) | 调试模式模拟数据 |

### 8.2 两套 ROS 下发路径并存

| 机制 | 实现文件 | 适用接口 | 状态 |
|------|---------|---------|------|
| rosbridge WebSocket | `rosbridge_gateway.py` | 微调、模块确认、图纸下发、急停 | **主路径（V2）** |
| rospy 直接发布 | `ros_service.py` | `/ros/send_ros` 通用接口 | 旧路径（测试用） |
| 子进程调用脚本 | `ros_control.py` | 串口测试、硬件状态、大屏流 | 辅助工具 |
| 外部命令/mock | `ros_dispatcher.py` | 适配层（当前实际绑定 rosbridge） | 遗留 |

### 8.3 无 ROS 调试模式

- 开关：`VITE_DEBUG_NO_ROS=true`（.env.development）
- 影响接口：模块列表、机械臂列表、图纸列表、模块确认、坐标下发、微调
- 模拟实现：`src/api/noRosDebug.ts`，不连接真实 WebSocket

### 8.4 白名单接口（无需鉴权，前后端配置联动）

前端 `src/utils/request.ts` 白名单（不带 token 发请求）：
`/login, /register, /send_ros, /get_ros_status, /module, /coordination, /finetuning, /device`

> ⚠ **安全风险**：`/module/`、`/coordination/send`、`/control/finetuning` 等核心控制接口后端也未鉴权（Mimosa 扫描同样报出）。若后端加鉴权，必须同步缩减前端白名单，否则会断。

### 8.5 响应格式不统一

- 大部分接口返回 `{ code, message, data }`
- `/control/emergency_stop` 返回 `{ success, message, timestamp }`
- `/control/hardware/realtime` 直接返回 `HardwareFeedback` 模型
- 前端使用多种兼容判断（`Array.isArray(res)` / `res.data` / `res.code`）

### 8.6 WebSocket 鉴权差异

| WebSocket | 鉴权方式 |
|-----------|---------|
| `/control/feedback/ws` | 无鉴权，直接连接 |
| `/ws/ws/robot_status` | JWT Token（Query 参数） |

### 8.7 点云视图服务依赖

- 坐标下发后等待点云视图生成（最长 5 秒超时，超时 504）
- 服务地址：`POINTCLOUD_VIEW_BASE_URL`（默认 `http://localhost:5000`），独立进程，不在 ROS 节点体系内

### 8.8 其他工程问题

- **大屏 WS 无数据**：`web_data_node.py` 整文件被注释（见 3.2）
- **work/workflow 写接口参数走 query string** 而非 JSON body；`work_ids` 是 JSON 数组字符串
- **types.ts 的 `UserInfo` 与登录实际响应不一致**（`username/role/email...` vs `account/name/typeId/headImage...`）
- **遗留死代码**：`AddItem.vue`（调用不存在的 `/hardware` 接口）；`GET /finetuning/`、`GET /finetuning/config`、`GET /drawing/{id}`、`GET /task/{id}` 已封装但页面未调用
- **微调写库 `creater_id=1` 写死**，不区分实际操作人

### 8.9 与基准文档的差异核对

| # | 基准文档表述 | 代码核对结果 | 处理 |
|---|---|---|---|
| 1 | `/finetuning/`、`/finetuning/config` 鉴权"是" | `finetuning.py` 无 `get_current_user` 依赖，前端白名单不带 token 调用 | **修正为免认证**（2.4 表） |
| 2 | `/hardware/imu_angles` 类型 "GyroFeedback (衍生)" | `tuo_luo_yi.py` 以 `robot_control_backend/TuoLuoYi` 类型发布（输入才是 GyroFeedback） | **修正**（3.1、4.2、5.8） |
| 3 | 大屏 WS 数据源 `web_data_node.py` | 该脚本整文件被注释，连接成功但无推送 | **补充警示**（3.2、8.8） |
| 4 | 其余接口字段、消息定义、编码规则 | 逐项核对一致 | 采纳 |

---

## 9. 业务管理接口（基准补充）

> 基准文档聚焦 ROS 通信链路；本节补充与 ROS 无直接关系的业务 CRUD 接口（已核对代码）。响应统一 `{code, message, data}`。

### 9.1 认证与用户 `/login` `/register` `/user`

- **POST `/api/login`**（免认证，form-urlencoded）：`username`, `password` → `data:{account, name, typeId, token, tokenType:"bearer", headImage, updateTime}`
- **POST `/api/register`**（免认证）：`username`(≥3), `password`(≥6) → `data:{account}`；新用户 `Type_ID=2`
- 用户序列化 `user_to_dict`：`id, account, username, name, typeId, typeLabel, headImage, isLock, birthday, sex, creatorId, createtime, locktime, modifytime, delFlag, notes`

| 端点 | 认证 | 请求字段 |
|---|---|---|
| GET `/api/user/me` | 登录 | 无 |
| GET `/api/user/` | 登录 | query：`keyword?`, `type_id?`(0=全部) |
| POST `/api/user/` | **admin** | body：`username`(≥3), `password`(≥6), `type_id=2`, `name?` |
| POST `/api/user/password` | 登录 | body：`old_password`, `new_password`(≥6) |
| POST `/api/user/avatar` | 登录 | multipart：`file`(image/*, ≤2MB) |
| PUT `/api/user/profile/me` | 登录 | body 可选：`name`, `birthday`, `sex`, `type_id`(仅 admin 本人生效) |
| PUT `/api/user/{id}` | **admin** | body 可选：`username`, `type_id`, `password`, `name` |
| DELETE `/api/user/{id}` | **admin** | 软删除（不能删自己/admin） |
| PUT `/api/user/{id}/lock`、`/unlock`、`/role` | **admin** | role body：`type_id`(1/2) |
| POST `/api/user/import` | **admin** | multipart：`file`(.csv，表头 `username,password[,type_id]`) → `{successCount, failCount, failList, users}` |
| GET `/api/user/export` | **admin** | CSV 文件流 |

### 9.2 仪表盘、图纸、工作/工作流/任务

- **GET `/api/dashboard/stats`**（免认证）→ 7 项 `{label, value, unit, trend}`：`deviceStatus, taskCount, faultCount, onlineUsers, responseTime, concurrency, deviceConnections`
- **图纸 `/drawing`（登录）**：`drawing_to_dict` = `drawingId, drawingName, drawingDescription, drawingFile, creatorId, createTime, modifyTime, latestVersionId, delFlag, notes`
  - GET `/`（query `keyword?`）、GET `/{id}`、GET `/{id}/versions`、GET `/{id}/file` → `{content(前10000字符), fullLength, truncated}`
  - POST `/import`（FormData：`drawing_name`✔, `drawing_description`, `drawing_id?`(有则追加新版本), `file`(.json)✔）
  - PUT `/{id}`（FormData：`drawing_name?`, `drawing_description?`, `notes?`）、DELETE `/{id}`（软删除）
- **工作 `/work`（登录，⚠ 参数走 query string）**：`work_to_dict` = `Work_ID, Workname, WorkDescript, Drawing_ID, Module_ID, Device_id(=Module_ID), unit_id, sensor_id, data, creater_id, Createtime, Modifytime, del_flag, Notes`
  - POST `/create`：`Workname`✔, `WorkDescript`, `Drawing_ID?`, `Module_ID?`, `Device_id?`, `unit_id?`, `sensor_id?`, `data`(JSON 字符串), `Notes`
  - GET `/list`（query `keyword?`）、PUT `/{id}`、DELETE `/{id}`
- **工作流 `/workflow`（登录，⚠ query string）**：`workflow_to_dict` = `Workflow_ID, Workflowname, WorkflowDescript, creater_id, Createtime, Modifytime, del_flag, Notes`
  - POST `/create`：`Workflowname`✔, `WorkflowDescript`, `Notes`, `work_ids`（**JSON 数组字符串**，按序写 `flow_seq`）
  - GET `/list`（附 `work_count`）、GET `/{id}`（附 `works:[...+flow_seq]`）、PUT `/{id}`、DELETE `/{id}`
- **任务 `/task`（登录，JSON body）**：`task_to_dict` = `Task_ID, Taskname, Taskdescripte, Workflow_ID, Drawing_ID, creater_id, Createtime, TaskAssignment_id, Status, Modifytime, del_flag, Notes`（列表附 `DrawingName, WorkflowName, AssigneeName, WorksSubset`）
  - 状态机：`"0"`就绪 `"1"`运行 `"2"`暂停 `"3"`结束
  - POST `/create`：`Taskname`✔, `Taskdescripte?`, `Workflow_ID?`, `Drawing_ID?`, `TaskAssignment_id?`, `Notes?`
  - GET `/list`（query `keyword?, status?, drawing_id?, workflow_id?`）、GET/PUT/DELETE `/{id}`
  - POST `/{id}/start|pause|resume|finish|dispatch`（dispatch：仅 "0" 可调度，其余运行中任务置 "2"）
  - GET `/{id}/tracing`（operate_type：0 启动/1 暂停/2 唤醒/3 结束/4 进度/5 调度/6 删除）、GET `/{id}/works`、POST `/{id}/progress`（body `Notes`✔；前端将工件记录 JSON 字符串化存入）

### 9.3 设备四层 CRUD `/model` `/device` `/unit` `/sensors`（均免认证）

- **型号**：`Model_ID, Modelname, Modeldescripte, creater_id, Createtime, del_flag, Notes, Type_ID, Typename, Typedescripte`；GET `/`、GET `/tree`（四级树 `model→device→unit→sensor`）、GET/PUT/DELETE `/{id}`、POST `/`（`Modelname`✔）
- **模块**（Module 表别名）：`Device_ID, Model_ID, DeviceAddress(int), Devicedescript, ...`；GET `/`、GET `/by_model/{id}`、GET/PUT/DELETE `/{id}`、POST `/`（`Model_ID`✔, `DeviceAddress`✔=(x<<4)\|y；坐标冲突 409）
- **机械臂**：`id, Unit_ID, UnitDescript, Module_ID, ...`；GET `/`、GET `/by_device/{id}`、GET/PUT/DELETE `/{id}`、POST `/`（`Unit_ID`✔, `Module_ID`/`Device_ID` 二选一；同模块重复 409）
- **传感器**：`id, sensor_ID, sensordescript, IsRead, Module_ID, Unit_ID, Unit_address, ...`；GET `/`、GET `/by_unit/{id}`、GET/PUT/DELETE `/{id}`、POST `/`（`sensor_ID`✔, `Unit_ID`✔, `Unit_address`✔；同模块重复 409）
- `/model/tree` 节点结构（`TreeNode`）：`{id:"model-<Type_ID>"|"device-<Module_ID>"|"unit-<id>"|"sensor-<id>", label, type, raw_id, arm_type?, sensor_type?, module_id?, device_id?, children?}`

---

## 10. 数据库表字段（基准补充）

SQLite（`ros_database.db`，项目根），17 张表，模型在 `app/db/models.py`，建库种子脚本 `sqlite_create.py`。时间字段 `DateTime(timezone=True)` 默认 `now()`；普遍带软删除 `del_flag` 与 `Notes`。

| 表 | 关键字段 | 说明 |
|---|---|---|
| `Users` | User_ID(PK), Username, Password(bcrypt), Type_ID(1=管理员/2=操作员), Creator_ID(自引用FK), Createtime, Islock, Locktime, Name, Headimage, Birthday, Sex, Modifytime, del_flag, Notes | 用户 |
| `fine_tuning` | id(PK), module_id+unit_id(联合FK→Unit), module_address?, module_descript?, parameter_name(rotation/swing/telescopic), old_value?, new_value, creater_id→Users, create_time, notes, del_flag | 微调记录 |
| `fine_tuning_config` | id(PK), module_id, unit_id, sensor_id(联合FK), config_json(整份JSON), creater_id, ... | 微调配置快照 |
| `Drawings` | Drawing_ID(PK), Drawingname, Drawingdescripte, Drawingfile(路径), Creator_ID→Users, Createtime, Modifytime, NewVersion_ID→DrawingsVersion, del_flag | 图纸 |
| `DrawingsVersion` | DrawingsVersion_ID(PK), Drawing_ID→Drawings, Drawingfile, Creator_ID, Modify_ID, ... | 图纸版本 |
| `works` | Work_ID(PK), Workname, WorkDescript, Drawing_ID?, Module_ID?, unit_id?(→Unit.id), sensor_id?(→sensors.id), data, creater_id, ... | 工作 |
| `workflows` | Workflow_ID(PK), Workflowname, WorkflowDescript, creater_id, ... | 工作流 |
| `work_flow_relations` | work_flow_relation_ID(PK), Workflow_ID, Work_ID, flow_seq(执行顺序), ... | 工作流-工作关系 |
| `Type` | Type_ID(PK), Typename, Typedescripte, ... | 自适应工装型号 |
| `Module` | Module_ID(PK), Type_ID→Type, Moduledescript, ModuleAddress(=(x<<4)\|y), ... | 模块 |
| `Unit` | id(PK 代理), Unit_ID(业务臂号 32/64/96), UnitDescript, Module_ID→Module；Unique(Module_ID,Unit_ID) | 机械臂 |
| `sensors` | id(PK 代理), sensor_ID(业务号), sensordescript, IsRead, Module_ID+Unit_ID(联合FK→Unit), Unit_address；Unique(Module_ID,sensor_ID) | 传感器（每臂 8 类） |
| `sensor_log` | Createtime+sensor_id(复合PK), creater_id, Work_ID, isread, data, ... | 传感器日志 |
| `Tasks` | Task_ID(PK), Taskname, Taskdescripte, Workflow_ID?, Drawing_ID?, creater_id, TaskAssignment_id?(指派人), Status("0"~"3"), ... | 任务 |
| `TasksTracing` | TasksTracing_ID(PK), Task_ID, operate_type, Workflow_ID, operater_ID, operate_time, Notes | 任务跟踪 |
| `calculation` | Createtime(PK), creater_id, Work_ID, Module_ID?, Unit_ID?, device_ID?, isread, coord, position, ... | 计算解析日志 |
| `point_data` | Createtime(PK), creater_id, Module_ID?, point, arms_address, ... | 点云解析数据 |

> 注意：`schemas/device.py`、`schemas/model.py` 的 `Device_*`/`Model_*` 是 **Module 表 / Type 表的对外别名**，库中无独立 Devices/Model 表。种子数据：`admin`(1)/`system`(2) 密码 `123456`、Module_ID=17、三臂 Unit_ID=32/64/96、每臂 8 传感器。

---

## 11. 认证矩阵（基准补充）

| 级别 | 接口 |
|---|---|
| 免认证 | `POST /login`、`POST /register`、`GET /dashboard/stats`、`/finetuning/**`、`POST /module/`、`POST /control/finetuning`、WS `/control/feedback/ws`、`/coordination/**`、`/ros/**`、`/model/**`、`/device/**`、`/unit/**`、`/sensors/**`、`GET /api/uploads/**` |
| 登录即可 | `/user/me`、`GET /user/`、`POST /user/password`、`POST /user/avatar`、`PUT /user/profile/me`、`/drawing/**`、`/work/**`、`/workflow/**`、`/task/**`、`GET /control/serial_test`、`GET /control/hardware/realtime`、`POST /control/emergency_stop` |
| 管理员（`Type_ID==1`） | `POST /user/`、`PUT /user/{id}`、`DELETE /user/{id}`、`lock`、`unlock`、`role`、`POST /user/import`、`GET /user/export` |

认证机制：OAuth2 Bearer Token（`tokenUrl=/api/login`）+ JWT（HS256，payload `{sub, exp}`），bcrypt 密码哈希；WS 用 query `token` 校验。

---

## 附录：关键文件索引

### 后端 (ros_mes_hou)

| 文件路径 | 作用 |
|---------|------|
| `app/main.py` | FastAPI 应用入口，启动 ROS 线程 |
| `app/api/api.py` | API 路由总装配 |
| `app/api/endpoints/control.py` | 微调控制 + 反馈 WebSocket + 急停 |
| `app/api/endpoints/coordination.py` | 目标图纸下发 + 点云视图 |
| `app/api/endpoints/module.py` | 模块锁定确认 |
| `app/api/endpoints/ros.py` | ROS 通用测试接口 |
| `app/api/endpoints/finetuning.py` | 微调记录 CRUD（数据库） |
| `app/api/endpoints/ws_stream.py` | 大屏 WebSocket 流 |
| `app/api/endpoints/user.py` / `task.py` / `workflow.py` / `drawing.py` | 业务管理接口 |
| `app/api/deps.py` | `get_current_user` / `get_current_admin` 鉴权依赖 |
| `app/services/rosbridge_gateway.py` | **核心：rosbridge 网关，消息构造与下发** |
| `app/services/ros_control.py` | 硬件控制（急停、串口测试、硬件状态） |
| `app/services/ros_service.py` | 旧版 rospy 直接发布 |
| `app/services/ros_dispatcher.py` | ROS 分发适配层（mock/command 模式） |
| `app/schemas/finetuning.py` / `hardware.py` | 微调 / 硬件反馈 Pydantic 模型 |
| `app/db/models.py` | 17 张表 SQLAlchemy 模型 |
| `app/core/config.py` / `security.py` | 配置项 / JWT 与密码 |

### 前端 (ros_mes_front)

| 文件路径 | 作用 |
|---------|------|
| `src/api/rosApi.ts` | 所有 API 接口封装 |
| `src/api/types.ts` | TypeScript 类型定义 |
| `src/api/noRosDebug.ts` | 无 ROS 调试模式模拟数据 |
| `src/utils/request.ts` | Axios 实例 + 拦截器 + 白名单 |
| `src/stores/user.ts` | 登录态（`account/nickname/role/token/avatar/updateTime`，同步 localStorage） |
| `src/components/Main/ModulePage/FineTuningPage.vue` | **核心：微调页面（REST + WebSocket）** |
| `src/components/Main/ModulePage/ModuleManagement.vue` | 模块管理（8x8 矩阵 + 锁定下发） |
| `src/components/Main/RosTestPage.vue` | ROS API 测试页面（免登录） |
| `.env.development` / `vite.config.ts` | 开发环境配置 / 开发代理 |

### ROS 包 (robot_control_backend，队友维护)

| 文件路径 | 作用 |
|---------|------|
| `msg/IntCmd.msg`、`RotationCmd.msg`、`SwingCmd.msg`、`TelescopicCmd.msg`、`SensorCmd.msg`、`Feedback.msg`、`GyroFeedback.msg`、`TuoLuoYi.msg`、`Heartbeat.msg`、`CmdAck.msg` | 消息定义（本文档第 5 节来源） |
| `scripts/control_node.py` | 控制节点（逆解时序 + 微调转发） |
| `scripts/feedback_node.py` | 反馈节点（角度换算 + 指令汇聚） |
| `scripts/tuo_luo_yi.py` | IMU 姿态换算与发布 |
| `scripts/rosbridge_wrapper.py` | rosbridge 封装 |
| `rob_arm.env` | ROS 话题与硬件参数配置 |
