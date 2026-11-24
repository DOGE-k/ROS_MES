# ROS_MES 数据库表结构

> 本文件由 `ros_mes_hou/tools/dump_schema_md.py` 从 `app/db/models.py` **自动生成**，不要手工编辑。
> 改字段时改 `models.py`（含字段上方注释），再在 `ros_mes_hou/` 下执行
> `python tools/dump_schema_md.py --write` 重新生成；
> `tests/test_db_schema_doc_in_sync.py` 会校验两者是否一致，不一致即测试失败。

## 总览

| # | 表 | 中文名 | 字段数 | 归属 |
|---|---|---|---|---|
| 1 | `Users` | 用户表 | 15 | MES 前后端 |
| 2 | `fine_tuning` | 微调记录表 | 20 | MES 前后端 |
| 3 | `fine_tuning_batches` | 微调批次表 | 14 | MES 前后端 |
| 4 | `control_safety` | 全局安全状态表 | 3 | MES 前后端 |
| 5 | `control_stop_holds` | 局部停记录表 | 11 | MES 前后端 |
| 6 | `ros_debug_settings` | ROS 调试设置表 | 3 | MES 前后端 |
| 7 | `control_sessions` | 模块握手会话表 | 13 | MES 前后端 |
| 8 | `fine_tuning_config` | 微调配置表 | 9 | MES 前后端 |
| 9 | `Drawings` | 图纸表 | 10 | MES 前后端 |
| 10 | `DrawingsVersion` | 图纸版本表 | 9 | MES 前后端 |
| 11 | `works` | 工作表 | 13 | MES 前后端 |
| 12 | `workflows` | 工作流表 | 8 | MES 前后端 |
| 13 | `work_flow_relations` | 工作流关系表 | 9 | MES 前后端 |
| 14 | `Type` | 自适应工装型号表 | 7 | MES 前后端 |
| 15 | `Module` | 模块表 | 8 | MES 前后端 |
| 16 | `Unit` | 机械臂单元表 | 8 | MES 前后端 |
| 17 | `sensors` | 传感器表 | 11 | MES 前后端 |
| 18 | `sensor_log` | 传感器日志表 | 8 | ROS 归档（后端不消费） |
| 19 | `Tasks` | 任务表 | 12 | MES 前后端 |
| 20 | `TasksTracing` | 任务跟踪表 | 7 | MES 前后端 |
| 21 | `calculation` | 计算解析数据日志表 | 11 | ROS 归档（后端不消费） |
| 22 | `point_data` | 点云图解析数据表 | 7 | ROS 归档（后端不消费） |

合计 **22** 张 ORM 表。另有 `can_event_log` 由 ROS 侧建表写入，`models.py` 无 ORM 定义，不在上表内。

---

## `Users`　用户表

| 字段名 | 数据类型 | 允许为空 | 键 | 默认值 | 说明 |
|---|---|---|---|---|---|
| `User_ID` | INTEGER | 否 | 主键 |  |  |
| `Username` | TEXT | 否 |  |  |  |
| `Password` | TEXT | 否 |  |  |  |
| `Type_ID` | INTEGER | 否 |  | 2 |  |
| `Creator_ID` | INTEGER | 否 | 外键→`Users.User_ID` |  |  |
| `Createtime` | DATETIME | 否 |  | 当前时间 |  |
| `Islock` | BOOLEAN | 否 |  | FALSE |  |
| `Locktime` | DATETIME | 是 |  |  |  |
| `Name` | VARCHAR(20) | 是 |  |  |  |
| `Headimage` | VARCHAR(255) | 是 |  |  |  |
| `Birthday` | DATETIME | 是 |  |  |  |
| `Sex` | INTEGER | 是 |  |  |  |
| `Modifytime` | DATETIME | 是 |  |  |  |
| `del_flag` | BOOLEAN | 是 |  | FALSE |  |
| `Notes` | TEXT | 是 |  |  |  |

