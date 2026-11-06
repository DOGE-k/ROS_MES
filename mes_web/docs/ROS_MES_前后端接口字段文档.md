# ROS_MES 前后端接口字段文档

维护范围：Vue 前端和 FastAPI 业务后端。2026-11-07 更新；当前代码及双方已确认契约是核查依据，历史测试结果不能代替当前实现验证。前后端任务先读[开发入口](../AGENTS.md)，最近变更见[改动记录](ROS_MES_前后端改动记录.md)。

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
| 真实/模拟连接 | 个人中心 → 调试设置 | 后端统一配置 ROS、图纸、急停模式和地址；历史 `VITE_DEBUG_NO_ROS` 不再绕过后端 |

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
| `connection_revision` | int | 可选 | 页面读取的连接配置版本；与后端当前版本不一致时返回 409，须重新读取并确认 |

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
- 请求体（业务目标字段必填，缺失/类型错 422）：

| 字段 | 类型 | 说明 |
|---|---|---|
| `device_id` | int | 模块设备业务编号，必填 |
| `module_id` | int | 模块业务编号，必填 |
| `unit_id` | int | 机械臂 `Unit_ID`，必填 |
| `unit_row_id` | int | 机械臂数据库行编号，必填 |
| `drawing_id` | int 或 null | `database` 来源必填实际图纸编号；内置模拟来源必须为 null |
| `drawing_source` | str | `database`（默认）或 `builtin_mock`；其他值或非字符串返回 422 |
| `connection_revision` | int | 可选；与当前服务版本不一致时返回 409 |

- 响应：`{"code":200,"message":"...","simulated":false或true,"data":{业务目标及drawing_id/drawing_source},"dispatch":{...},"views":{"front":"/api/coordination/views/front?connection_revision=版本","side":"...","top":"..."}}`。
- 真实下发：校验参数及配置版本 → 查库取图纸路径 → 转相对路径 → rosbridge 发布 → 等待点云三视图生成（最长 5 秒，超时 504）。实际图纸不存在返回 404，路径为空返回 422。
- 模拟下发：可选正式图纸或后端内置示例。内置示例仅允许当前 `drawing_mode=mock` 且 `drawing_source=builtin_mock/drawing_id=null`；不创建正式图纸记录、不构造真实 ROS 路径，返回明确的模拟预览。
- `drawing_mode=skip` 时本接口及三视图接口返回 409。模拟示例不得在真实模式使用；真实空库仍要求先导入正式图纸。

正常模式页面顺序为“选模块 → 多选 1~5 台机械臂和一张图纸 → 批量机械臂确认 → 按臂图纸下发 → 微调”。全部确认和图纸下发成功后进入微调页；主页面提供机械臂切换和重新下发图纸入口，已确认机械臂的图纸、三视图和微调状态按臂分别保留于本次页面会话中。切换机械臂不会再次弹出选择框；重新下发只作用于当前机械臂。请求进行中禁用目标切换，避免数据串臂。

**接口 5：点云视图代理**
- 路径参数：`view_name` ∈ {`top`, `front`, `side`}（其他值 404）
- 响应：真实模式代理点云图片，服务不可达 502；模拟模式返回标记 `SIMULATED` 的 SVG，不请求点云服务。可选查询参数 `connection_revision`，配置版本变化返回 409；不使用图纸模式返回 409。

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
- POST `/finetuning/config`：`module_id`(✔)、`unit_id`(✔)、`sensor_id`(可由 `device_id`/`devices[0]` 兜底)、`device_id?`、`is_debug=false`、`drawing_id=null`（传值时须为正整数）、`drawing_source="database"`、`connection_revision?`（非负版本号）、`x/y/z=0`（可传 null 表示尚无有效值）、`feedback_state={}`（逐字段状态及 `age_ms`）、`devices:[{device_id?, sensor_id?, unit_id?, parameter_name?, label?, initial=0或null, adjust=0, current=0或null}]` → 整份 JSON 存 `config_json`，随保存响应 `data.config` 返回。`is_debug=true` 时 `drawing_id` 必须为空；内置示例保存为 `is_debug=false/drawing_source="builtin_mock"/drawing_id=null`，且只允许当前图纸模式为 mock，不能与跳过图纸同时使用。版本不一致返回 409，来源或组合非法返回 422。旧客户端省略新字段仍兼容；新元数据不增加业务表列。
- GET `/finetuning/`：query `skip=0, limit=100, module_id?, unit_id?`

