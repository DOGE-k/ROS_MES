# ROS_MES 前后端命名规范

> 参照《ROS 话题命名规范》（第一段前缀定方向：`control`=下发、`hardware`=回传；第二段按数据语义命名）的思路，为前后端制定同等风格的命名规范。
>
> - 适用范围：`ros_mes_hou/`（FastAPI 后端）、`ros_mes_front/`（Vue3 + TS 前端）
> - 原则：**既有代码保持兼容、不强制重命名；新代码一律按本规范执行**，与现状的冲突记录在第 5 节
> - 制定日期：2026-10-05，事例均取自当前代码（v1.1）

---

## 目录

1. [总原则](#1-总原则)
2. [后端命名规范（ros_mes_hou）](#2-后端命名规范ros_mes_hou)
3. [前端命名规范（ros_mes_front）](#3-前端命名规范ros_mes_front)
4. [前后端联动字段命名（接口层）](#4-前后端联动字段命名接口层)
5. [现状不一致清单（历史遗留 vs 新代码要求）](#5-现状不一致清单)

---

## 1. 总原则

ROS 话题规范的思路是"**前缀定方向、名称按数据、后缀定类型**"。前后端映射为三条：

| 原则 | ROS 话题对应 | 前后端对应 |
|---|---|---|
| ① 前缀定职责/方向 | `control` 下发 / `hardware` 回传 | 层级前缀：后端按 `api.endpoints / crud / schemas / services / db` 分层；前端按 `api / stores / components / router / utils` 分层 |
| ② 名称按数据语义 | `rotation` / `telescope` / `gyroscope` | 标识符围绕"资源 + 字段"命名（`drawing_id`、`task_to_dict`、`getDrawingListApi`），不用无意义缩写 |
| ③ 后缀定类型/动作 | `cmd` / `_sequenced` / `output` | 后缀表动作与形态：`_to_dict`、`Create/Update/Response`、`Item/Form/Detail`、`Api` |

其余通用要求：

- 标识符用英文，不拼音混写（历史遗留的 `TuoLuoYi`、`rob_arm` 由队友侧维护，不在本规范范围）；
- 同一概念在整条链路上**只用一个名字**：接口层用 `device_id` 就不要同时出现 `Device_ID`；
- 布尔值用 `is_/has_` 前缀（Python）或 `isXxx`（TS）；常量用 `UPPER_SNAKE_CASE`。

---

## 2. 后端命名规范（ros_mes_hou）

### 2.1 分层与文件

| 层 | 职责（对应 ROS"方向"） | 文件命名 | 事例 |
|---|---|---|---|
| `app/api/endpoints/` | 路由层：接收前端请求 | `<资源名>.py`，与路由前缀一致 | `task.py` 挂 `/task`、`control.py` 挂 `/control` |
| `app/crud/` | 数据库读写 | `<资源名>.py` | `device.py` 里 `get_device/create_device` |
| `app/schemas/` | 请求/响应模型 | `<资源名>.py` | `finetuning.py` 定义 `FineTuningCreate` |
| `app/services/` | ROS 通信/外部服务 | 按机制命名 | `rosbridge_gateway.py`、`ros_control.py`、`ros_service.py` |
| `app/db/` | ORM 模型与连接 | 固定 | `models.py`、`database.py` |
| `app/core/` | 配置与安全 | 固定 | `config.py`、`security.py` |

### 2.2 路由与端点

| 规则 | 事例 | 说明 |
|---|---|---|
| 路由前缀 = 资源名词（单数） | `/user`、`/drawing`、`/task`、`/model`、`/device`、`/unit`、`/control`、`/finetuning` | 与 ROS `control/hardware` 分段同理，第一段定资源域；`/sensors` 复数为历史特例，保留但不再新增复数前缀 |
| 资源 CRUD 用标准动词 | `GET /task/list`、`POST /task/create`、`PUT /task/{task_id}`、`DELETE /task/{task_id}` | 路径用小写，路径参数 `<资源>_id`（`task_id`、`drawing_id`、`user_id`） |
| 状态机/特殊动作用动作端点 | `POST /task/{id}/start`、`/pause`、`/resume`、`/finish`、`/dispatch`；`PUT /user/{id}/lock`、`/unlock`、`/role` | 对应 ROS 的 `_sequenced` 思路：动作显式写进路径 |
| 文件查询/子资源 | `GET /device/by_model/{model_id}`、`GET /unit/by_device/{device_id}`、`GET /model/tree` | `by_<字段>` 表示按字段过滤 |

### 2.3 Python 标识符

| 对象 | 规范 | 正例（现有代码） | 反例/注意 |
|---|---|---|---|
| SQLAlchemy 模型类 | PascalCase 单数 | `User`、`Task`、`Drawing`、`Module`、`Unit`、`Sensor` | 类名单数、表名允许历史遗留 |
| 数据库表名（新表） | snake_case | `fine_tuning`、`work_flow_relations`、`point_data` | 旧表 `Users`/`Drawings`/`works`/`Type` 大小写单复数混乱，**保留不改**（见 5 节） |
| 列名（新表） | snake_case | `module_id`、`parameter_name`、`create_time` | 旧表 PascalCase 列（`User_ID`、`Drawingname`）保留不改 |
| Pydantic 模型 | `<实体><Base\|Create\|Update\|Response>` | `DeviceCreate`、`UnitUpdate`、`FineTuningResponse`、`TokenData` | 实体名与模型类一致 |
| CRUD 函数 | `<动词>_<实体>` 及 `<动词>_<实体>_by_<字段>` | `get_device_by_model_and_address`、`create_fine_tuning_record`、`update_unit`、`delete_device` | 动词固定：`get / create / update / delete / save / parse` |
| 序列化函数 | `<实体>_to_dict` | `user_to_dict`、`task_to_dict`、`work_to_dict`、`workflow_to_dict`、`drawing_to_dict` | `serialize_model`/`serialize_device` 是旧风格，新代码用 `*_to_dict` |
| 服务层函数 | 动词开头 | `build_fine_tuning_publish_payload`、`build_module_confirm_publish_payload`、`dispatch()`、`stream_feedback()`、`publish_ros_command()` | `build_*_publish_payload` 专指"构造 rosbridge 发布载荷" |
| 常量 | UPPER_SNAKE_CASE | `ROSBRIDGE_URL`、`FEEDBACK_TOPICS`、`SECRET_KEY`、`SYSTEM_MODULE_ID` | 环境变量读取统一 `os.getenv("X", 默认值)` 写在模块顶部 |
| 私有回调 | `_` 前缀 | `_cb_rotation_raw`、`_wait_for_module_confirm_success` | 类内私有方法加 `_` |

### 2.4 响应结构

- 统一包装 `{"code": int, "message": str, "data": <载荷>}`；错误信息放 FastAPI `detail`；
- `data` 内字段**新增接口一律 snake_case**（`task_to_dict` 的 `Task_ID, Workname` 等属历史遗留，保持不动）。

---

## 3. 前端命名规范（ros_mes_front）

### 3.1 文件与目录

| 对象 | 规范 | 正例 | 说明 |
|---|---|---|---|
| 页面组件 | PascalCase `.vue`，一个功能一个目录 | `components/Main/TaskManage/TaskManage.vue` | 目录名 = 组件名 |
| API 模块 | camelCase `.ts` | `api/rosApi.ts`、`api/types.ts`、`api/noRosDebug.ts` | |
| 状态仓库 | camelCase 文件，store id 同名 | `stores/user.ts` → `defineStore('user')` | |
| 环境变量 | `VITE_` 前缀 | `VITE_API_TARGET`、`VITE_DEBUG_NO_ROS` | |

### 3.2 路由

- 路由 `path` 用 PascalCase 页面名（现状 `/Dashboard`、`/TaskManagement`、`/RosTestPage`）；
- **新增页面统一：`path` = 组件文件名去 `.vue`**（如 `FineTuningPage.vue` → `/FineTuningPage`），避免现状中 `/Dashboard` ↔ `DashboardPage.vue`、`/DrawingManage` ↔ `DrawingManage.vue` 的对应关系不一致。

### 3.3 TypeScript 类型

| 场景 | 后缀 | 正例（现有代码） |
|---|---|---|
| 列表/表格行 | `Item` | `TaskItem`、`WorkItem`、`DrawingItem`、`FineTuningItem` |
| 表单提交 | `Form` | `TaskForm`、`DrawingForm`、`LoginForm` |
| 详情（含子结构） | `Detail` | `WorkflowDetail` |
| 通用包装 | `ApiResponse<T>` | `{ code, message, data }` |
| 树/结构节点 | 语义名词 | `TreeNode`、`DashboardStats` |

### 3.4 API 封装函数（`src/api/rosApi.ts`）

| 规则 | 事例 | 说明 |
|---|---|---|
| `<动词><资源>[Api]` | `getUserListApi`、`createWorkApi`、`deleteDrawingApi`、`importDrawingApi` | 动词固定：`get / create / update / delete / import / save / send / test` |
| ROS 控制类不加 `Api` | `sendRosMessage`、`createModule`、`sendFineTuning`、`testSerialConnection` | 对应 ROS"下发"语义（`control`），与业务 CRUD 区分 |
| 新增封装一律带 `Api` 后缀 | `getDrawingListApi` ✓ | 现状约一半带一半不带（见 5 节），新代码统一带 |

### 3.5 组件内标识符（`<script setup>`）

| 对象 | 规范 | 正例（现有代码） |
|---|---|---|
| ref / reactive | camelCase 名词 | `treeData`、`treeRef`、`filterText`、`expandedKeys` |
| 布尔状态 | `isXxx` | `isEditing` |
| 数据加载函数 | `load<资源>` / `fetch<资源>` | `loadUsers`、`loadTree`、`fetchUsers` |
| 事件处理函数 | `handle<动作>` | `handleSaveConfig`、`handleSubmit` |
| 普通常量 | UPPER_SNAKE_CASE | `ARM_OPTIONS`、`SENSOR_OPTIONS`、`FEEDBACK_TOPICS` |
| Store 使用 | `use<名>Store` | `useUserStore`、`useLayoutSettingStore` |
| localStorage key | 全小写 | `account`、`nickname`、`role`、`token`、`avatar`、`updateTime` |

---

## 4. 前后端联动字段命名（接口层）

> 对应 ROS 规范中"第二段按要传的数据命名"——**接口字段的名字 = 数据本身的名字**，前后端必须逐字一致。

| 类别 | 规范 | 事例 |
|---|---|---|
| 业务五元组 | 固定为 `device_id / module_id / unit_id / unit_row_id / drawing_id`（snake_case） | `POST /coordination/send` 请求体、WS payload 的 `business` 字段 |
| 坐标编码 | `module_id = x*16 + y`；模块表 `DeviceAddress = (x<<4) \| y` | 前端 `ModuleManagement.vue` 计算，后端/ROS 直接透传 |
| 微调参数名 | `parameter_name` ∈ {`rotation`, `swing`, `telescopic`} | 映射三个 `/control/adjust_*_cmd` 话题 |
| WS 数据类型枚举 | `data_type` ∈ {`rotation_axis_encoder`, `swing_axis_encoder`, `telescope_axis_encoder`, `pressure_sensor`, `imu_pose`, `error`} | 前端 `FineTuningPage.vue` 按此分发渲染，两端共用同一套枚举值 |
| 别名兼容 | `Device_ID→device_id`、`new_value→position` 等双别名**仅限既有接口**；新增接口一个字段只允许一个名字 | `FineTuningCreate` 的 validator 兜底 |
| 时间字段 | 接口层统一 ISO 字符串；字段名 `create_time`（新）/ 旧接口的 `Createtime` 保持不动 | `user_to_dict` 输出 `createtime` 属遗留 |

---

## 5. 现状不一致清单

> 参照 ROS 规范中"ros 内部节点之间不做命名上的要求"的处理方式——以下均为**历史遗留，保持兼容、不再扩散**；新代码一律按第 2~4 节执行。

| # | 现状 | 冲突点 | 新代码要求 |
|---|---|---|---|
| 1 | `works` 表同时有 `Module_ID` 与 `Device_id` 两列（同义） | 同一概念两个名字 | 统一用 `module_id`；`Device_id` 仅作响应兼容输出 |
| 2 | `Device_ID` / `device_id` 双别名（schemas、`/module/` 请求体） | 大小写两套 | 新接口只收 `device_id` |
| 3 | 路由前缀 `/sensors` 复数，其余单数（`/unit`、`/device`） | 单复数不一 | 保留现状，新增路由用单数 |
| 4 | endpoints 文件名一半带 `_api`（`device_api.py`、`model_api.py`），一半不带（`task.py`、`drawing.py`） | 文件名风格不一 | 新文件不带 `_api` 后缀，与路由前缀同名 |
| 5 | 序列化函数 `*_to_dict` 与 `serialize_*` 并存 | 函数命名两套 | 新代码用 `<实体>_to_dict` |
| 6 | 前端 API 函数 `*Api` 后缀约一半带一半不带（`getUserListApi` vs `getDashboardStats`）；还有别名行 `sendCoordination = sendCoordinate` | 函数命名两套 | 新增一律带 `Api`；ROS 控制类（send/test/create module）除外 |
| 7 | `work/workflow` 的创建/更新参数走 query string 且为 PascalCase（`Workname`、`Workflow_ID`），其余接口为 JSON body + snake_case | 参数位置与大小写两套 | 新接口用 JSON body + snake_case；旧接口前端按现状调用 |
| 8 | 数据库旧表名/列名 PascalCase、单复数混用（`Users`、`Drawings`、`works`、`TasksTracing` vs `fine_tuning`、`point_data`） | 表命名两套 | 旧表不动；新表 snake_case，模型类单数 |
| 9 | `types.ts` 的 `UserInfo`（`username/role/email`）与登录实际响应（`account/name/typeId/headImage`）不一致 | 前后端字段对不上 | 以实际响应为准修正类型定义 |
| 10 | 路由 path 与组件名对应关系不一（`/Dashboard`↔`DashboardPage.vue`，`/DrawingManage`↔`DrawingManage.vue`） | path 规则不一 | 新页面 `path` = 组件文件名去 `.vue` |

---

## 附：命名速查卡

```
后端  文件     <资源>.py（endpoints/crud/schemas 同名）
     路由     /<资源单数>/{资源}_id/动词
     模型类   PascalCase 单数        表(新)  snake_case
     Schema   <实体>Create|Update|Response
     CRUD     get_/create_/update_/delete_<实体>
     序列化   <实体>_to_dict
     服务     build_*_publish_payload / dispatch / stream_*

前端  文件     组件 PascalCase.vue；ts 模块 camelCase
     路由     path = 组件文件名去 .vue
     类型     <实体>Item|Form|Detail；ApiResponse<T>
     API      <动词><资源>Api（ROS 控制类除外）
     组件内   load<资源> / handle<动作> / isXxx
     常量     UPPER_SNAKE_CASE        store   use<名>Store

联动  字段     snake_case；业务五元组 device_id/module_id/unit_id/unit_row_id/drawing_id
     枚举     data_type/parameter_name 两端共用同一套值
     编码     module_id = x*16+y
```