- 外键 `-`：`(Creator_ID)` → `Users(User_ID)`
- 索引 `ix_Users_User_ID`：`(User_ID)`

## `fine_tuning`　微调记录表

字段语义（初始值/应到值/到位实测/偏差/结论）见接口字段文档 §2.4.4。`new_value` 允许为空：缺少初始值时无法算应到值。

| 字段名 | 数据类型 | 允许为空 | 键 | 默认值 | 说明 |
|---|---|---|---|---|---|
| `id` | INTEGER | 否 | 主键 |  |  |
| `module_id` | INTEGER | 否 | 外键→`Unit.Module_ID` |  |  |
| `unit_id` | INTEGER | 否 | 外键→`Unit.Unit_ID` |  |  |
| `module_address` | INTEGER | 是 |  |  |  |
| `module_descript` | TEXT | 是 |  |  |  |
| `parameter_name` | VARCHAR(100) | 否 |  |  |  |
| `old_value` | FLOAT | 是 |  |  | 初始值：本次发令前的实测位置；下发前检查关闭或缺少起点反馈时为空 |
| `new_value` | FLOAT | 是 |  |  | 应到值 = old_value + requested_delta；缺少初始值时为为空 |
| `requested_delta` | FLOAT | 是 |  |  | 微调量：本次请求的增量（页面输入值），与批次 progress_json 的 position 同义 |
| `observed_position` | FLOAT | 是 |  |  | 到位实测：绝对位置与相对初始值的增量，来自到位事件 angle/100 |
| `observed_delta` | FLOAT | 是 |  |  |  |
| `deviation` | FLOAT | 是 |  |  | 偏差 = observed_delta - requested_delta |
| `position_error` | FLOAT | 是 |  |  | 固件自报误差：到位事件 pos_error/100，设备自述，不参与 MES 判定 |
| `outcome` | VARCHAR(20) | 是 |  |  | 运动结论：moved 已动（默认）/ no_motion 人工标记未动 / unknown 无法判定 |
| `outcome_by` | INTEGER | 是 | 外键→`Users.User_ID` |  |  |
| `outcome_at` | DATETIME | 是 |  |  |  |
| `creater_id` | INTEGER | 否 | 外键→`Users.User_ID` |  |  |
| `create_time` | DATETIME | 否 |  | 当前时间 |  |
| `notes` | TEXT | 是 |  |  |  |
| `del_flag` | BOOLEAN | 是 |  | FALSE |  |

- 外键 `-`：`(creater_id)` → `Users(User_ID)`
- 外键 `-`：`(outcome_by)` → `Users(User_ID)`
- 外键 `fk_fine_tuning_unit`：`(module_id, unit_id)` → `Unit(Module_ID, Unit_ID)`
- 索引 `ix_fine_tuning_id`：`(id)`

## `fine_tuning_batches`　微调批次表

幂等请求 + 逐轴进度 + 目标锁；完成后人工关闭时 `target_key` 置空。

| 字段名 | 数据类型 | 允许为空 | 键 | 默认值 | 说明 |
|---|---|---|---|---|---|
| `id` | VARCHAR(36) | 否 | 主键 |  |  |
| `request_id` | VARCHAR(80) | 否 | 唯一 |  | 前端请求 ID，全局唯一；用于幂等重放，同一 request_id 不会重复下发 |
| `target_key` | VARCHAR(80) | 是 | 唯一 |  | 未完成/待核实批次保留唯一目标锁；终结后置空，SQLite 允许多个 NULL。 |
| `module_id` | INTEGER | 否 |  |  |  |
| `unit_id` | INTEGER | 否 |  |  |  |
| `seg` | INTEGER | 否 |  |  | 模块组号（CAN 帧 SEG 位域） |
| `creator_id` | INTEGER | 否 |  |  |  |
| `request_json` | TEXT | 否 |  |  | 批次请求 JSON：本次三轴微调量 |
| `progress_json` | TEXT | 否 |  |  | 批次进度 JSON：含 steps[] 的逐轴结果，outcome 由各轴 fine_tuning 记录镜像而来 |
| `status` | VARCHAR(30) | 否 |  |  | 批次状态：queued / checking / executing / completed / uncertain / blocked / closed |
| `message` | TEXT | 否 |  |  |  |
| `cancel_requested` | BOOLEAN | 否 |  | FALSE | 是否已请求撤销；执行线程在轴间检查该标记 |
| `created_at` | DATETIME | 是 |  | 当前时间 |  |
| `updated_at` | DATETIME | 是 |  | 当前时间 |  |

