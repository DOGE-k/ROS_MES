# ROS_MES 前后端 ↔ ROS 接口清单（三轴版 V2.1）

> **收录说明**（2026-10-25）：本文档由队友基于 ROS 源码现状整理（整理日期 2026-10-24），收录进仓库时仅把原文中的本机绝对路径链接改为仓库相对路径；**取代**《ROS_MES_前后端接口字段文档.md》中的 ROS 话题 / 消息 / device_id 编码部分（四轴布局已失效），该文档的业务接口与数据库部分仍有效。**团队已确认：本文档为 ROS 对接唯一权威。**
>
> **后端已处理项**（同日提交，勿重复修改）：7.1 模块确认回执超时已调至 35s（`ROS_MODULE_CONFIRM_ACK_WAIT_S`）；模块确认业务接口使用 `module_id/device_id/unit_id(s)`，不向前端暴露 ROS 的 `seg/arm/position`；后端适配层通过显式 `ROS_MODULE_SEG_MAP` 将业务 `module_id` 映射为 ROS `seg`，再按 `Unit_ID÷32` 映射为 `arm=1~5`，发送 `position=[100, seg, arm]`；7.3 的反馈标签表三轴化已完成，源码种子定义包含 5 臂（Unit_ID 32/64/96/128/160），实际部署数据库以现有记录为准；7.4 的 `/hardware/cmd_ack` 已加入反馈流，**枚举已从源码提取**：仅超位拒绝一种（`ack_msg=1, result=3, detail=1上限/2下限`），无成功回执；7.8 已解决（旧 rospy 路径迁入 `app/ros/ros1/native.py`）。**前端已处理项**：`deviceEncoding.ts` 已改三轴编码。**新增**：急停解除接口 `POST /api/control/emergency_stop/release`（发布 `/control/softstop_release`，softstop_node 源码确认转发 `[0x04]`）。
>
> **图纸话题已定论**（2026-10-25 ROS 端确认"按接口的来"）：话题以本文档 `/frontend_pointcloud_topic`（无前缀）为准，ROS 端自行将其 `rob_arm.env` 的 `ROS_TOPIC_FRONTEND_POINTCLOUD` 改为无前缀；后端零改动。联调时验证一次"图纸下发 → 三视图"链路即可。
>
> **2026-11-20 源码对齐**：补充人工校零 `/control/axis_zero`、轴状态聚合节点、`/hardware/module_status` 在线轴过滤；反馈话题由 8 路增至 13 路；伸缩软限位按当前 `rob_arm.env` 为 **-20 ~ +20mm**（此前 0~30mm 与 -10~20mm 均已作废）。现网运行入口仍为 `robot_control_backend/`（ROS1 Noetic）；`ros2_robot_control_backend/` 是 rclpy 迁移副本，未作为现场入口。

---

## 1. 链路结构

```
前端 Vue ──HTTP/WS──> 后端 FastAPI ──rosbridge ws:9010──> ROS 话题
                      （app/ros/rosbridge.py 是唯一桥）
```

- 前端**不直连** rosbridge，全部经后端转发。
- 反馈流：后端订阅 ROS 话题 → 标准化 → 经自有 WebSocket `/api/control/feedback/ws` 推给前端。
- rosbridge 地址：`ROSBRIDGE_URL` 环境变量，默认 `ws://localhost:9010`（launch 里 rosbridge 端口 9010）。

---

## 2. 前端 → 后端 HTTP 接口

| 接口 | 方法 | payload | 触发的 ROS 话题 |
|---|---|---|---|
| `/api/control/finetuning` | POST | `{module_id, device_id, unit_id, parameter_name, position}` | 按 `parameter_name` 路由到 `/control/adjust_{rotation,swing,telescopic}_cmd` |
| `/api/control/finetuning/batches` | POST | `{request_id, module_id, unit_id, adjustments, connection_revision}` | 登记批次后逐轴发布 `/control/adjust_*_cmd`；状态经批次查询接口返回 |
| `/api/finetuning/config` | POST | 配置快照 + `calibrated`、`notes` | `calibrated=true` 时先发布 `/control/axis_zero`（IntCmd）；发布失败返回 503 且不落库 |
| `/api/coordination/send` | POST | 图纸文件路径 | `/frontend_pointcloud_topic`（std_msgs/String，JSON `{"file_path":...}`）→ data_process_node |
| `/api/module/` | POST | `{x, y, module_id?, device_id?, unit_ids}` | `/control/module_cmd`（IntCmd）→ module_confirme_node；业务层继续使用模块/设备/机械臂单元字段，后端逐个确认所选 `unit_ids` |
| `/api/control/feedback/ws` | WebSocket | — | 后端订阅 13 路 ROS 反馈话题转发（含 `/hardware/axis_status`、到位/停止/故障/限位） |
| `/api/control/emergency_stop` | POST | — | `/control/softstop` → softstop_node 转发 `/arm/cmd_vel` [1] |
| `/api/control/emergency_stop/release` | POST | — | `/control/softstop_release` → softstop_node 转发 `/arm/cmd_vel` [4]（V2.1 新增） |

