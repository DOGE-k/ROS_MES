# ROS_MES 前后端接口字段文档

维护范围：Vue 前端和 FastAPI 业务后端。2026-11-05 整理；当前代码及双方已确认契约是核查依据，历史测试结果不能代替当前实现验证。前后端任务先读[开发入口](../AGENTS.md)，最近变更见[改动记录](ROS_MES_前后端改动记录.md)。

本文件由早期团队基准（2026-10-05、前后端 v1.1/`b03b57a`）演进而来。原四轴话题、消息格式和编码章节已失效，本次移除重复正文，统一引用根 `docs/` 的[三轴版 V2.1 共享契约](../../docs/ROS_MES_前后端ROS接口清单_三轴版_V2.1.md)。ROS/CAN 资料和跨系统报告仍在原位置，本文件不另立 ROS 协议权威。

## 阅读导航

- [整体架构](#1-整体架构)
- [控制与微调 REST 接口](#2-rest-api-接口前端后端ros)
- [WebSocket 与反馈语义](#3-websocket-接口)
- [编号边界及外部契约](#4-编号边界及外部契约)
- [代码入口](#5-代码入口)
- [运行与兼容注意事项](#6-运行与兼容注意事项)
- [版本适配](#7-ros1ros2-适配)
- [业务管理接口](#9-业务管理接口基准补充)
- [数据库字段](#10-数据库表字段基准补充)
- [认证矩阵](#11-认证矩阵基准补充)

## 1. 整体架构

前端 `ros_mes_front`（Vue/TypeScript）通过 `/api` HTTP 和后端 WebSocket 访问 `ros_mes_hou`（FastAPI/SQLite）。业务后端经 `app/ros/` 适配层连接 rosbridge；前端不直接连接 rosbridge。默认端口：前端 5173、后端 8000、rosbridge 9010、点云视图服务 5000。

| 配置 | 环境变量/默认 | 说明 |
|---|---|---|
| 前端开发代理 | `VITE_API_TARGET` | `/api` HTTP/WS 同源代理，默认 `http://127.0.0.1:8000` |
| rosbridge | `ROSBRIDGE_URL`，`ws://localhost:9010` | 后端连接地址 |
| API 前缀 | `API_STR=/api` | 接口表省略此前缀 |
| JWT | `MES_SECRET_KEY`、`MES_TOKEN_EXPIRE_MINUTES` | 凭据不写文档，默认有效期 60 分钟 |
| 点云视图服务 | `POINTCLOUD_VIEW_BASE_URL=http://localhost:5000` | 后端图片代理目标 |
| 数据库 | `DATABASE_URL` | 默认项目根 `ros_database.db`，不要运行种子脚本覆盖现有数据 |
| ROS 版本 | `ROS_VERSION=1` 或 `2` | 类型串和时间戳差异集中在 `app/ros/profile.py` |
| 无 ROS 模拟 | `VITE_DEBUG_NO_ROS=true` | 前端开发模拟，与个人中心“跳过图纸绑定”开关独立 |

## 2. REST API 接口（前端→后端→ROS）

> 所有接口均通过 `baseURL: /api` 访问，多数返回 `{ code, message, data }`；急停/解除等历史接口使用独立响应模型，以各节为准。路径均省略 `/api` 前缀

### 2.1 ROS 通用测试接口

| 序号 | 接口路径 | 方法 | 鉴权 | 对应 ROS 话题 | 用途 |
|------|---------|------|------|-------------|------|
| 1 | `/ros/send_ros` | GET | 否（白名单） | `/web_cmd` (std_msgs/String) | 通用 ROS 消息下发测试 |
| 2 | `/ros/get_ros_status` | GET | 否（白名单） | `/robot_status` 订阅 | 获取 ROS 节点运行状态 |

**接口 1：发送 ROS 消息**
- 请求参数：`msg: string`（Query 参数）
- 响应：`{"code":200, "message":"已发送到 ROS：xxx", "data":{"topic":"/web_cmd", "command":"send_ros", "payload":{"msg":"xxx"}}}`
- 后端实现：`app/ros/rosbridge.py` → `publish_web_cmd()`
- 发布内容：JSON 字符串 `{"command": "send_ros", "payload": {"msg": "..."}}`

**接口 2：获取 ROS 状态**
- 请求参数：无
- 响应：`{"code":200, "message":"获取 ROS 状态成功", "data":{"robot_status":"unknown", "battery":85, "node":"ros_mes_api_server", "ros_ready":true/false}}`
- 后端实现：`app/ros/rosbridge.py` 的状态订阅器 → `native_status` 快照

---

### 2.2 模块锁定与确认接口

| 序号 | 接口路径 | 方法 | 鉴权 | 对应 ROS 话题 | 用途 |
|------|---------|------|------|-------------|------|
| 3 | `/module/` | POST | 否（白名单） | `/control/module_cmd` (IntCmd) | 锁定目标模块并下发确认指令 |

**接口 3：模块锁定下发**

正常模式的页面调用时机（无图纸调试例外见 §2.6）：模块管理页只选模块并导航，不下发确认；微调页首次配置弹窗可选择 1~5 台机械臂和一张图纸，先调用本接口（`unit_ids` 为所选 `Unit_ID` 数组），确认成功后再为每台确认成功的机械臂调用 §2.3 的图纸下发接口。微调主页面只在本次确认成功的机械臂之间切换；后端仍支持多个 `unit_ids` 的顺序确认。

- 请求体（业务层字段；ROS 的 `seg/arm/position` 不由前端传递）：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `x` | int | ✔（或别名） | X 坐标 (1~8)；别名 `X/targetX/moduleX/col` 或 `position.x` |
| `y` | int | ✔（或别名） | Y 坐标 (1~8)；别名 `Y/targetY/moduleY/row` 或 `position.y` |
| `module_id` | int | 可选 | 默认 `x*16+y` |
| `device_id` | int | 可选 | 设备 ID |
| `unit_ids` | int[] | ✔ | 本次确认的机械臂 `Unit_ID` 列表；页面可传 1~5 台，后端按顺序逐个确认 |
| `position` | int | 可选 | 位置（前端传 0）；也可传对象 `{x, y}` |

- 响应：

```json
{
  "code": 200,
  "message": "module locked and confirmation command dispatched",
  "data": {
    "x": 1, "y": 2, "module_id": 18, "device_id": 1,
    "unit_ids": [32, 64, 96], "position": 0, "raw": {}, "seg": 0,
    "confirmations": [
      {"unit_id": 32, "arm": 1, "confirmed": true},
      {"unit_id": 64, "arm": 2, "confirmed": true},
      {"unit_id": 96, "arm": 3, "confirmed": true}
    ]
  },
  "dispatch": {
    "action": "module_confirm", "confirmed": true, "count": 3,
    "confirmations": [
      {"unit_id": 32, "arm": 1, "confirmed": true},
      {"unit_id": 64, "arm": 2, "confirmed": true},
      {"unit_id": 96, "arm": 3, "confirmed": true}
    ]
  }
}
```

如果某台机械臂确认失败，接口返回 HTTP 502，`detail` 中包含 `failed_unit_id`、`failed_arm`、已确认的 `confirmed_unit_ids`、尚未处理的 `pending_unit_ids` 和 `reason`；后端不会继续下发后续机械臂。

- ROS 下行及回执细节引用[共享三轴契约](../../docs/ROS_MES_前后端ROS接口清单_三轴版_V2.1.md)，本节只定义业务请求和 HTTP 结果。
- 业务接口不使用 `station`、`seg` 或 ROS `arm` 字段。后端按 `unit_ids` 逐个下发；同一时间只确认一台未绑定机械臂。`ROS_MODULE_SEG_MAP` 缺少目标模块映射，或 `unit_id` 无法映射为 1~5 的 ROS `arm` 时，直接返回 422。
- 确认结果来自模块握手回执，不能与普通微调的“仅发送”结果混用；响应中的 `data.seg` 是本次确认采用的组号，前端可用于核验已知硬件反馈的归属。
- x/y 缺失、`unit_ids` 为空、模块 SEG 映射缺失或映射出的 `arm` 不在 1~5 → 422

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
- 流程：校验参数 → 查库取图纸路径 → 转相对路径 → rosbridge 发布 → 等待点云三视图生成（最长 5 秒，超时 504）

正常模式页面顺序为“选模块 → 多选 1~5 台机械臂和一张图纸 → 批量机械臂确认 → 按臂图纸下发 → 微调”。全部确认和图纸下发成功后进入微调页；主页面提供机械臂切换和重新下发图纸入口，已确认机械臂的图纸、三视图和微调状态按臂分别保留于本次页面会话中。切换机械臂不会再次弹出选择框；重新下发只作用于当前机械臂。请求进行中禁用目标切换，避免数据串臂。

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

> ⚠ **修正**：基准文档将 7/8 标为"鉴权：是"。经核对 `app/api/endpoints/finetuning.py` 无 `get_current_user` 依赖，且前端 `request.ts` 白名单对 `/finetuning` 不带 token 调用——实际**全部免认证**。2026-11-05 复核：前端虽然有 GET `/finetuning/config` 封装，后端尚未实现该查询端点；本次只扩展保存接口。

**接口 6：微调控制（主路径）**
- 请求体：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `module_id` | int | ✔ | 模块编号（V2 要求 > 0） |
| `device_id` | int | ✔ | 轴号 1~15；兼容别名 `Device_ID` 自动映射 |
| `unit_id` | int | ✔ | 机械臂 ID |
| `parameter_name` | str | ✔ | `"rotation"` \| `"swing"` \| `"telescopic"` |
| `position` | float | ✔ | 调整量（度/mm）；兼容别名 `new_value` 自动映射 |

- 响应：

```json
{
  "code": 200, "message": "微调指令已发送；尚无设备确认",
  "data": [
    { "device_id": 1, "position": 5.0, "type": "axis", "parameter_name": "rotation" },
    { "device_id": -1, "position": 0.0, "type": "pressure" }
  ],
  "dispatch": { "sent": true, "confirmed": null, "confirmation_status": "not_requested" }
}
```

- 约束：`device_id` ∈ 1~15，`module_id` > 0，`parameter_name` 为上述三者之一；构造校验失败 422，发送失败 502。下发 `position` 是增量，旋转/摆动为度，伸缩为 mm。
- `dispatch.sent=true` 只表示后端已向 rosbridge WebSocket 写出发布消息；普通微调/图纸发布为 `confirmed=null`、`confirmation_status="not_requested"`，没有等待设备确认。模块确认分支单独等待真实握手回执。
- `data` 中轴位置是请求回显，压力 0 是历史兼容占位，**都不是设备实测值**。真实模式前端只消费有效 ROS 反馈更新实际值；已发送、设备接受、运动完成必须分别理解。
- 微调记录在发送前写库，记录存在不证明指令发送成功或设备执行成功。HTTP 错误也不能据此自动重发增量指令。
- ROS 话题、消息及编号契约见[共享三轴清单](../../docs/ROS_MES_前后端ROS接口清单_三轴版_V2.1.md)，本侧实现/使用状态见[对接状态清单](后端与ROS接口对接状态清单.md)。

**接口 7/8 字段**：
- POST `/finetuning/`：`module_id`(✔)、`unit_id`(✔)、`device_id/Device_ID`?、`position/new_value`(至少其一)、`parameter_name`?（缺省自动生成 `module_<m>_unit_<u>_position`）、`old_value`?（缺省取最近一次 new_value）→ 返回 `FineTuningResponse[]`（GET 列表：`id, module_id, unit_id, module_address?, module_descript?, parameter_name, old_value?, new_value, creater_id, create_time?, notes?, del_flag`）
- POST `/finetuning/config`：`module_id`(✔)、`unit_id`(✔)、`sensor_id`(可由 `device_id`/`devices[0]` 兜底)、`device_id?`、`is_debug=false`、`drawing_id=null`（传值时须为正整数）、`x/y/z=0`（可传 null 表示尚无有效值）、`feedback_state={}`（逐字段状态及 `age_ms`）、`devices:[{device_id?, sensor_id?, unit_id?, parameter_name?, label?, initial=0或null, adjust=0, current=0或null}]` → 整份 JSON 存 `config_json`，随保存响应 `data.config` 返回。2026-11-05 起实际保存图纸编号与调试标记；`is_debug=true` 时 `drawing_id` 必须为空，否则返回 422。旧客户端不传这两个字段仍可保存；无需数据库迁移。
- GET `/finetuning/`：query `skip=0, limit=100, module_id?, unit_id?`

---

### 2.5 硬件控制与状态接口

| 序号 | 接口路径 | 方法 | 鉴权 | 对应 ROS 话题/方式 | 用途 |
|------|---------|------|------|-------------------|------|
| 10 | `/control/serial_test` | GET | 是 | 子进程调用 `serial_test_node.py` | 串口连接测试 |
| 11 | `/control/hardware/realtime` | GET | 是 | 子进程调用 `hardware_node.py` | 获取实时硬件状态 |
| 12 | `/control/emergency_stop` | POST | 是 | 适配层急停发布 | 发送全局急停 |
| 13 | `/control/emergency_stop/release` | POST | 是 | 适配层解除发布 | 发送急停解除 |

**接口 10：串口连接测试**
- 响应：`{"code":200, "message":"串口测试完成", "data":{"success":true, "connected":true, "message":"串口连接正常", "bytes_received":128}}`
- 实现：`app/ros/base.py` → `test_serial_connection()`，异步子进程，超时 10 秒

**接口 11：实时硬件状态**
- 响应模型 `HardwareFeedback`：`{"joints":[float...], "status":str, "timestamp":float}`
- 实现：`app/ros/base.py` → `get_hardware_status()`，超时 5 秒

**接口 12：紧急停止**
- 响应（非标准包装）：`{"success":bool, "message":str, "timestamp":datetime}`；失败 500
- ROS 下行及回执细节引用[共享三轴契约](../../docs/ROS_MES_前后端ROS接口清单_三轴版_V2.1.md)，本节只定义业务请求和 HTTP 结果。
- 实现：`app/ros/rosbridge.py` 的独立急停发送路径。`success=true` 表示发送路径完成，不代表设备已停或已解除。急停/解除的下行契约引用共享三轴清单；本次不改动该兼容路径。
- 解除：POST `/control/emergency_stop/release`，响应同 `EmergencyStopResponse`。

---

### 2.6 无图纸微调调试开关（2026-11-05）

入口为现有“个人中心 → 调试设置 → 跳过图纸绑定”，默认关闭。前端 Pinia 状态只在当前打开应用期间跨页共享；刷新、登录或退出登录后关闭。进入微调页时固定本次模式，设置影响下一次进入。

开启后，模块选择及 `/module/` 机械臂确认保持不变；首次弹窗只选机械臂，不加载图纸列表，不调用 `/coordination/send` 或三视图接口，确认成功后允许三轴微调、反馈、多臂切换和配置保存。页面显示“调试模式 · 未绑定图纸”，本次会话禁用图纸及点云入口。关闭后正常流程继续要求图纸下发成功。

调试配置通过现有 POST `/finetuning/config` 保存，`is_debug=true/drawing_id=null`；正常配置为 `is_debug=false/drawing_id=<实际图纸编号>`。当前前端使用所选臂真实登记的压力传感器业务号，恢复缓存时同步恢复该编号，真实通信模式下缺少压力传感器会提示补齐，不用模块设备号代替。保存、确认及微调请求期间禁止切换机械臂或重复操作。

此功能不修改 `VITE_DEBUG_NO_ROS`。新开关仍走当前真实通信和保存 API；已有无 ROS 环境模拟功能独立保留，并提示模拟保存未写数据库。调试功能的变更及既有验证记录统一见[改动记录](ROS_MES_前后端改动记录.md)。

保存配置的 `feedback_state` 记录每个实测字段的 `status` 和 `age_ms`。无有效样本的 `initial/current` 以及 IMU x/y/z 使用 null；历史或过期值可以保留，但必须连同其状态保存，不能当作刚收到的实测数据。新元数据进入已有 `config_json`，不改表结构；旧客户端省略字段仍兼容。

## 3. WebSocket 接口

### 3.1 微调反馈 `/api/control/feedback/ws`

免认证，服务器向前端单向推送 JSON。后端 `control.py` 调用 `app/ros/rosbridge.py`，订阅 `profile.py` 定义的 8 类对外反馈；具体 ROS 类型、编号和话题契约引用共享清单，逐项接入与验证状态见[对接状态清单](后端与ROS接口对接状态清单.md)。

| 字段 | 类型/语义 |
|---|---|
| `time_id` | 后端接收/归一化的墙钟时间，不能当作设备时钟已同步的证明 |
| `topic`、`header`、`raw` | 来源话题、原消息头时间戳及原消息字段；非有限数值在 `raw` 中以文本保留，保证 JSON 可传输 |
| `module_id` | 原消息编号；含义由 `module_id_space` 指明，不直接等于业务模块号 |
| `device_id` | 轴级或臂级编号；无效/缺失编号不能用于更新实际值 |
| `position` | 有效有限数值，或 null；不把缺失、空数组、非法数据补成零 |
| `position_valid`、`valid_fields` | 有效位置标志及有效字段名列表，IMU 分量独立校验 |
| `data_type`、`feedback_type` | 本侧分类与中文标签 |
| `module_id_space` | 已知普通遥测为 `seg`，压力均值为 `business`，混合回执为 `mixed`，未知来源为 `unknown` |

前端实际值只由归属明确且有效的样本更新；HTTP 请求回显及占位压力不能覆盖实测值。普通轴、瞬时压力和 IMU 按本次模块确认返回的 `seg`、当前机械臂轴号/臂级编号核验，不按轴号单独匹配，也不把所有话题一律当作 SEG。

| `data_type` | 本侧消费范围 |
|---|---|
| `rotation_axis_encoder`、`swing_axis_encoder`、`telescope_axis_encoder` | 三轴实际值；旋转/摆动为度，伸缩反馈为 mm |
| `pressure_sensor` | 瞬时压力，独立于轴的接收状态 |
| `imu_pose` | `swing_angle/rotation_angle/x/y/z`，每个分量独立更新 |
| `cmd_ack` | 回执事件提示，见下文 |
| `pressure_average`、`vacuum_loss_event` | 后端已转发；本次不顺便扩展前端业务，见状态清单 |
| `error` | 连接异常信息；不能继续将旧数值显示为实时 |

**逐项状态**：每个轴、压力和每个 IMU 分量分别记录浏览器单调时钟 `performance.now()` 的有效样本接收时间。尚无样本显示等待；新有效样本显示实时；恢复缓存显示历史直到新样本；超时或连接断开显示过期。旧数值可以保留用于比较，但不能冒充实时，真正的零值仍是有效数值。

暂定 UI 新鲜度阈值：轴和 IMU 各 5 秒、压力 10 秒。可用 `VITE_ROS_AXIS_STALE_MS`、`VITE_ROS_PRESSURE_STALE_MS`、`VITE_ROS_IMU_STALE_MS` 配置。这只是显示策略，不是设备周期承诺、故障诊断或自动停止条件；现场发布频率仍需核实。

**CmdAck 元数据**：保持 `ack_msg/result/detail/raw`，增加 `module_candidates`（业务模块候选数组）、`module_resolution=resolved|ambiguous|unknown`、`business_module_id`（仅可靠唯一归属时有值）。原 `module_id` 不改写。

普通 ROS 软件拒绝回执使用业务模块号，CAN 回执使用 SEG，当前消息没有发布者来源标识或请求关联 ID。归属算法同时保留两种合法解释：正业务号是候选，0～14 还可能是 SEG；SEG 映射缺失/非法时为 unknown，多候选为 ambiguous。前端仅对可靠归属且匹配控制目标的事件提示接受/拒绝；不明归属保留原始信息并明确标记，不能改变当前臂实际值或某次请求的结果。

收到接受回执也不表示运动完成。`ack_msg` 不同可能对应回零等其他命令，不能把任意 `result=3` 都称为“本次微调超限”。未收到回执不推断成功/失败，不无限等待或自动重发增量指令。

回执事件列表最多保留 20 条，只在当前页面会话内存在，不是持久化日志或完整指令追踪。

### 3.2 大屏 `/api/ws/ws/robot_status`

当前路由前缀与端点路径叠加，地址有双层 `/ws`。通过 Query `token` 校验 JWT，缺失/无效关闭 1008；接受后转发 `app/ros/base.py` 的 `stream_robot_data()` 文本流。底层数据源为 `web_data_node.py`，可用性与历史限制登记在状态清单；连接建立不证明有实时数据，本次不恢复 ROS 数据源。

## 4. 编号边界及外部契约

- 业务 `module_id`、登记模块设备号、机械臂 `Unit_ID`/代理行号、数据库 `sensor_ID` 与 ROS `device_id`/CAN SEG 是不同语义，按对应接口字段传递，禁止混用。
- 业务模块到 SEG 依赖显式 `ROS_MODULE_SEG_MAP`；前端使用模块确认响应中的 SEG 核验已知硬件遥测。映射缺失或歧义不能靠模块号、轴号猜测。
- 数据库可登记范围由 `/api/device/config` 给出，实际存在的记录仍通过 CRUD 接口读取。源码种子或配置包含五臂不代表现场数据库已登记五臂。
- 话题、消息、三轴编号、握手及 CAN 协议不在本文复制：参考[共享三轴契约](../../docs/ROS_MES_前后端ROS接口清单_三轴版_V2.1.md)、[模块确认命令](../../docs/机械臂模块确认命令.md)、[保护事件说明](../../docs/模块确认与保护事件技术说明.md)。
- 共享契约若与当前源码或部署配置不一致，记录差异与来源，待对应维护方确认；本侧对接清单不另立权威。

## 5. 代码入口

| 位置（相对 `mes_web/`） | 用途 |
|---|---|
| `ros_mes_hou/app/api/api.py` | 路由装配 |
| `ros_mes_hou/app/api/endpoints/{control,module,coordination,finetuning}.py` | 控制、模块确认、图纸/视图、记录/配置保存 |
| `ros_mes_hou/app/ros/{profile,rosbridge,normalizer,base}.py` | 版本与话题配置、传输、归一化、子进程工具 |
| `ros_mes_hou/app/core/{config,device_catalog,security}.py` | 路径/配置、可登记设备规则、鉴权 |
| `ros_mes_hou/app/db/models.py`、`app/schemas/` | 数据模型与请求/响应校验 |
| `ros_mes_front/src/api/{rosApi,types,deviceEncoding,noRosDebug}.ts` | API、类型、ROS 编号助手、开发模拟 |
| `ros_mes_front/src/components/Main/ModulePage/` | 模块选择与微调页面 |
| `ros_mes_front/src/components/Main/UserManage/Profile.vue` | 个人中心及调试设置 |
| `ros_mes_front/src/stores/{user,debugSettings}.ts` | 登录态和仅本次应用会话的调试开关 |

## 6. 运行与兼容注意事项

前端开发代理支持 HTTP 和 WebSocket；前端不直接连接 rosbridge。点云视图通过后端代理返回图片，正常图纸流程依赖点云服务；无图纸调试不依赖图纸列表或点云服务。

部分接口有历史别名、Query 参数或独立响应模型，不能假定全部字段同一风格；新增规范见[命名规范](ROS_MES_前后端命名规范.md)。设备操作的免认证状态是当前实现事实，不是新增接口的安全设计建议。鉴权变更须前后端配套，不借本次反馈修正扩大范围。

测试历史记录和当前缺口统一见[改动记录](ROS_MES_前后端改动记录.md)与[对接状态清单](后端与ROS接口对接状态清单.md)。历史 UI 方案、v1.1 适配清单和旧待办已归档，不能当作现行状态执行。

## 7. ROS1/ROS2 适配

业务接口不感知 ROS 版本。`ROS_VERSION=1|ros1|2|ros2` 由 `app/ros/profile.py` 选择类型串和时间戳格式；传输共享 rosbridge JSON 协议。测试页通道两版均经 rosbridge，ROS1 原生 rospy 通道仅为历史兼容。

话题可由 `ROS_TOPIC_<键名大写>` 环境变量覆盖。后端存在 ROS2 类型串预设，不等于完整 ROS 执行包已经移植或现场 ROS2 链路已通过。构建与设备执行能力应按共享资料和实际部署证据核对。

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
- **机械臂**：`id, Unit_ID, UnitDescript, Module_ID, ...`；GET `/`、GET `/by_device/{id}`、GET/PUT/DELETE `/{id}`、POST `/`（`Unit_ID`✔，须在设备配置内；`Module_ID`/`Device_ID` 二选一且须为已登记模块；同模块重复 409）
- **传感器**：`id, sensor_ID, sensordescript, IsRead, Module_ID, Unit_ID, Unit_address, ...`；GET `/`、GET `/by_unit/{id}`、GET/PUT/DELETE `/{id}`、POST `/`（`Unit_ID`✔、配置内 `sensordescript`✔，归属通过 `Module_ID`/`Device_ID` 或 `unit_row_id` 指定；`sensor_ID`、`Unit_address` 可省略，由后端生成；显式传值须与配置一致；同模块业务号重复 409）
- `/model/tree` 节点结构（`TreeNode`）：`{id:"model-<Type_ID>"|"device-<Module_ID>"|"unit-<id>"|"sensor-<id>", label, type, raw_id, arm_type?, sensor_type?, module_id?, device_id?, children?}`

**设备配置接口（2026-11-04）**：`GET /api/device/config`，免认证，无需 ROS 或数据库读写，返回 `{code, message, data}`。`data` 结构：

```json
{
  "arms": [{"label": "四号机械臂", "value": 128}],
  "sensor_types": [{
    "label": "压力传感器",
    "Unit_address": 0,
    "sensor_ids": {"32": 49, "64": 81, "96": 113, "128": 145, "160": 177}
  }]
}
```

以上仅展示一个机械臂选项和一种传感器；完整响应包含五臂、八类传感器。配置集中在 `app/core/device_catalog.py`，前端只读取选项和编号映射，不再保存偏移或计算 `sensor_ID`。支持范围与数据库实际已登记记录分开，已登记列表继续使用原 CRUD 接口。数据库初始化脚本仍可独立运行，后端测试对照其五臂、40 条传感器种子，防止配置与种子规则漂移。

写接口规则：未知机械臂/传感器类型、编号或地址不匹配、机械臂归属不匹配返回 422；重复新增或编辑到被占用的业务号返回 409（包括编辑到软删除行的保留业务号）；记录不存在返回 404。传感器编辑未传编号/地址时，按目标机械臂及传感器类型重新生成；仅更新备注或启用状态时保留历史编号。删除后重新新增复用原记录，避免软删除行的唯一约束冲突。配置接口不迁移、不补写数据；前后端需配套更新，配置加载失败时页面提示重试。

---

## 10. 数据库表字段（基准补充）

SQLite（`ros_database.db`，项目根），17 张表，模型在 `app/db/models.py`，建库种子脚本为仓库根的 `sqlite_create.py`。时间字段 `DateTime(timezone=True)` 默认 `now()`；普遍带软删除 `del_flag` 与 `Notes`。

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
| `Unit` | id(PK 代理), Unit_ID(业务臂号 32/64/96/128/160), UnitDescript, Module_ID→Module；Unique(Module_ID,Unit_ID) | 机械臂 |
| `sensors` | id(PK 代理), sensor_ID(业务号), sensordescript, IsRead, Module_ID+Unit_ID(联合FK→Unit), Unit_address；Unique(Module_ID,sensor_ID) | 传感器（每臂 8 类） |
| `sensor_log` | Createtime+sensor_id(复合PK), creater_id, Work_ID, isread, data, ... | 传感器日志 |
| `Tasks` | Task_ID(PK), Taskname, Taskdescripte, Workflow_ID?, Drawing_ID?, creater_id, TaskAssignment_id?(指派人), Status("0"~"3"), ... | 任务 |
| `TasksTracing` | TasksTracing_ID(PK), Task_ID, operate_type, Workflow_ID, operater_ID, operate_time, Notes | 任务跟踪 |
| `calculation` | Createtime(PK), creater_id, Work_ID, Module_ID?, Unit_ID?, device_ID?, isread, coord, position, ... | 计算解析日志 |
| `point_data` | Createtime(PK), creater_id, Module_ID?, point, arms_address, ... | 点云解析数据 |

> 注意：`schemas/device.py`、`schemas/model.py` 的 `Device_*`/`Model_*` 是 **Module 表 / Type 表的对外别名**，库中无独立 Devices/Model 表。种子账号与初始密码见建库脚本（部署时自行设置，文档不复制凭据）；Module_ID=17、源码种子定义五臂 Unit_ID=32/64/96/128/160、每臂 8 传感器；现有部署数据库登记数量必须另行核查。

---

## 11. 认证矩阵（基准补充）

| 级别 | 接口 |
|---|---|
| 免认证 | `POST /login`、`POST /register`、`GET /dashboard/stats`、`/finetuning/**`、`POST /module/`、`POST /control/finetuning`、WS `/control/feedback/ws`、`/coordination/**`、`/ros/**`、`/model/**`、`/device/**`、`/unit/**`、`/sensors/**`、`GET /api/uploads/**` |
| 登录即可 | `/user/me`、`GET /user/`、`POST /user/password`、`POST /user/avatar`、`PUT /user/profile/me`、`/drawing/**`、`/work/**`、`/workflow/**`、`/task/**`、`GET /control/serial_test`、`GET /control/hardware/realtime`、`POST /control/emergency_stop`、`POST /control/emergency_stop/release` |
| 管理员（`Type_ID==1`） | `POST /user/`、`PUT /user/{id}`、`DELETE /user/{id}`、`lock`、`unlock`、`role`、`POST /user/import`、`GET /user/export` |

认证机制：OAuth2 Bearer Token（`tokenUrl=/api/login`）+ JWT（HS256，payload `{sub, exp}`），bcrypt 密码哈希；WS 用 query `token` 校验。

---