- 唯一约束 `-`：`(request_id)`
- 唯一约束 `-`：`(target_key)`

## `control_safety`　全局安全状态表

固定单行。MES 急停/解除的发送状态与联锁代次，不是设备状态表。

| 字段名 | 数据类型 | 允许为空 | 键 | 默认值 | 说明 |
|---|---|---|---|---|---|
| `id` | INTEGER | 否 | 主键 |  | 固定单行：1=真实、2=模拟，两种环境互不清除 |
| `state` | VARCHAR(30) | 否 |  | clear | 全局急停状态：clear 正常 / latched 联锁 |
| `generation` | INTEGER | 否 |  | 0 | 状态代次，每次变化递增，供前端判断状态新鲜度 |

## `control_stop_holds`　局部停记录表

| 字段名 | 数据类型 | 允许为空 | 键 | 默认值 | 说明 |
|---|---|---|---|---|---|
| `id` | INTEGER | 否 | 主键 |  |  |
| `mode` | VARCHAR(10) | 否 |  | real | 执行模式：real 真机 / mock 模拟 |
| `scope` | VARCHAR(10) | 否 |  |  | 停止范围：module 整模块 / axis 单轴 |
| `module_id` | INTEGER | 否 |  |  |  |
| `device_id` | INTEGER | 是 |  |  | 轴号；scope=axis 时有值 |
| `state` | VARCHAR(30) | 否 |  | requested | 状态：requested 已请求 / held 锁定中 / cleared 已解除 |
| `message` | TEXT | 是 |  |  |  |
| `creator_id` | INTEGER | 否 |  | 1 |  |
| `created_at` | DATETIME | 是 |  | 当前时间 |  |
| `cleared_at` | DATETIME | 是 |  |  |  |
| `cleared_reason` | VARCHAR(40) | 是 |  |  | 解除原因，便于追溯是谁因为什么恢复下发 |

- 索引 `ix_control_stop_holds_id`：`(id)`
- 索引 `ix_control_stop_holds_module_id`：`(module_id)`

## `ros_debug_settings`　ROS 调试设置表

固定单行。当前服务连接模式与地址，逐项自动保存；`revision` 递增通知前端刷新。

| 字段名 | 数据类型 | 允许为空 | 键 | 默认值 | 说明 |
|---|---|---|---|---|---|
| `id` | INTEGER | 否 | 主键 |  | 固定单行，id=1 |
| `revision` | INTEGER | 否 |  | 0 | 配置版本，每次保存递增，用于通知前端刷新 |
| `config_json` | TEXT | 否 |  |  | 调试设置 JSON：真实/模拟连接、执行模式等 |

## `control_sessions`　模块握手会话表