---

### 2.4.1 三轴统一确认与顺序执行（2026-11-06）

三个输入框只保存待提交增量，当前机械臂共用一个“确认下发”按钮。确认时冻结模块、机械臂和三个轴的本次增量，只提交非零项；同一机械臂一次只允许一个执行批次。前端不得将三次 HTTP 成功当作三轴运动完成。

- `POST /control/finetuning/batches`：携带客户端唯一 `request_id`、`module_id`、`unit_id` 和 `adjustments:[{parameter_name, position}]`。批次号只用于 MES 幂等和进度，不添加到 ROS 消息，不声称设备回显它。相同请求号不得重复执行；冲突请求返回 409。
- `GET /control/finetuning/batches/{id}`：查询每轴及批次进度。刷新页面恢复查询，不自动再次提交。
- 后端独立订阅反馈，先取得当前模块/机械臂三轴的新鲜位置及有效、空闲、无急停/故障的状态，才允许发送第一轴。等待同轴新运行状态、符合目标位置的到位事件和空闲状态后，才推进下一轴；接受 ACK 本身不推进队列。
- 轴忙/拒绝、限位/故障、失压、断线、急停和超时停止后续下发；无法证明结果时标为 `uncertain` 并保留目标锁，禁止自动重发。状态及幂等记录保存于后端专用批次表，重启后未结束批次变为待核实，不恢复执行。
- 待核实批次经操作者现场核对后，可调用独立确认接口释放 MES 控制锁；该操作不发送运动、不解除设备故障，后续新批次仍须通过实时空闲检查。历史已发送项目不得作为一整批自动重试。
- MES 批次在单个后端工作进程中执行；同一设备需由本控制会话独占，不能与 ROS 内部自动流程或其他控制器同时运动。现有反馈无设备请求序号，迟到/混合来源存在协议边界；真机启用前需核实状态、到位事件、单位及独占操作条件。反馈不足时不得继续发送，不用固定延时或读数不变推断完成。
- 默认仅以隔离数据库和模拟 ROS 消息验证，不修改 ROS/固件。伸缩单位按现有共享契约 mm/CAN 0.01mm；到位原始字段与现场固件一致性仍需 ROS 方确认。

下列路径均带 `/api` 前缀、要求登录；查询与恢复操作不发送运动指令。

| 方法与路径 | 请求/用途 | 响应与限制 |
|---|---|---|
| POST `/control/finetuning/batches` | `request_id`、`module_id`、`unit_id`、`adjustments` | HTTP 202，返回批次快照；只表示已登记。同一请求号与相同内容返回原批次；内容冲突或目标锁定为 409，参数/登记/映射错误为 422 |
| GET `/control/finetuning/batches/active?module_id=17&unit_id=32` | 页面进入/重新配置前检查目标 | 返回锁定批次或 `data:null`，不自动确认模块或重发图纸 |
| GET `/control/finetuning/batches/by-request/{request_id}` | 提交响应丢失后按原请求号查询 | 返回原批次或 `data:null`；暂未查到不代表可重发 |
| GET `/control/finetuning/batches/{id}` | 查询逐轴进度 | 不存在为 404；前端保留未知状态，不自动提交新批次 |
| POST `/control/finetuning/batches/{id}/interrupt` | 停止后续下发 | **不停止已经运动的轴**；立即停止应使用全局急停 |
| POST `/control/finetuning/batches/{id}/acknowledge` | `{"operator_confirmed":true}`，现场核实后关闭待确认记录 | 仅 `uncertain` 且后台任务已结束时允许；否则 409。仅释放 MES 锁，不复位故障/解除急停/重发运动 |

请求示例：`{"request_id":"batch_20261106_001","module_id":17,"unit_id":32,"adjustments":[{"parameter_name":"rotation","position":2},{"parameter_name":"telescopic","position":0.5}]}`。请求号为 8～80 位字母、数字、下划线或连字符；1～3 项，每轴至多一项且为非零有限数值。沿用页面单次输入范围 -360～360，**不是设备软/硬限位承诺**。后端由机械臂和参数类型计算轴号，不接受客户端覆盖；旧单轴接口也校验轴号、参数和机械臂一致，并检查批次锁。