- `parameter_name` 取值：`"rotation"` / `"swing"` / `"telescopic"`，其他值网关直接报错。
- 微调 `position` 语义：**增量**（旋转/摆动单位°，伸缩单位 mm）。

---

## 3. 后端 → ROS 话题（发布）

来源：`mes_web/ros_mes_hou/app/ros/rosbridge.py`（2026-10-25 前为 `app/services/rosbridge_gateway.py`）

| 话题 | 消息类型 | 字段构造 |
|---|---|---|
| `/control/adjust_rotation_cmd` | RotationCmd | `module_id/device_id` 前端透传；`position=[float(增量°)]` |
| `/control/adjust_swing_cmd` | SwingCmd | 同上 |
| `/control/adjust_telescopic_cmd` | TelescopicCmd | 同上（增量 mm） |
| `/control/module_cmd` | IntCmd | `{module_id, device_id:0, position:[100, seg, arm]}`，见 §6 握手协议；`seg/arm` 仅在 ROS 适配层生成 |
| `/control/axis_zero` | IntCmd | `{module_id: 业务模块号, device_id: 0, position: [arm]}`；仅复位目标臂 ROS 软件基准/状态缓存，不发 CAN 运动 |
| `/frontend_pointcloud_topic` | std_msgs/String | `{"file_path": "<图纸路径>"}` |

发布流程：`advertise` → 等 0.1s → `publish`。仅**模块确认**会临时订阅回执话题等待结果。

网关校验：`device_id` 校验范围 1~15（三轴，V2.1）；`module_id` 必须为正整数，禁止后端写死。

---

## 4. 后端订阅的 ROS 话题（→ 前端 WS）

来源：`app/ros/profile.py` 话题表 + `app/ros/normalizer.py`

| 话题 | 消息 | data_type 标签 | 单位/语义 |
|---|---|---|---|
| `/hardware/rotation_feedback` | RotationCmd | `rotation_axis_encoder` | **度**（feedback_node 已 ÷100） |
| `/hardware/swing_feedback` | SwingCmd | `swing_axis_encoder` | 度 |
| `/hardware/telescope_feedback` | TelescopicCmd | `telescope_axis_encoder` | **mm**（feedback_node 已 ÷100） |
| `/hardware/sensor_feedback` | SensorCmd | `pressure_sensor` | 压力瞬时值（臂级 device_id 21~25） |
| `/hardware/pressure_avg` | SensorCmd | `pressure_average` | 5s 窗口均值（臂级 21~25） |
| `/hardware/imu_angles` | 陀螺姿态 | `imu_pose`，附带 `swing_angle/rotation_angle/x/y/z` | 末端位姿（臂级 21~25） |
| `/hardware/vacuum_loss` | VacuumLoss | `vacuum_loss_event` | 失压告警（臂级 21~25） |
| `/hardware/cmd_ack` | CmdAck | `cmd_ack`（透传 `ack_msg/result/detail`） | 指令回执（V2.1）。**源码提取枚举**：仅超位拒绝一种——`ack_msg=1, result=3, detail=1上限/2下限`；无成功回执 |
| `/hardware/axis_status` | AxisStatus | `axis_status` | 三轴状态字；`base_valid`、`axis_state`、`status_bits`。固件周期帧缺失时由 `axis_status_aggregator.py` 按 5Hz 推导发布 |
| `/hardware/arrive_notification` | ArriveNotification | `arrive_notification` | 到位事件：`angle/pos_error/status_bits/flags`，`angle` 按 0.01°/0.01mm 换算 |
| `/hardware/stop_notification` | StopNotification | `stop_notification` | 停止事件：`stop_reason`（1=到位 2=急停 3=指令停止 4=限位 5=故障 6=看门狗）、`output_level` |
| `/hardware/axis_fault` | AxisFault | `axis_fault` | 轴故障：`fault_bits/local_action/detail/duration_ms` |
| `/hardware/limit_event` | LimitEvent | `limit_event` | 限位事件，用于批次阻断与前端告警 |