| 字段名 | 数据类型 | 允许为空 | 键 | 默认值 | 说明 |
|---|---|---|---|---|---|
| `id` | VARCHAR(36) | 否 | 主键 |  |  |
| `module_id` | INTEGER | 否 |  |  |  |
| `device_id` | INTEGER | 是 |  |  |  |
| `x` | INTEGER | 是 |  |  | 模块地址高 4 位 |
| `y` | INTEGER | 是 |  |  | 模块地址低 4 位 |
| `seg` | INTEGER | 否 |  |  | 模块组号（CAN 帧 SEG 位域） |
| `unit_ids_json` | TEXT | 否 |  |  | 本次绑定的机械臂 Unit_ID 列表 JSON |
| `connection_revision` | INTEGER | 是 |  |  | 建立会话时的后端连接版本号；版本变化则旧会话不可续接 |
| `creator_id` | INTEGER | 否 |  | 1 |  |
| `created_at` | DATETIME | 是 |  | 当前时间 |  |
| `last_active_at` | DATETIME | 是 |  | 当前时间 |  |
| `invalidated_at` | DATETIME | 是 |  |  |  |
| `invalid_reason` | VARCHAR(60) | 是 |  |  | 失效原因：closed 操作员关闭 / superseded 被新握手顶替 / connection_changed 后端连接重建 / expired 超时 / missing 记录缺失 |

- 索引 `ix_control_sessions_module_id`：`(module_id)`

## `fine_tuning_config`　微调配置表

微调页面配置 JSON 快照。

| 字段名 | 数据类型 | 允许为空 | 键 | 默认值 | 说明 |
|---|---|---|---|---|---|
| `id` | INTEGER | 否 | 主键 |  |  |
| `module_id` | INTEGER | 否 | 外键→`Unit.Module_ID`，外键→`sensors.Module_ID` |  |  |
| `unit_id` | INTEGER | 否 | 外键→`Unit.Unit_ID` |  |  |
| `sensor_id` | INTEGER | 否 | 外键→`sensors.sensor_ID` |  |  |
| `config_json` | TEXT | 否 |  |  |  |
| `creater_id` | INTEGER | 否 | 外键→`Users.User_ID` |  |  |
| `create_time` | DATETIME | 否 |  | 当前时间 |  |
| `notes` | TEXT | 是 |  |  |  |
| `del_flag` | BOOLEAN | 是 |  | FALSE |  |

- 外键 `-`：`(creater_id)` → `Users(User_ID)`
- 外键 `fk_fine_tuning_config_sensor`：`(module_id, sensor_id)` → `sensors(Module_ID, sensor_ID)`
- 外键 `fk_fine_tuning_config_unit`：`(module_id, unit_id)` → `Unit(Module_ID, Unit_ID)`
- 索引 `ix_fine_tuning_config_id`：`(id)`
- 索引 `ix_fine_tuning_config_module_id`：`(module_id)`
- 索引 `ix_fine_tuning_config_sensor_id`：`(sensor_id)`
- 索引 `ix_fine_tuning_config_unit_id`：`(unit_id)`

## `Drawings`　图纸表

| 字段名 | 数据类型 | 允许为空 | 键 | 默认值 | 说明 |
|---|---|---|---|---|---|
| `Drawing_ID` | INTEGER | 否 | 主键 |  |  |
| `Drawingname` | TEXT | 否 |  |  |  |
| `Drawingdescripte` | TEXT | 否 |  |  |  |
| `Drawingfile` | TEXT | 否 |  |  |  |
| `Creator_ID` | INTEGER | 否 | 外键→`Users.User_ID` |  |  |
| `Createtime` | DATETIME | 否 |  | 当前时间 |  |
| `Modifytime` | DATETIME | 是 |  |  |  |
| `NewVersion_ID` | INTEGER | 是 | 外键→`DrawingsVersion.DrawingsVersion_ID` |  |  |
| `del_flag` | BOOLEAN | 是 |  | FALSE |  |
| `Notes` | TEXT | 是 |  |  |  |

- 外键 `-`：`(Creator_ID)` → `Users(User_ID)`
- 外键 `-`：`(NewVersion_ID)` → `DrawingsVersion(DrawingsVersion_ID)`
- 索引 `ix_Drawings_Drawing_ID`：`(Drawing_ID)`

## `DrawingsVersion`　图纸版本表