批次响应统一为 `{"code":202或200,"message":"...","data":{...}}`；快照字段如下：

| 字段 | 语义 |
|---|---|
| `id/request_id` | 后端批次 UUID / 客户端幂等号，均不是固件请求序号 |
| `module_id/unit_id/seg` | 冻结的业务模块、机械臂及本次物理 SEG |
| `status/message` | `queued` 等待、`checking` 状态检查、`executing` 执行、`completed` 已观测完成、`blocked` 尚未发送即受阻、`uncertain` 结果待核实、`closed` 人工核实关闭 |
| `target_locked` | 是否保留控制锁；按物理 SEG+arm 唯一占用，并核验业务目标，业务编号别名不能绕过锁 |
| `steps[]` | `parameter_name/position/device_id/status`；开始执行后可含 `expected_position`，为基于实测基线计算的预期目标，不能当作实测位置 |
| `steps[].status` | `pending` 未发送、`sent_unconfirmed` 发送阶段、`completed` 已观测完成、`uncertain` 已尝试发送但结果不明 |

实现默认等待初始状态 10 秒、单轴完成 60 秒、状态与位置新鲜度 3 秒。每轴必须观测到发送后的运行状态、符合目标及误差条件的到位事件和运行后的空闲状态；默认比较容差为旋转/摆动 0.2°、伸缩 0.1mm，仅为 MES 软件判定阈值，需现场验证，不能代替设备精度验收。未观测到完整条件时不发下一轴，即使动作过短而漏掉 RUN 也按待核实处理。

页面每秒查询批次进度。刷新后先恢复后端锁定批次；批次完成/人工关闭后可重新配置会话。提交不明时保留请求号只查询，已完成项清空草稿，人工核实关闭时也清空已尝试发送项；未发送项可供操作者重新审阅。批次详情和 ACK 提示按机械臂保存，切换后不沿用上一臂记录，切回可恢复本次会话内原臂记录；重新配置建立新会话时清除旧臂缓存。旧查询的迟到结果不得覆盖新批次或其他机械臂。后端模拟也保存批次并逐轴观测模拟 RUN/到位/空闲，明确标记模拟来源，不连接设备。

批次响应新增 `simulated/execution_mode/safety_mode/connection`，连接快照含 `mode/safety_mode/url/revision`。内部复用现有 `request_json` 的 `_execution` 元数据保存，不增加批次表列。模拟目标锁使用 `mock:SEG:arm`，真实目标锁保留 `SEG:arm`，防止模拟解除影响真实记录。请求可带 `connection_revision`，与模块确认返回版本不一致时返回 409，要求重新确认目标。

### 2.5 硬件控制与状态接口

| 序号 | 接口路径 | 方法 | 鉴权 | 对应 ROS 话题/方式 | 用途 |
|------|---------|------|------|-------------------|------|
| 10 | `/control/serial_test` | GET | 是 | 子进程调用 `serial_test_node.py` | 串口连接测试 |
| 11 | `/control/hardware/realtime` | GET | 是 | 子进程调用 `hardware_node.py` | 获取实时硬件状态 |
| 12 | `/control/emergency_stop` | POST | 是 | 适配层急停发布 | 发送全局急停 |
| 13 | `/control/emergency_stop/release` | POST | 是 | 适配层解除发布 | 发送急停解除 |
| 13a | `/control/emergency_stop/status` | GET | 是 | MES 持久化联锁记录 | 刷新恢复操作提示，不代表设备实测 |

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

**前端急停/解除交互（2026-11-07）**：移除五秒自动恢复；急停期间中止批次后续下发，页面不把发送成功写成设备已停。全屏仅在操作者主动长按急停或点击“查看急停状态”时打开；历史记录、轮询、刷新或切换环境只更新持续提示，不自动打开全屏，也不自动发送急停或解除。全屏可随时“返回页面（保留急停状态）”，真实联锁继续保留，不因关闭遮罩而解除。