标准化后转发字段：`{time_id, topic, header, module_id, device_id, position, data_type, feedback_type, raw, ...}`。前端按 `device_id` 映射到臂/轴显示（FineTuningPage.vue）。

---

## 5. device_id 编码（三轴布局，ROS 侧现行）

| 范围 | 含义 |
|---|---|
| 0 | 系统级（急停/解除/模块停，`/arm/cmd_vel` position=[1]/[4]/[8]）；人工校零时 `/control/axis_zero` 也使用 `device_id=0`，`position=[arm]` |
| 1~15 | 轴级：`(臂号-1)*3 + 关节`；关节 1=旋转 / 2=摆动 / 3=伸缩 |
| 21~25 | 臂级传感器（压力/IMU 共用，按话题区分），臂号 = device_id - 20 |

轴号速查：臂1=1/2/3，臂2=4/5/6，臂3=7/8/9，臂4=10/11/12，臂5=13/14/15。

---

## 6. 模块确认（会话式握手）契约

方案来源：《固定工位会话式模块确认方案》。流程：宣告 → 分配 → 三项核对（UID56+SEG+Result=0）→ READY。

### 6.1 业务接口与 ROS 适配边界

前端和后端业务接口继续使用项目已有字段：

| 字段 | 含义 |
|---|---|
| `module_id` | 业务模块号，后端原样带入 ROS 回执匹配 |
| `device_id` | 业务模块设备号，沿用现有模块接口语义 |
| `unit_ids` | 本次确认的机械臂 `Unit_ID` 数组；页面可一次选择 1~5 台，后端按顺序逐台确认 |
| `x/y` | 现有模块坐标字段，保留用于模块选择和兼容既有调用 |

业务接口不接收 `station`、`seg` 或 ROS `arm`。后端适配层从显式 `ROS_MODULE_SEG_MAP` 读取 `module_id → seg`，并按机械臂 `Unit_ID` 映射 `arm=1~5`。映射缺失时必须拒绝下发，禁止把业务模块号直接猜作 `seg`。

### 6.2 下行 `/control/module_cmd`（IntCmd）

| 字段 | 值 |
|---|---|
| `module_id` | 后端业务模块号，**回执原样返回**（后端按它匹配 ACK） |
| `device_id` | 固定 0 |
| `position` | `[100, seg, arm]`：100=触发握手；`seg` 为 ROS 下位机组号 0~14；`arm` 为组内臂槽位 1~5 |

`device_id=0` 是当前 ROS 模块级指令协议的固定值，仅存在于 ROS 适配后的 IntCmd；业务层的 `device_id` 继续保留原命名。一次请求包含多个 `unit_ids` 时，后端逐个发布一条 `[100, seg, arm]`；同一时间只给一台未绑定机械臂上电。某条确认失败时停止后续项，接口返回已成功项、失败项和未处理项。

**回执**（二选一，网关等待其中一个）：

| 话题 | 判定 | HTTP |
|---|---|---|
| `/hardware/module_confirm_success` | `module_id` 匹配 且 `device_id==0` 且 `position[0]==100` | 200 |
| `/hardware/web_module_cmd` | `module_id` 匹配 且 `device_id==0` 且 `position[0]==1` | 502 |

ROS 侧超时参数（rob_arm.env）：等宣告 `MODULE_CONFIRM_WAIT_ANNOUNCE_S=30.0`；等确认 `MODULE_CONFIRM_ACK_TIMEOUT_S=0.3`、重试 `MODULE_CONFIRM_MAX_RETRY=3`（Seq 递增）。
后端回执等待上限：`ROS_MODULE_CONFIRM_ACK_WAIT_S`（默认 35s，须 ≥ 宣告窗口 + 重试时间）。

### 6.3 页面操作顺序（2026-10-28 调整）

1. **模块管理页**只选择 X/Y 模块坐标。页面检查模块是否登记后进入微调页，此时不调用 `/api/module/`，也不发送 ROS 确认。
2. **微调页的首次配置弹窗**加载该模块下登记的机械臂，可一次选择 1~5 台机械臂和一张图纸。确认后先调用 `/api/module/`，其中 `unit_ids` 为所选机械臂的 `Unit_ID` 数组；收到成功回执后，再为确认成功的每台机械臂调用 `/api/coordination/send` 下发同一张图纸。确认或图纸下发失败时留在弹窗，成功后进入微调页。
3. **微调主页面**常驻机械臂切换入口。切换只在本次首次确认成功的机械臂之间进行，不再重复弹出机械臂和图纸选择框；页面会恢复各自的图纸、三视图、调整值及反馈显示。
4. 如需更换当前机械臂的图纸，使用主页面的“重新下发图纸”入口重新选择。重发只作用于当前机械臂，不重复执行本次已成功的模块确认。