| 字段名 | 数据类型 | 允许为空 | 键 | 默认值 | 说明 |
|---|---|---|---|---|---|
| `DrawingsVersion_ID` | INTEGER | 否 | 主键 |  |  |
| `Drawing_ID` | INTEGER | 否 | 外键→`Drawings.Drawing_ID` |  |  |
| `Drawingfile` | TEXT | 否 |  |  |  |
| `Creator_ID` | INTEGER | 否 | 外键→`Users.User_ID` |  |  |
| `Createtime` | DATETIME | 否 |  | 当前时间 |  |
| `Modify_ID` | INTEGER | 否 | 外键→`Users.User_ID` |  |  |
| `Modifytime` | DATETIME | 是 |  |  |  |
| `del_flag` | BOOLEAN | 是 |  | FALSE |  |
| `Notes` | TEXT | 是 |  |  |  |

- 外键 `-`：`(Creator_ID)` → `Users(User_ID)`
- 外键 `-`：`(Drawing_ID)` → `Drawings(Drawing_ID)`
- 外键 `-`：`(Modify_ID)` → `Users(User_ID)`
- 索引 `ix_DrawingsVersion_DrawingsVersion_ID`：`(DrawingsVersion_ID)`

## `works`　工作表

| 字段名 | 数据类型 | 允许为空 | 键 | 默认值 | 说明 |
|---|---|---|---|---|---|
| `Work_ID` | INTEGER | 否 | 主键 |  |  |
| `Workname` | TEXT | 否 |  |  |  |
| `WorkDescript` | TEXT | 是 |  |  |  |
| `Drawing_ID` | INTEGER | 是 | 外键→`Drawings.Drawing_ID` |  |  |
| `Module_ID` | INTEGER | 是 | 外键→`Module.Module_ID` |  |  |
| `unit_id` | INTEGER | 是 | 外键→`Unit.id` |  |  |
| `sensor_id` | INTEGER | 是 | 外键→`sensors.id` |  |  |
| `data` | TEXT | 是 |  |  |  |
| `creater_id` | INTEGER | 否 | 外键→`Users.User_ID` |  |  |
| `Createtime` | DATETIME | 是 |  | 当前时间 |  |
| `Modifytime` | DATETIME | 是 |  |  |  |
| `del_flag` | BOOLEAN | 是 |  | FALSE |  |
| `Notes` | TEXT | 是 |  |  |  |

- 外键 `-`：`(Drawing_ID)` → `Drawings(Drawing_ID)`
- 外键 `-`：`(Module_ID)` → `Module(Module_ID)`
- 外键 `-`：`(creater_id)` → `Users(User_ID)`
- 外键 `-`：`(sensor_id)` → `sensors(id)`
- 外键 `-`：`(unit_id)` → `Unit(id)`
- 索引 `ix_works_Work_ID`：`(Work_ID)`

## `workflows`　工作流表

| 字段名 | 数据类型 | 允许为空 | 键 | 默认值 | 说明 |
|---|---|---|---|---|---|
| `Workflow_ID` | INTEGER | 否 | 主键 |  |  |
| `Workflowname` | TEXT | 否 |  |  |  |
| `WorkflowDescript` | TEXT | 是 |  |  |  |
| `creater_id` | INTEGER | 否 | 外键→`Users.User_ID` |  |  |
| `Createtime` | DATETIME | 是 |  | 当前时间 |  |
| `Modifytime` | DATETIME | 是 |  |  |  |
| `del_flag` | BOOLEAN | 是 |  | FALSE |  |
| `Notes` | TEXT | 是 |  |  |  |

- 外键 `-`：`(creater_id)` → `Users(User_ID)`
- 索引 `ix_workflows_Workflow_ID`：`(Workflow_ID)`

## `work_flow_relations`　工作流关系表