解除按钮调用现有解除接口；失败保留待确认状态，已主动返回页面时不重新弹出全屏。真实发送成功显示“解除指令已发送，设备状态待确认”，不自动写成设备已解除；明确的模拟解除成功关闭遮罩并清除模拟联锁。新批次仍须通过后端实时空闲/无急停检查。急停与解除记录在后端控制联锁中，刷新页面不清空；解除急停不等于故障复位。

状态查询返回 `data:{state,generation,simulated,connection_revision}`。`state` 为 `clear`（无联锁记录，或模拟解除成功）、`stop_requested`（请求急停）、`stop_sent`（急停已发送）、`stop_unknown`（发送结果不明）、`release_sent`（真实解除已发送，设备状态仍待确认）。`generation` 是 MES 联锁版本，变化会中止相应控制环境批次的后续下发；解除不会恢复旧批次。侧栏每秒查询；发送期间防重复点击，旧查询结果不得覆盖刚发起的操作。急停/解除响应也包含 `simulated`；只有明确的模拟解除成功才将遮罩直接关闭，真实模式仍保留待确认提示。

### 2.6 页面调试连接配置（2026-11-07）

图纸处理合并为 `drawing_mode=skip/mock/real` 三选，不再叠加独立跳过开关；mock 可使用后端内置示例，空正式图纸表也能测试。历史急停记录通过持续提示呈现，轮询/刷新/切换环境不主动打开全屏、不发送控制；真实联锁继续保留。完整自测结果见最新改动记录。

在现有“个人中心 → 调试设置”中逐项手动选择：ROS 通信/微调为模拟或真实，图纸处理为不使用图纸、模拟下发或真实下发，急停及解除为模拟或真实。真实模式填写 ROS WebSocket 地址、图纸 ROS 地址、三视图 HTTP 地址及急停 ROS 地址，默认共用 ROS 地址，可分别配置。选择后自动应用，地址在回车或移出输入框后应用；不添加全部模拟/全部真实、测试连接、保存并应用按钮。

模拟在后端适配层执行，前端继续使用真实业务 API、数据库、批次和反馈流，不再由 `VITE_DEBUG_NO_ROS` 截走业务请求。模拟急停/解除返回明确的模拟成功，解除后关闭遮罩；真实发送成功仍不是设备状态确认，不自动降级模拟。真实微调或图纸下发要求真实急停，急停与解除始终共用模式和目标。

连接配置由后端统一维护，页面刷新后重新读取；编辑后自动保存。执行中或待核实批次存在时拒绝切换；一个动作/批次固定使用启动时的配置，不在执行中换地址。模拟批次/遥测带来源标记，模拟和真实的控制联锁、目标锁分开保存；模拟解除不能清除真实急停记录。急停遮罩提供进入同一调试配置面板的入口，以便在无 ROS 环境切到模拟，无需发送真实解除来打开设置。

新增登录接口 GET/PATCH `/control/debug-settings`；PATCH 带配置版本防止覆盖其他窗口修改，成功返回当前完整配置与版本。ROS/固件消息保持原样；本侧只增加配置、路由和模拟实现。模拟数据不能作为真机验收证据。

GET 返回 `{"code":200,"message":"...","data":{...}}`；PATCH 请求为 `{"expected_revision":0,"changes":{"ros_mode":"mock"}}`，仅发送本次改动，返回已接受的完整配置。版本冲突、进行中或待核实批次、正在处理的下发/急停操作返回 409；非法地址、未知配置字段或真实下发搭配模拟急停返回 422，失败后继续使用原配置。页面失败时重新读取当前服务配置，不自动重试覆盖。

| 配置字段 | 含义及默认值 |
|---|---|
| `revision` | 后端配置版本，更新成功递增；前端用 `expected_revision` 防止覆盖其他窗口 |
| `ros_mode` | `real/mock`，控制模块确认、微调及反馈来源；首次无保存配置时为 real |
| `drawing_mode` | `skip` 不使用图纸、`mock` 模拟下发、`real` 真实下发；首次为 real |
| `emergency_mode` | 急停与解除共同使用的 `real/mock`，首次为 real；任一真实运动/图纸下发要求此项 real |
| `ros_url` | ROS WebSocket 地址，首次继承 `ROSBRIDGE_URL` |
| `drawing_ros_url` | 图纸 ROS WebSocket 地址，留空继承 `ros_url` |
| `emergency_ros_url` | 急停/解除 ROS WebSocket 地址，留空继承 `ros_url` |
| `pointcloud_url` | 三视图 HTTP 服务地址，首次继承 `POINTCLOUD_VIEW_BASE_URL`，默认 `http://localhost:5000` |