各臂状态只保留在当前页面会话中，刷新或离开后需重新配置；页面缓存不代表断电后的设备仍已确认。确认、图纸下发、微调或保存请求进行中禁止切换控制目标，避免请求结果写入另一台机械臂。

历史说明：此前“在模块管理页多选机械臂，并以路由 `unit_ids` 限制微调页选项”的页面流程已被本节取代；HTTP 字段命名、后端批量能力和 ROS `[100, seg, arm]` 协议保持不变。

### 6.4 在线轴识别（2026-11-20 源码）

`control_node.py` 订阅 `/hardware/module_status`，把状态应答的 `exist_mask` bit0~2 解释为从 `axis_base` 起的三轴是否存在。图纸逆解分阶段等待到位时，只等待“本阶段增量非空且在线”的轴；尚无在线信息时回退为等待全部增量轴，避免旧固件不返回 `module_status` 时整条链路停住。某阶段没有在线轴则直接进入下一阶段。该校验只收缩等待集合，不改变已下发的增量。

---

## 7. 注意事项（按严重度）

### 🔴 7.1 模块确认网关超时 5s vs 握手窗口 30s —— 必然 502（**后端已修**）

后端等待回执超时已与普通超时分离：`RosbridgeClient(module_confirm_timeout=…)`，默认取 `ROS_MODULE_CONFIRM_ACK_WAIT_S`（35s）。

### 🔴 7.2 业务字段与 ROS 下行字段分层 —— **已按新协议调整**

旧流程的 `station` 已移除。前端只选择模块和机械臂，业务请求使用 `module_id/device_id/unit_ids`；后端通过 `ROS_MODULE_SEG_MAP` 完成 `module_id → seg`，再把 `Unit_ID` 映射成 `arm=1~5`，最终发送 `position=[100, seg, arm]`。映射缺失或 `arm` 无法落在 1~5 时直接返回 422，不能回退为 `position=[100, station]` 或把 `module_id` 当作 `seg`。

### 🔴 7.3 device_id 三轴化 —— 后端已改，前端已同步，部署库数据需核对（**部分待办**）

前端 `deviceEncoding.ts` 与后端已同步为三轴：`(arm-1)*3 + {1,2,3}`（1~15）、臂级 21~25 不变。
源码种子定义包含 5 臂（32/64/96/128/160），但现有部署数据库可能仍只有 3 臂；上线前必须核对 `Unit` 表，不能因源码已有 5 臂就假定部署库已补齐。

### 🟠 7.4 微调无回执 —— 超位拒绝前端无感知（**后端已修，前端待接**）

`/hardware/cmd_ack` 已加入后端反馈流（`data_type=cmd_ack`，透传 `result/detail`）。前端 FineTuningPage 可按该标签提示"超位被拒绝"。

### 🟡 7.5 伸缩轴单位（**已定论：话题边界两向均为 mm，MM_PER_REV 废弃**）

**2026-10-25 晚 ROS 端定稿并已推送（3ed42f3《更新伸缩杆执行层逻辑》）**：电机3 为直线位移轴，下位机 CAN 字段单位 0.01mm——`telescopic_node` 接收 **mm 增量**（软限位读取 `TELESCOPIC_MIN_MM / TELESCOPIC_MAX_MM`，内部 ×100 透传 CAN）、`feedback_node` 回传 **mm 实测长度**（CAN 0.01mm ÷100），`TelescopicCmd.msg` 注释同步更新。
即：**ROS 话题边界两向均为 mm，与前后端语义天然一致——后端零换算、前端零改动**（MM_PER_REV 参数废弃；此前曾按"话题 0.01mm"做的 ×100/position_mm 预实现已撤销）。伸缩显示直接用反馈 position（mm），伸缩下发直接传 mm 增量。

> 2026-11-20 按 `rob_arm.env` 复核：伸缩软限位为 **-20 ~ +20mm**（2026-11-14 由 -10~20 调整）；超限日志为 `⚠️ Arm%d 伸缩超位...指令已丢弃`。旧的 0~30mm 描述作废。

| 环节 | 单位 |
|---|---|
| `/control/adjust_telescopic_cmd`（前端下发） | mm |
| CAN 下行 MSG=1 相对增量 | 0.01mm |
| CAN 上行位置反馈 | 0.01mm |
| `/hardware/telescope_feedback`（前端展示） | mm |