| 字段名 | 数据类型 | 允许为空 | 键 | 默认值 | 说明 |
|---|---|---|---|---|---|
| `work_flow_relation_ID` | INTEGER | 否 | 主键 |  |  |
| `Workflow_ID` | INTEGER | 否 | 外键→`workflows.Workflow_ID` |  |  |
| `Work_ID` | INTEGER | 否 | 外键→`works.Work_ID` |  |  |
| `flow_seq` | INTEGER | 否 |  |  |  |
| `creater_id` | INTEGER | 否 | 外键→`Users.User_ID` |  |  |
| `Createtime` | DATETIME | 是 |  | 当前时间 |  |
| `Modifytime` | DATETIME | 是 |  |  |  |
| `del_flag` | BOOLEAN | 是 |  | FALSE |  |
| `Notes` | TEXT | 是 |  |  |  |

- 外键 `-`：`(Work_ID)` → `works(Work_ID)`
- 外键 `-`：`(Workflow_ID)` → `workflows(Workflow_ID)`
- 外键 `-`：`(creater_id)` → `Users(User_ID)`
- 索引 `ix_work_flow_relations_work_flow_relation_ID`：`(work_flow_relation_ID)`

## `Type`　自适应工装型号表

| 字段名 | 数据类型 | 允许为空 | 键 | 默认值 | 说明 |
|---|---|---|---|---|---|
| `Type_ID` | INTEGER | 否 | 主键 |  |  |
| `Typename` | TEXT | 否 |  |  |  |
| `Typedescripte` | TEXT | 是 |  |  |  |
| `creater_id` | INTEGER | 否 | 外键→`Users.User_ID` |  |  |
| `Createtime` | DATETIME | 否 |  | 当前时间 |  |
| `del_flag` | BOOLEAN | 是 |  | FALSE |  |
| `Notes` | TEXT | 是 |  |  |  |

- 外键 `-`：`(creater_id)` → `Users(User_ID)`
- 索引 `ix_Type_Type_ID`：`(Type_ID)`

## `Module`　模块表

| 字段名 | 数据类型 | 允许为空 | 键 | 默认值 | 说明 |
|---|---|---|---|---|---|
| `Module_ID` | INTEGER | 否 | 主键 |  |  |
| `Type_ID` | INTEGER | 否 | 外键→`Type.Type_ID` |  |  |
| `Moduledescript` | TEXT | 是 |  |  |  |
| `ModuleAddress` | TEXT | 否 |  |  |  |
| `creater_id` | INTEGER | 否 | 外键→`Users.User_ID` |  |  |
| `Createtime` | DATETIME | 否 |  | 当前时间 |  |
| `del_flag` | BOOLEAN | 是 |  | FALSE |  |
| `Notes` | TEXT | 是 |  |  |  |

- 外键 `-`：`(Type_ID)` → `Type(Type_ID)`
- 外键 `-`：`(creater_id)` → `Users(User_ID)`
- 索引 `ix_Module_Module_ID`：`(Module_ID)`

## `Unit`　机械臂单元表

`Unit_ID` 为业务臂号 32/64/96/128/160（调试数据允许 1~5）；21~25 是 AXIS 臂级设备号，不是本字段取值。

| 字段名 | 数据类型 | 允许为空 | 键 | 默认值 | 说明 |
|---|---|---|---|---|---|
| `id` | INTEGER | 否 | 主键 |  |  |
| `Unit_ID` | INTEGER | 否 |  |  |  |
| `UnitDescript` | TEXT | 是 |  |  |  |
| `Module_ID` | INTEGER | 否 | 外键→`Module.Module_ID` |  |  |
| `creater_id` | INTEGER | 否 | 外键→`Users.User_ID` |  |  |
| `Createtime` | DATETIME | 否 |  | 当前时间 |  |
| `del_flag` | BOOLEAN | 是 |  | FALSE |  |
| `Notes` | TEXT | 是 |  |  |  |

- 唯一约束 `uq_unit_module`：`(Module_ID, Unit_ID)`
- 外键 `-`：`(Module_ID)` → `Module(Module_ID)`
- 外键 `-`：`(creater_id)` → `Users(User_ID)`
- 索引 `ix_Unit_id`：`(id)`