地址允许 ws/wss（ROS）或 http/https（三视图），拒绝嵌入账号密码、查询串、片段及非法端口。配置是当前后端服务共用的，不仅属于某个浏览器窗口；仍限定单 worker。模拟位置在进程内维护，重启不恢复旧模拟动作，持久化批次继续按待核实处理。

模块确认按当前配置确认所有实际使用的真实入口；图纸和微调使用不同真实 ROS 地址时，两处都要确认成功。修改连接后，微调页旧确认和反馈缓存失效，需要重新确认机械臂。图纸请求也可带 `connection_revision`，返回的三视图 URL 带版本，配置变化后旧版本视图返回 409，防止读到其他环境的图片。图纸模拟返回明确的模拟预览 SVG，不请求真实点云服务。

ROS 模拟时，串口/硬件检查和大屏底层工具不拉起 ROS/串口脚本，返回带 `simulated` 的模拟结果；ROS 测试通道也不发布真实消息。模拟遥测和批次均带来源标记，当前模拟覆盖轴状态/位置、到位及压力，未生成的 IMU 分量仍显示等待，不冒充真实测量。

### 2.7 不使用图纸与内置模拟图纸（2026-11-07）

入口为现有“个人中心 → 调试设置 → 图纸处理方式”。原独立“跳过图纸绑定”开关已合并为“不使用图纸”（`drawing_mode=skip`），和模拟下发、真实下发互斥。设置存于后端，对当前服务共享，刷新后重新读取，不再由前端临时开关控制；连接更改后旧微调会话失效，须重新配置和确认机械臂。

选择“不使用图纸”后，模块选择及 `/module/` 机械臂确认保持不变；首次弹窗只选机械臂，不加载图纸列表，不调用 `/coordination/send` 或三视图接口，确认成功后允许三轴微调、反馈、多臂切换和配置保存。页面显示“调试模式 · 未绑定图纸”，本次会话禁用图纸及点云入口。

微调选择图纸时使用 GET `/drawing/?for_tuning=true`。正式图纸附加 `drawingSource="database"`；仅在 mock 模式，列表首项为 `drawingId=null/drawingSource="builtin_mock"/simulated=true` 的“内置模拟图纸（无需导入）”。此项是后端提供的选择描述，不写入正式图纸表；普通图纸管理 GET `/drawing/` 仍只列正式记录，空库仍显示零条。真实模式不提供内置示例，空库提示先导入图纸。

三种配置通过现有 POST `/finetuning/config` 保存：不使用图纸为 `is_debug=true/drawing_source="database"/drawing_id=null`；内置模拟图纸为 `is_debug=false/drawing_source="builtin_mock"/drawing_id=null`；正式图纸为 `is_debug=false/drawing_source="database"/drawing_id=<实际图纸编号>`。页面带 `connection_revision` 核验会话版本。当前前端使用所选臂真实登记的压力传感器业务号，恢复缓存时同步恢复该编号；缺少登记的压力传感器会提示补齐，不用模块设备号代替。保存、确认及微调请求期间禁止切换机械臂或重复操作。

不使用图纸不改变通信模式。通信来源由上方 ROS 连接配置决定，业务 API 和配置保存统一经过后端；历史 `VITE_DEBUG_NO_ROS` 编译开关不再截走请求。调试功能的变更及既有验证记录统一见[改动记录](ROS_MES_前后端改动记录.md)。

保存配置的 `feedback_state` 记录每个实测字段的 `status` 和 `age_ms`。无有效样本的 `initial/current` 以及 IMU x/y/z 使用 null；历史或过期值可以保留，但必须连同其状态保存，不能当作刚收到的实测数据。新元数据进入已有 `config_json`，不改表结构；旧客户端省略字段仍兼容。

## 3. WebSocket 接口

### 3.1 微调反馈 `/api/control/feedback/ws`