**前端无需换算**，输入框按 `(mm)`、反馈按 mm 直接展示。前提：固件需按 0.01mm 解析伸缩轴 MSG=1（下位机侧待确认，属外部依赖，不改 ROS/前端）。

### 🟠 7.6 反馈 module_id 是 SEG，不是业务模块号（**下行已动态寻址，上行仍为 SEG**）

hardware_node 上行反馈 `module_id = CAN SEG 位域`（0~14），与前端下发的业务 module_id 不同空间。当前前端按 device_id 匹配所以未暴露；任何按 module_id 关联的逻辑都会错。

**下行运动帧已改为动态 SEG 路由（原 P0-3 已修）**：
- module_confirme_node 握手成功后发布 `/control/seg_bind`（`IntCmd`，`position=[SEG]` 绑定 / `[-1]` 解绑），hardware_node 维护 `module_id → SEG` 表；
- 运动帧（MSG=1）、单轴停止（MSG=3）、模块停（`0x08|SEG<<18`）均按该业务模块绑定的 SEG 构造，不再固定 SEG=0；
- 未绑定（未做模块确认）时回退 `CAN_DEFAULT_SEG=0`，保证单工位可用；
- 某工位断电重启（重新宣告未编号）时，module_confirme_node 自动解绑该模块的 SEG，避免运动帧继续发往未编号的组；
- CAN 过滤器已去掉 SEG 位（`cls_mask=0x1FC3E000`），任意组（SEG=0~14）的反馈/事件/传感器帧都能收到。

### 🟢 7.7 急停链路（**已闭环**）

ROS 侧系统级指令走 `/arm/cmd_vel`（device_id=0，position=[1]急停/[4]解除/[8]模块停）。后端现状：
- `POST /api/control/emergency_stop` → `/control/softstop`，softstop_node（源码已核对）转发 `/arm/cmd_vel` [0x01]；
- `POST /api/control/emergency_stop/release`（V2.1 新增）→ `/control/softstop_release`，softstop_node 转发 [0x04]；
- "模块停"（[0x08, module_id]）与"单轴急停"（[0x0C]）暂无入口，如需再立项。

### 🟢 7.8 旧路径残留（**已解决**）

rospy 直发 `/web_cmd` 的旧路径已迁移为 `app/ros/ros1/native.py`（ROS1 适配器专属通道，ROS2 适配器无此通道），与 rosbridge 网关各司其职。

---

## 8. ROS1 / ROS2 差异速查表

> 本文其余部分（话题、消息、device_id 编码、握手语义）是**版本无关的契约**，ROS1 与 ROS2 下应完全一致；两个版本的差异只有下表几项，代码层面的唯一真相是 `mes_web/ros_mes_hou/app/ros/profile.py`。后端切换用环境变量 `ROS_VERSION=1|2`（见 `deploy/config/backend.env`），业务接口不感知版本。

| 差异项 | ROS1（现网） | ROS2（预设，待移植定稿核对） |
|---|---|---|
| 自定义消息类型串 | `robot_control_backend/IntCmd` | `robot_control_backend/msg/IntCmd` |
| std_msgs 类型串 | `std_msgs/String` | `std_msgs/msg/String` |
| `header.stamp` 字段名 | `secs` / `nsecs` | `sec` / `nanosec` |
| 测试通道（`/web_cmd`、`/robot_status`，`/ros/**` 接口） | **两版一致**：2026-10-25 起统一经 rosbridge（干净 venv 无 rospy 也能用），rospy 直连保留为 ROS1 历史兼容 | 同左 |
| 构建与启动 | catkin_make + roslaunch（Noetic） | colcon + ros2 launch（待 ROS 端移植） |

**对 ROS 端 ROS2 移植的要求**：话题名、消息字段、device_id 编码、模块确认握手语义保持与本文档一致（即与 ROS1 现网一致）；若必须调整，先改本文档并同步前后端，再动代码。移植出可跑分支后，后端切 `ROS_VERSION=2` 联调一次即可验证 `profile.py` 中的 ROS2 预设。

> **2026-11-20 现状**：仓库中的 `ros2_robot_control_backend/` 是 rclpy 迁移副本（`hardware_node.py` 已用 rclpy 重写，但部分脚本与 launch 仍保留 ROS1 写法/旧模块引用），**未作为现网运行入口**。现场仍使用 `robot_control_backend/`（catkin + roslaunch，ROS1 Noetic）；后端 ROS2 预设已存在于 `profile.py`，切换前需先完成该目录的联调。