## `sensors`　传感器表

| 字段名 | 数据类型 | 允许为空 | 键 | 默认值 | 说明 |
|---|---|---|---|---|---|
| `id` | INTEGER | 否 | 主键 |  |  |
| `sensor_ID` | INTEGER | 否 |  |  |  |
| `sensordescript` | TEXT | 是 |  |  |  |
| `IsRead` | INTEGER | 否 |  |  |  |
| `Module_ID` | INTEGER | 否 | 外键→`Unit.Module_ID` |  |  |
| `Unit_ID` | INTEGER | 否 | 外键→`Unit.Unit_ID` |  |  |
| `Unit_address` | INTEGER | 否 |  |  |  |
| `creater_id` | INTEGER | 否 | 外键→`Users.User_ID` |  |  |
| `Createtime` | DATETIME | 否 |  | 当前时间 |  |
| `del_flag` | BOOLEAN | 是 |  | FALSE |  |
| `Notes` | TEXT | 是 |  |  |  |

- 唯一约束 `uq_sensor_module`：`(Module_ID, sensor_ID)`
- 外键 `-`：`(creater_id)` → `Users(User_ID)`
- 外键 `fk_sensor_unit`：`(Module_ID, Unit_ID)` → `Unit(Module_ID, Unit_ID)`
- 索引 `ix_sensors_id`：`(id)`

## `sensor_log`　传感器日志表

> **归属**：ROS 侧写入的传感器归档表，后端不消费。`sensor_id` 实际是 AXIS 设备号（1~15 轴 / 21~25 臂级），不是 `sensors.id` 行主键；`sqlite_create.py` 里声明的外键为遗留项，SQLite 未启用 FK 校验。

| 字段名 | 数据类型 | 允许为空 | 键 | 默认值 | 说明 |
|---|---|---|---|---|---|
| `Createtime` | DATETIME | 否 | 主键 | 当前时间 |  |
| `creater_id` | INTEGER | 否 | 外键→`Users.User_ID` |  |  |
| `Work_ID` | INTEGER | 否 | 外键→`works.Work_ID` |  |  |
| `sensor_id` | INTEGER | 否 | 主键，外键→`sensors.id` |  |  |
| `isread` | INTEGER | 否 |  |  |  |
| `data` | TEXT | 否 |  |  |  |
| `del_flag` | BOOLEAN | 是 |  | FALSE |  |
| `Notes` | TEXT | 是 |  |  |  |

- 外键 `-`：`(Work_ID)` → `works(Work_ID)`
- 外键 `-`：`(creater_id)` → `Users(User_ID)`
- 外键 `-`：`(sensor_id)` → `sensors(id)`

## `Tasks`　任务表

`Status` 取值 "0"就绪 / "1"运行中 / "2"已暂停 / "3"已结束，前端 `TaskManage.vue` 的 statusLabel() 只映射这四个值。

| 字段名 | 数据类型 | 允许为空 | 键 | 默认值 | 说明 |
|---|---|---|---|---|---|
| `Task_ID` | INTEGER | 否 | 主键 |  |  |
| `Taskname` | TEXT | 否 |  |  |  |
| `Taskdescripte` | TEXT | 是 |  |  |  |
| `Workflow_ID` | INTEGER | 是 | 外键→`workflows.Workflow_ID` |  |  |
| `Drawing_ID` | INTEGER | 是 | 外键→`Drawings.Drawing_ID` |  |  |
| `creater_id` | INTEGER | 否 | 外键→`Users.User_ID` |  |  |
| `Createtime` | DATETIME | 否 |  | 当前时间 |  |
| `TaskAssignment_id` | INTEGER | 是 | 外键→`Users.User_ID` |  |  |
| `Status` | VARCHAR(20) | 否 |  | 0 |  |
| `Modifytime` | DATETIME | 是 |  |  |  |
| `del_flag` | BOOLEAN | 是 |  | FALSE |  |
| `Notes` | TEXT | 是 |  |  |  |