免认证，服务器向前端单向推送 JSON。后端 `control.py` 调用 `app/ros/rosbridge.py`，订阅 `profile.py` 定义的 13 类对外反馈；具体 ROS 类型、编号和话题契约引用共享清单，逐项接入与验证状态见[对接状态清单](后端与ROS接口对接状态清单.md)。批次管理器另开独立订阅连接，页面断开不触发重新下发。

| 字段 | 类型/语义 |
|---|---|
| `time_id` | 后端接收/归一化的墙钟时间，不能当作设备时钟已同步的证明 |
| `topic`、`header`、`raw` | 来源话题、原消息头时间戳及原消息字段；非有限数值在 `raw` 中以文本保留，保证 JSON 可传输 |
| `module_id` | 原消息编号；含义由 `module_id_space` 指明，不直接等于业务模块号 |
| `device_id` | 轴级或臂级编号；无效/缺失编号不能用于更新实际值 |
| `position` | 有效有限数值，或 null；不把缺失、空数组、非法数据补成零 |
| `position_valid`、`valid_fields` | 有效位置标志及有效字段名列表，IMU 分量独立校验 |
| `data_type`、`feedback_type` | 本侧分类与中文标签 |
| `simulated`、`connection_revision` | 反馈来源是否为后端模拟，以及产生该反馈的服务连接配置版本；模拟数据不作实测证明 |
| `module_id_space` | 已知普通遥测为 `seg`，压力均值为 `business`，混合回执为 `mixed`，未知来源为 `unknown` |

前端实际值只由归属明确且有效的样本更新；HTTP 请求回显及占位压力不能覆盖实测值。普通轴、瞬时压力和 IMU 按本次模块确认返回的 `seg`、当前机械臂轴号/臂级编号核验，不按轴号单独匹配，也不把所有话题一律当作 SEG。

| `data_type` | 本侧消费范围 |
|---|---|
| `rotation_axis_encoder`、`swing_axis_encoder`、`telescope_axis_encoder` | 三轴实际值；旋转/摆动为度，伸缩反馈为 mm |
| `pressure_sensor` | 瞬时压力，独立于轴的接收状态 |
| `imu_pose` | `swing_angle/rotation_angle/x/y/z`，每个分量独立更新 |
| `cmd_ack` | 回执事件提示，见下文 |
| `axis_status`、`arrive_notification` | 后端批次消费者核验运行/目标到位/空闲；前端通过批次查询显示执行状态，不把事件字段当实测位置 |
| `stop_notification`、`axis_fault`、`limit_event`、`vacuum_loss_event` | 后端批次消费者遇到所属臂异常时停止后续下发；前端通过批次结果显示，独立告警页未扩展 |
| `pressure_average` | 已转发，前端未展示；ROS 均值采样归属仍待核实 |
| `error` | 连接异常信息；不能继续将旧数值显示为实时 |

**逐项状态**：每个轴、压力和每个 IMU 分量分别记录浏览器单调时钟 `performance.now()` 的有效样本接收时间。尚无样本显示等待；新有效样本显示实时；恢复缓存显示历史直到新样本；超时或连接断开显示过期。旧数值可以保留用于比较，但不能冒充实时，真正的零值仍是有效数值。

暂定 UI 新鲜度阈值：轴和 IMU 各 5 秒、压力 10 秒。可用 `VITE_ROS_AXIS_STALE_MS`、`VITE_ROS_PRESSURE_STALE_MS`、`VITE_ROS_IMU_STALE_MS` 配置。这只是显示策略，不是设备周期承诺、故障诊断或自动停止条件；现场发布频率仍需核实。

**CmdAck 元数据**：保持 `ack_msg/result/detail/raw`，增加 `module_candidates`（业务模块候选数组）、`module_resolution=resolved|ambiguous|unknown`、`business_module_id`（仅可靠唯一归属时有值）。原 `module_id` 不改写。

普通 ROS 软件拒绝回执使用业务模块号，CAN 回执使用 SEG，当前消息没有发布者来源标识或请求关联 ID。归属算法同时保留两种合法解释：正业务号是候选，0～14 还可能是 SEG；SEG 映射缺失/非法时为 unknown，多候选为 ambiguous。前端仅对可靠归属且匹配控制目标的事件提示接受/拒绝；不明归属保留原始信息并明确标记，不能改变当前臂实际值或某次请求的结果。