- 外键 `-`：`(Drawing_ID)` → `Drawings(Drawing_ID)`
- 外键 `-`：`(TaskAssignment_id)` → `Users(User_ID)`
- 外键 `-`：`(Workflow_ID)` → `workflows(Workflow_ID)`
- 外键 `-`：`(creater_id)` → `Users(User_ID)`
- 索引 `ix_Tasks_Task_ID`：`(Task_ID)`

## `TasksTracing`　任务跟踪表

`operate_type`：0启动 / 1暂停 / 2唤醒 / 3结束 / 4编辑 / 5调度入流水线 / 6删除。

| 字段名 | 数据类型 | 允许为空 | 键 | 默认值 | 说明 |
|---|---|---|---|---|---|
| `TasksTracing_ID` | INTEGER | 否 | 主键 |  |  |
| `Task_ID` | INTEGER | 否 | 外键→`Tasks.Task_ID` |  |  |
| `operate_type` | INTEGER | 否 |  |  |  |
| `Workflow_ID` | INTEGER | 否 | 外键→`workflows.Workflow_ID` |  |  |
| `operater_ID` | INTEGER | 否 | 外键→`Users.User_ID` |  |  |
| `operate_time` | DATETIME | 否 |  | 当前时间 |  |
| `Notes` | TEXT | 是 |  |  |  |

- 外键 `-`：`(Task_ID)` → `Tasks(Task_ID)`
- 外键 `-`：`(Workflow_ID)` → `workflows(Workflow_ID)`
- 外键 `-`：`(operater_ID)` → `Users(User_ID)`
- 索引 `ix_TasksTracing_TasksTracing_ID`：`(TasksTracing_ID)`

## `calculation`　计算解析数据日志表

> **归属**：ROS 侧写入的计算解析日志，后端不消费。

| 字段名 | 数据类型 | 允许为空 | 键 | 默认值 | 说明 |
|---|---|---|---|---|---|
| `Createtime` | DATETIME | 否 | 主键 | 当前时间 |  |
| `creater_id` | INTEGER | 否 | 外键→`Users.User_ID` |  |  |
| `Work_ID` | INTEGER | 否 | 外键→`works.Work_ID` |  |  |
| `Module_ID` | INTEGER | 是 | 外键→`Module.Module_ID` |  |  |
| `Unit_ID` | INTEGER | 是 |  |  |  |
| `device_ID` | INTEGER | 是 |  |  |  |
| `isread` | INTEGER | 是 |  |  |  |
| `coord` | TEXT | 是 |  |  |  |
| `position` | TEXT | 是 |  |  |  |
| `del_flag` | BOOLEAN | 是 |  | FALSE |  |
| `Notes` | TEXT | 是 |  |  |  |

- 外键 `-`：`(Module_ID)` → `Module(Module_ID)`
- 外键 `-`：`(Work_ID)` → `works(Work_ID)`
- 外键 `-`：`(creater_id)` → `Users(User_ID)`

## `point_data`　点云图解析数据表

> **归属**：ROS 侧写入的点云解析结果，后端不消费。

| 字段名 | 数据类型 | 允许为空 | 键 | 默认值 | 说明 |
|---|---|---|---|---|---|
| `Createtime` | DATETIME | 否 | 主键 | 当前时间 |  |
| `creater_id` | INTEGER | 否 | 外键→`Users.User_ID` |  |  |
| `Module_ID` | INTEGER | 是 | 外键→`Module.Module_ID` |  |  |
| `point` | TEXT | 否 |  |  |  |
| `arms_address` | TEXT | 否 |  |  |  |
| `del_flag` | BOOLEAN | 是 |  | FALSE |  |
| `Notes` | TEXT | 是 |  |  |  |

- 外键 `-`：`(Module_ID)` → `Module(Module_ID)`
- 外键 `-`：`(creater_id)` → `Users(User_ID)`