收到接受回执也不表示运动完成。`ack_msg` 不同可能对应回零等其他命令，不能把任意 `result=3` 都称为“本次微调超限”。未收到回执不推断成功/失败，不无限等待或自动重发增量指令。

回执事件列表最多保留 20 条，只在当前页面会话内存在，不是持久化日志或完整指令追踪。

新增五类轴事件保留 `raw/header`，按 SEG 归属；整数事件字段缺失/非法时为 null，`position=null/position_valid=false`，不得伪造位置。字段分别为轴状态 `status_bits/axis_state/base_valid`、到位 `angle/pos_error/status_bits/flags`、停止 `stop_reason/output_level`、故障 `fault_bits/local_action/detail/duration_ms`、限位 `limit_type/output_level`；失压补充 `pressure_raw/loss_threshold`。批次消费者对可能属于当前臂的拒绝回执保守中止，但不以接受 ACK 推进，不能据此声称已建立设备逐请求追踪。

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
  - GET `/`（query `keyword?`, `for_tuning=false`；微调可传 true 获取带来源标记及 mock 内置示例的选择列表，详见 §2.7）、GET `/{id}`、GET `/{id}/versions`、GET `/{id}/file` → `{content(前10000字符), fullLength, truncated}`
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

SQLite（`ros_database.db`，项目根），当前模型 20 张表，模型在 `app/db/models.py`，历史建库种子脚本为仓库根的 `sqlite_create.py`。时间字段 `DateTime(timezone=True)` 默认 `now()`；业务表普遍带软删除 `del_flag` 与 `Notes`。

2026-11-06 新增 `fine_tuning_batches`、`control_safety` 及页面配置表 `ros_debug_settings`。后端启动时已有的 `create_all` 会仅创建缺失表，无需重建/清空现有库，**不要为本次升级运行根种子脚本**。批次执行及恢复按单后端工作进程设计，当前不支持多 worker/多实例同时控制；重启后未完成批次转待核实并保留锁，不恢复动作。连接快照复用 JSON，不对已有业务表追加列。

| 表 | 关键字段 | 说明 |
|---|---|---|
| `Users` | User_ID(PK), Username, Password(bcrypt), Type_ID(1=管理员/2=操作员), Creator_ID(自引用FK), Createtime, Islock, Locktime, Name, Headimage, Birthday, Sex, Modifytime, del_flag, Notes | 用户 |
| `fine_tuning` | id(PK), module_id+unit_id(联合FK→Unit), module_address?, module_descript?, parameter_name(rotation/swing/telescopic), old_value?, new_value, creater_id→Users, create_time, notes, del_flag | 微调记录 |
| `fine_tuning_batches` | id(UUID PK), request_id(Unique), target_key(可空 Unique，真实 SEG:arm / 模拟 mock:SEG:arm), module_id, unit_id, seg, creator_id, request_json, progress_json, status, message, cancel_requested, created_at, updated_at | 幂等请求、逐轴进度与目标锁；完成/人工关闭后 target_key 置空 |
| `control_safety` | id(PK，1=真实、2=模拟), state, generation | MES 急停/解除发送状态及联锁版本，不是设备状态表；两种环境互不清除 |
| `ros_debug_settings` | id(PK，单例 1), revision, config_json | 当前服务连接模式和地址，逐项自动保存 |
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
| 登录即可 | `/user/me`、`GET /user/`、`POST /user/password`、`POST /user/avatar`、`PUT /user/profile/me`、`/drawing/**`、`/work/**`、`/workflow/**`、`/task/**`、`/control/finetuning/batches/**`（含集合创建）、`GET/PATCH /control/debug-settings`、`GET /control/serial_test`、`GET /control/hardware/realtime`、`POST /control/emergency_stop`、`POST /control/emergency_stop/release`、`GET /control/emergency_stop/status` |
| 管理员（`Type_ID==1`） | `POST /user/`、`PUT /user/{id}`、`DELETE /user/{id}`、`lock`、`unlock`、`role`、`POST /user/import`、`GET /user/export` |

认证机制：OAuth2 Bearer Token（`tokenUrl=/api/login`）+ JWT（HS256，payload `{sub, exp}`），bcrypt 密码哈希；WS 用 query `token` 校验。

---
