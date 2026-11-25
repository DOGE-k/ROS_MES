# 后端与 ROS 接口对接状态清单

原现状核查日期 2026-11-13（2026-11-20 按最新 ROS 源码复核）；2026-11-19 的迁移对照、隔离范围及新增独立消息模块见第 7 节。新模块仅离线验证，未接运行入口，不更新历史真机验证结论。维护范围：前后端视角的接入状态、证据和缺口。本清单不是 ROS 协议定义，不替代根 `docs/` 的[三轴版 V2.1 共享契约](../../docs/ROS_MES_前后端ROS接口清单_三轴版_V2.1.md)。前后端任务入口见 [AGENTS.md](../AGENTS.md)，HTTP/WS 字段见[接口文档](ROS_MES_前后端接口字段文档.md)，最终验证结果由[改动记录](ROS_MES_前后端改动记录.md)按日期维护。

## 1. 状态与证据口径

- **已定义**：仓库存在消息/话题或双方约定，不等于源码实现、现场部署或设备已支持。
- **ROS 源码已实现**：仅指当前仓库有发布、订阅、转换或 CAN 解析路径；不代表相同版本正在现场运行。
- **下位机支持待确认**：未审查对应固件源码/版本，或缺少同版本设备证据。ROS 解析器、模拟器、协议文字不能证明固件已实现，不能把未知写成“未实现”。
- **后端已接入 / 前端已使用**：分别看实际传输、归一化、页面分支；只有 API 封装或消息定义不算页面已使用。
- **模拟验证**与**真机验证**分开记录。本次改动默认不自动操作设备；历史报告保留其日期、版本和测试方式，不能提升为当前版本验收。
- 本次自动检查结果见第 6 节；生产构建及隔离浏览器结果见改动记录的完成条目，不用软件替身结果宣称真机通过。

证据路径均相对本文件位置。优先级 P0=可能误认控制结果或串目标，P1=必要联调信息，P2=后续能力；登记优先级不代表本次已经立项实施。

## 2. 对外下行及测试接口

| 接口/用途 | ROS 话题与消息 | ROS 源码实现状态 | 下位机支持 | 后端接入 | 前端使用 | 证据与缺口 | 优先级/后续条件 |
|---|---|---|---|---|---|---|---|
| GET/PATCH `/api/control/debug-settings`，页面选择连接 | 不新增 ROS 消息，仅配置后端传输 | ROS 节点未改 | 不适用 | 持久化模式/地址/版本及微调发送前检查开关，操作中拒绝切换；真实/模拟联锁分离 | 个人中心调试设置及急停遮罩共用面板，逐项自动保存，提供微调发送前检查开关及图纸 skip/mock/real 选择 | [运行配置](../ros_mes_hou/app/ros/runtime_settings.py)、[模拟适配](../ros_mes_hou/app/ros/mock_client.py)、[页面面板](../ros_mes_front/src/components/Main/UserManage/RosConnectionSettings.vue)；首次默认真实，不自动降级 | 已通过隔离验证，真实地址由现场填写 |
| `POST /api/module/`，逐台确认机械臂 | `/control/module_cmd`、成功/失败回执，`IntCmd` | `module_confirme_node.py` 有 UID/组号/臂位双确认及可配置状态复核 | 当前固件会话绑定的实际支持待确认 | 构造显式 SEG/arm，逐项等待匹配回执，失败停止后续项；返回 `data.seg` | 微调初次配置使用，调试模式也必须确认 | [模块端点](../ros_mes_hou/app/api/endpoints/module.py)、[网关](../ros_mes_hou/app/ros/rosbridge.py)、[ROS 节点](../../robot_control_backend/scripts/module_confirme_node.py)；模拟握手不证明设备绑定 | P0；保留兼容；现场核对固件版本和绑定状态 |
| `GET /api/control/session`、`POST /api/control/session/{id}/resume`、`{id}/close`，微调会话登记与续接 | 不新增 ROS 消息；续接**不发布** `/control/module_cmd` | 会话表 `(seg, arm) → uid56` 只在 `module_confirme_node` 内存中，节点重启或机械臂断电即失效，无对外查询入口 | 握手成功后登记，按连接版本、保持时长及新握手抢占作废；续接只读记录并滑动有效期 | 个人中心开关、模块管理页续接卡片、微调页“已续接会话 · 未重新握手”标识 | [会话管理](../ros_mes_hou/app/ros/control_session.py)、[控制端点](../ros_mes_hou/app/api/endpoints/control.py)、[微调页](../ros_mes_front/src/components/Main/ModulePage/FineTuningPage.vue)；续接**未经设备复核**，页面不写成绑定已确认 | P1；若 ROS 侧提供只读绑定查询，可把状态从“按记录恢复”升级为“已复核” |
| `POST /api/control/stop`、`GET /api/control/stop/holds`，局部停（模块停/单轴停） | `/arm/cmd_vel` 直发：`position=[0x08, module_id]`（device_id=0）与 `[0x0C, 1]`（device_id=轴号） | `hardware_node.py` 已实现 `0x08` 模块停与 `0x0C` 单轴停的处理与 SEG 动态换算；`softstop_node.py` 无模块停订阅，故本侧直发同话题 | 固件对 `0x08`/`0x0C` 是否锁存、如何恢复**待确认**；协议只有全局 `0x04` 解除 | 落 `control_stop_holds` 按 scope 拦截下发，命中在途批次停止后续下发并转 `uncertain`；发送失败保留锁 | 微调页「停本模块」与每轴「停」、局部停横幅与清除入口；侧栏长按仍是全局急停 | [局部停管理](../ros_mes_hou/app/ros/stop_holds.py)、[下发通道](../ros_mes_hou/app/ros/rosbridge.py)、[控制端点](../ros_mes_hou/app/api/endpoints/control.py)、[微调页](../ros_mes_front/src/components/Main/ModulePage/FineTuningPage.vue)；清除记录**不发指令**，恢复运动需重新下发 | P0；需现场确认固件锁存行为与多模块并行时“只解除某模块”的可行性 |
| `POST /api/control/finetuning/batches`，三轴统一确认 | `/control/adjust_rotation_cmd`、`adjust_swing_cmd`、`adjust_telescopic_cmd`；既有三轴消息 | 三轴节点有微调转发、基准/软限位处理；本次未改 ROS | 实际运动、单位、状态/到位事件支持待确认 | 持久化幂等及物理目标锁，顺序发送；观测到运行、目标到位及空闲才推进；异常保留待核实 | 主微调页输入本次相对增量，图纸模式主反馈采用静止后固定基准，无图纸模式采用动作起点；批次到位提示使用单次增量 | [批次管理器](../ros_mes_hou/app/ros/finetuning_batch.py)、[控制端点](../ros_mes_hou/app/api/endpoints/control.py)、[微调页](../ros_mes_front/src/components/Main/ModulePage/FineTuningPage.vue)；MES 请求号不是设备回显号 | P0；前后端模拟通过，现场需验证反馈、单位、时序及独占条件 |
| `POST /api/control/finetuning`，兼容单轴增量 | 同上 | 同上 | 待确认 | 保留发送语义，不等待完成；检查轴/参数/臂一致及批次锁 | 主微调页已改用批次接口；旧调用仍兼容 | [消息构造](../ros_mes_hou/app/ros/rosbridge.py)；发送≠接受≠到位 | P0；不把旧接口当作批次完成依据，不自动重发 |
| `GET /api/drawing/?for_tuning=true`、`POST /api/coordination/send`，图纸选择/路径及三视图 | `/frontend_pointcloud_topic`，`std_msgs/String`；选择列表不发送 ROS | `data_process_node.py` 有文件处理和视图服务；后续点云/逆解为 ROS 内部链路 | 本接口本身不证明后续轴运动；下位机执行待确认 | mock 可返回内置选择项并模拟下发/视图，不写正式图纸表；real 校验正式图纸，skip 拒绝下发及视图；版本变化拒绝旧请求/视图 | 三种图纸处理互斥；图纸下发后逐臂连续有效静止 10 秒锁固定基准，重发图纸重新观测全部已确认臂；内置模拟图纸保存来源及 null 图纸编号 | [图纸端点](../ros_mes_hou/app/api/endpoints/drawing.py)、[协调端点](../ros_mes_hou/app/api/endpoints/coordination.py)、[ROS 图纸节点](../../robot_control_backend/scripts/data_process_node.py)；模拟预览不证明点云处理，真实视图可取不证明运动完成 | P1；真实流程需图纸可见、正确 ROS/视图地址及真实急停 |
| `POST /api/control/emergency_stop`，急停发送 | `/control/softstop` → `/arm/cmd_vel`，`IntCmd` | `softstop_node.py` 有转发，硬件节点有 CAN 下发路径 | 当前固件急停及解除状态待现场确认 | 独立发送路径保留，先持久化联锁并停止批次后续下发 | 侧栏长按急停，删除五秒自动恢复，发送结果不明保留提示 | [急停端点](../ros_mes_hou/app/api/endpoints/control.py)、[侧栏](../ros_mes_front/src/components/Main/AsidePage.vue)、[ROS 转发](../../robot_control_backend/scripts/softstop_node.py)；发送成功不是已停证据 | P0；当前不宣称设备停止确认 |
| `POST /api/control/emergency_stop/release`，解除发送；GET `/api/control/emergency_stop/status`，MES 联锁查询 | `/control/softstop_release` → `/arm/cmd_vel`，既有 `IntCmd`；查询只读 MES 数据库 | ROS 有独立解除转发 | 待确认 | 记录解除发送状态与联锁版本，不恢复旧批次；模拟解除不清除真实联锁 | 侧栏已实际调用；历史/轮询/刷新仅持续提示，全屏由长按或手动查看打开且可返回页面保留状态；真实发送成功仍待确认，模拟解除成功可关闭 | 同上；恢复提示不发送新的急停，解除急停与轴故障复位不同，状态查询不是设备实测 | P0；软件链路模拟通过，实际解除待现场确认 |
| `POST /api/control/emergency_stop/manual_release`，人工解除 MES 急停记录 | MES 业务状态更新 | 操作由前后端完成 | 现场处理结果由操作员确认 | 按当前环境、连接版本及急停版本清除记录，保留中断批次核实流程，模拟环境同步清除模拟锁存 | 急停全屏提供“人工解除急停”，清除成功后关闭全屏并恢复状态提示 | [控制端点](../ros_mes_hou/app/api/endpoints/control.py)、[联锁记录](../ros_mes_hou/app/ros/finetuning_batch.py)、[侧栏](../ros_mes_front/src/components/Main/AsidePage.vue)。自动检查及页面验证见改动记录 2026-11-11 条目 | 人工确认清除属于 MES 业务流程，设备状态以现场确认及后续实时检查为准 |
| `GET /api/ros/send_ros`，通用测试消息 | `/web_cmd`，`std_msgs/String` | 测试通道，具体接收/业务动作需按 ROS 节点核查 | 不适用，不证明硬件动作 | 两版适配统一经 rosbridge 发布 | `RosTestPage.vue` 使用 | [测试端点](../ros_mes_hou/app/api/endpoints/ros.py)、[测试页](../ros_mes_front/src/components/Main/RosTestPage.vue)；页面历史“模拟”文案不等于 API 固定使用模拟 | P2；区分环境模拟和真实通道 |
| `GET /api/ros/get_ros_status`，订阅状态快照 | `/robot_status`，状态消息 | 发布者有效输出/现场部署待确认 | 不适用 | 常驻订阅器维护连接与最近状态 | 测试页使用 | [profile](../ros_mes_hou/app/ros/profile.py)、[状态订阅器](../ros_mes_hou/app/ros/rosbridge.py)；`ros_ready` 不证明机械臂在线，默认电量等不能作设备实测 | P1；需真实发布者和可辨识数据来源 |
| 串口测试、硬件实时状态 HTTP 工具 | 子进程 `serial_test_node.py` / `hardware_node.py`，非独立 ROS 对外话题契约 | 脚本依赖运行环境/硬件；存在文件不保证输出符合接口模型 | 待确认 | `app/ros/base.py` 有超时子进程工具 | 顶栏使用串口测试；实时硬件状态未发现页面消费 | [基类工具](../ros_mes_hou/app/ros/base.py)、[控制端点](../ros_mes_hou/app/api/endpoints/control.py)；未在本次自动启动硬件脚本 | P2；隔离设计及硬件环境就绪后验证 |

## 3. 已订阅的对外反馈

以下 13 路由 [profile](../ros_mes_hou/app/ros/profile.py)、[反馈流](../ros_mes_hou/app/ros/rosbridge.py)和[归一化](../ros_mes_hou/app/ros/normalizer.py)接入。新增五类事件由后端批次管理器消费，前端通过批次查询显示结果；下位机支持一列区分“ROS/固件方口述或仿真验证”与“真机实测”，未标真机验证的一律按待确认处理。

> 2026-11-14 新增 `axis_status_aggregator.py` 并默认随 `ros_robot.launch` 启动：绑定 SEG/ARM 后按 5Hz 推导发布三轴 `/hardware/axis_status`，空闲时在三条 `/hardware/*_feedback` 话题上按 2Hz 补发最后一次真实位置；停止命令、急停解除、人工校零后立即置空闲，解除急停与校零会恢复 `base_valid`，故障/限位/急停使其失效（停止命令本身不恢复）。`sim_axis_status_node.py` 是联调替代（位置恒 0、`base_valid` 恒 1、`module_id=SEG`），默认不启动且不能与聚合节点同时发布。聚合状态与补发位置均来自指令、事件和缓存，不等于设备实测运动。

| 话题/消息 | 用途与编号语义 | ROS 源码实现状态 | 下位机支持 | 后端接入 | 前端使用 | 验证证据/缺口 | 优先级及后续条件 |
|---|---|---|---|---|---|---|---|
| `/hardware/rotation_feedback` / `RotationCmd` | 旋转角度，`module_id` 为 CAN SEG | `feedback_node.py` 换算 CAN 位置并透传 SEG | 待确认 | 已转发；本次补有效性标记 | 主微调页按 SEG/臂核验及逐项时效消费，原始反馈按图纸固定基准或动作起点换算相对量 | [反馈节点](../../robot_control_backend/scripts/feedback_node.py)；需与当前固件单位和现场版本核对 | P0；未归属或无效样本不更新实际值 |
| `/hardware/swing_feedback` / `SwingCmd` | 摆动角度，CAN SEG | 同上 | 待确认 | 同上 | 同上 | 同上；不能按轴号单独跨模块匹配 | P0；同上 |
| `/hardware/telescope_feedback` / `TelescopicCmd` | 实测长度 mm，CAN SEG | ROS 内部把 CAN 0.01mm 换算为 mm | 待确认 | 原样传 mm；本次补有效性标记 | 主微调页按 mm 消费并扣除该模式有效基准，显示相对移动量 | [伸缩消息](../../robot_control_backend/msg/TelescopicCmd.msg)、反馈节点；固件单位需同版本核实 | P0；保留明确单位与基准依赖 |
| `/hardware/sensor_feedback` / `SensorCmd` | 瞬时压力，CAN SEG、臂级编号 | 反馈节点转换及发布 | 待确认 | 已转发 | 主微调页消费；本次改为独立等待/时效状态 | 不能因为轴已反馈就把默认压力 0 显示为实测 | P0；压力实际频率、标定单位待确认 |
| `/hardware/imu_angles` / `TuoLuoYi` | 姿态/坐标分量，沿硬件链路透传 CAN SEG | `tuo_luo_yi.py` 分模块/臂维护并发布 | 待确认 | 已转发；本次分量独立有效性 | 主微调页消费；本次分量独立时效 | [IMU 节点](../../robot_control_backend/scripts/tuo_luo_yi.py)；缺失/非法分量不能补成零 | P0；现场标定、精度与坐标语义另行验证 |
| `/hardware/pressure_avg` / `SensorCmd` | 采样窗口均值，`module_id` 来自触发上下文的业务编号 | `imu_average_calculator_node.py` 已发布，但存在异臂样本进入同一窗口的路径 | 待确认 | 已转发 `pressure_average`，不能一律当 SEG | **前端未展示** | [均值节点](../../robot_control_backend/scripts/imu_average_calculator_node.py)；只提示来源问题，本次不修改 ROS 或把界面接通当作均值正确 | P2；ROS 侧先核实采样归属、触发和窗口 |
| `/hardware/vacuum_loss` / `VacuumLoss` | 失压事件，硬件 CAN SEG 与臂级编号 | 硬件节点有事件解析与发布 | 待确认 | 转发事件及压力/阈值字段；所属臂事件中止批次后续下发 | 通过批次待核实原因提示；未新增独立告警页 | [批次管理器](../ros_mes_hou/app/ros/finetuning_batch.py)；现场压力单位和防误报条件待核对 | P1；模拟中止路径已接入，设备保护效果未验证 |
| `/hardware/cmd_ack` / `CmdAck` | 接受/拒绝事件；软件回执用业务号，CAN 回执用 SEG | 三轴节点软件拒绝、硬件节点 CAN ACK及回零软件拒绝均可发布到此话题 | 各类 ACK 的实际发送支持待确认 | 转发 result/detail/raw 及保守归属元数据；可能属于当前臂的非零拒绝保守中止，接受不推进 | 可归属及归属待确认事件提示，批次另行显示中止结果 | [CmdAck](../../robot_control_backend/msg/CmdAck.msg)、[硬件节点](../../robot_control_backend/scripts/hardware_node.py)；没有发布者来源或请求 ID | P0；不能关联为某次请求最终结果 |
| `/hardware/axis_status` / `AxisStatus` | SEG、轴号、状态字/运行状态/基准有效性 | 硬件节点解析纯转发；2026-11-14 起 `axis_status_aggregator.py` 在绑定 SEG/ARM 后按 5Hz 推导发布状态、空闲按 2Hz 补发缓存位置 | 固件周期上报由 ROS 侧口述确认；聚合节点可补全链路，但状态非设备实测，MES 真机链路待复核 | 新鲜有效空闲用于发送前检查；新 RUN 及后续空闲用于批次完成判定。2026-11-14 起发送前 5 秒内一帧都收不到即快速失败，消息含话题名与已收帧统计，不再空等 60 秒（不放宽放行条件） | 批次进度间接消费，未增加独立状态仪表 | [归一化](../ros_mes_hou/app/ros/normalizer.py)、[聚合节点](../../robot_control_backend/scripts/axis_status_aggregator.py)、批次管理器；缺字段不补默认值；[实测报告](../../docs/机械臂物理状态实测报告_2026-11-07.md) 的 CAN 层静默结论与 ROS 侧反馈不一致（疑为固件版本差异），需真机 `candump`/`rostopic hz` 复核 | P0；聚合状态只能保证链路推进，不能证明设备真的运动；真机复核前短动作漏 RUN 时仍按停止后续发送处理 |
| `/hardware/arrive_notification` / `ArriveNotification` | SEG、轴号、原始位置/误差及有效标志 | 硬件节点有 CAN 事件解析 | 待确认 | 同轴发送后检查目标、误差和有效标志，配合空闲判定；整批从未收到轴状态帧时，可与 `stop_reason=1` 组合作为完成证据（步骤记录 `completion_evidence=arrive_stop`、`run_observed=false`） | 通过批次查询显示完成/待核实；另在「到位 / 停止事件」卡片显示原始字段，并用 `angle` 补全该轴实测值 | 消息无设备请求号；伸缩原始单位等需按现场版本核实 | P0；软件观测完成不等于固件级逐请求关联 |
| `/hardware/stop_notification` / `StopNotification` | SEG、轴号、停止原因/输出 | 硬件节点有解析 | 待确认 | 非正常到位停止中止后续下发；正常停止不单独替代到位判定，仅在无轴状态帧时与到位事件组合 | 通过批次原因提示；另在「到位 / 停止事件」卡片显示停止原因 | `StopReason`、作用域和现场版本待核实 | P0；未由发送结果推断停机 |
| `/hardware/axis_fault` / `AxisFault` | SEG、轴号、故障字段 | 消息及解析存在；协议说明记载部分固件判断关闭 | 待确认 | 所属臂故障事件中止后续下发 | 通过批次原因提示；另在「设备告警事件」卡片显示 `fault_bits`（十六进制+已定义位）/`local_action`/`detail`/`duration_ms`，带 2 秒同轴同位去重，不依赖当前确认臂 | 不凭消息定义推断实际报告种类；位定义仅用仓库已有依据（bit3 限位/bit4 急停/bit5、bit7 故障），其余显示 `bit N` | P0；现场固件实际支持待核实 |
| `/hardware/limit_event` / `LimitEvent` | SEG、轴号、限位类型/输出 | 硬件节点有解析 | 待确认 | 所属臂限位事件中止后续下发 | 通过批次原因提示；另在「设备告警事件」卡片显示限位类型与输出，按"轴+限位类型"2 秒去重 | 软件拒绝、物理限位和锁存故障仍需区分；`limit_type` 枚举未在仓库定义，仅 1/2 按需求表标注上行/下行 | P0；不自动复位或重发 |
| `/hardware/can_fault` / `std_msgs/String` | CAN 总线状态，`data` 内嵌 JSON | **后端本次新增订阅与归一化**；ROS 侧发布实现与字段名待确认 | 待确认 | 归一化为 `can_fault`，`module_id_space=system`，解析 `state`/`message`/`detail`/`channel`/`timestamp`；解析失败保留 None 不猜字段 | 页面顶部常驻横幅，`state=ok` 自动消失，5 秒内重发只刷新不追加 | `???` 字段名按需求表实现，需 ROS 侧确认；`state` 缺失按 `error` 处理 | P1；总线级故障，影响所有轴反馈 |

## 4. 回执、时间和状态边界

兼容单轴接口的 `sent` 是 WebSocket 写出证据，`confirmed=null/confirmation_status=not_requested` 表示未等待设备确认。批次接口的 HTTP 202 只表示登记；`completed` 表示在目标独占条件下观测到发送后的运行、目标到位及空闲组合，仍受无设备请求序号的关联边界限制。模块确认通过专用回执核验后保留 `confirmed=true`；不能用普通微调的语义更改破坏该分支。急停/解除仍使用独立兼容下行路径。

CmdAck 同一话题混合不同编号空间，`header` 目前也没有可靠的发布者来源标记。`raw` 能保存已有信息，不能恢复消息中不存在的来源或请求编号。即便模块和轴唯一可归属，迟到 ACK 与同轴连续增量命令仍不能可靠逐条关联；接受事件不等于运动完成，没有回执也不等于拒绝。

本次归属规则只增加后端 WebSocket 元数据，不改 ROS 消息：正业务号保留为候选；原号在 0～14 时再按显式 `ROS_MODULE_SEG_MAP` 收集 SEG 对应候选。配置无效或 SEG 无映射为 unknown，多候选为 ambiguous，仅无未决解释且唯一时为 resolved；保留原号和 raw。普通遥测、压力均值、混合回执不能共用一个无条件转换规则。

前端按各轴、压力和 IMU 分量的有效样本接收时间判断过期，默认三轴 60 秒、压力 10 秒、IMU 5 秒。恢复的缓存显示为历史值，反馈连接断开时标记过期。只有有效样本更新读数和接收时间，数值 0 是有效反馈。

微调输入及下发使用本次相对增量，后端以发令前 `start_position` 计算单次动作到位增量 `observed_delta` 与偏差。普通图纸模式主反馈以图纸运动结束后连续有效静止 10 秒锁定的位置为固定基准，`reference_source="drawing_settled"`，后续微调按该固定值计算 `current`。无图纸调试模式沿动作起点口径，来源为 `command_start`。新配置保存 `position_mode="relative"`、`reference_source`、`initial/reference_position`、相对 `current` 与 `raw_current`，旧请求省略来源时默认 `command_start`。历史批次查询继续恢复单次动作相对结果。字段和恢复规则见[接口文档 2.4.3 节](ROS_MES_前后端接口字段文档.md)。

2026-11-14 记录语义对齐：单个轴的一次下发涉及三个不同的量，接口与页面统一叫「初始值（`start_position`）→ 微调量（`position`/`requested_delta`）→ 应到（`expected_position`）」，设备侧回来的是「到位实测（`observed_angle`）」，两者之差才是「偏差（`deviation`）」。`deviation` 的参照系固定为本次 `start_position`，不用图纸固定基准——连续批次各自收敛是正常现象，用基准算会假报超差。固件 `pos_error/100` 单独记为 `position_error`，与 MES 自算偏差来源不同，两者都保留。记录表 `new_value` 旧实现存的是 `old_value + position` 却被当作实测值读取，现改为存应到值并新增 `requested_delta`、`observed_position`、`observed_delta`、`deviation`、`position_error`、`outcome`、`outcome_by`、`outcome_at`。字段对照见[接口文档 2.4.4 节](ROS_MES_前后端接口字段文档.md)。

运动结论由人工判断补齐：批次结束时收到到位写 `moved`，没有到位证据（超时、中断、发令前被拦、反馈断线）写 `unknown` 表示待核实；操作员看现场确认没动时通过 `POST /api/control/finetuning/batches/{batch_id}/axes/{parameter_name}/outcome` 标为 `no_motion`，可撤销。该接口只写判定，不发送运动指令、不改实测字段。选择标记而不是删除记录行，是因为记录行是“CAN 帧已发出”的证据，删掉后无法区分“没发”和“发了没动”。

图纸基准由前端按连接版本、SEG、Unit_ID 与图纸 generation 分臂观测，图纸 POST 前开始收样，全部相关 POST 成功后可锁定。先有位置变化或有效 RUN，再由三轴连续有效稳定 10 秒提供静止证据，最大采样间隔 3 秒、窗口位置范围暂按 0.01°/0.01mm。锁定前断链、缺样或坏样重新计时。真实 ROS 图纸消息仅有文件路径，同一会话重发图纸时全部已确认臂重新观测，下发成功后各臂图纸关联及共享默认图纸同步为本次图纸。整次配置操作核验 generation 与连接版本，仅接纳本轮有效模块确认及图纸响应，观测状态仅由当前反馈连接更新。开启既有会话保持后，固定值与观测状态进入本机快照，高频反馈下每约 500ms 保存，`pagehide` 立即保存。已锁定值刷新续接可保留，未锁定状态刷新后重新观察，跨端缺少快照时基准未知。采集在微调页面运行期间进行。现场原始反馈跳值及真机基准效果待核实。

三轴配置快照在 `config_json.devices[]` 写入 `requested_delta`，保存每轴最近一次进入下发流程的指令增量。保存时相对实测值取 `current`，批次到位实测和偏差可查 `progress_json`。 输入框草稿 `adjust` 仅用于页面输入和会话续接。

2026-11-14 人工校零链路已接入：前端点亮「校准」并保存时，后端向 `/control/axis_zero` 发布 `IntCmd(device_id=0, position=[arm])`，再保存校零配置；普通保存不发布，发布失败返回 503 且不落库。ROS 旋转、摆动、伸缩节点及状态聚合节点均按臂号复位对应软件基准/缓存，不影响其他臂。该流程只同步 ROS 软件基准，不产生 CAN 运动或新的设备校零回执；源码和模拟回调已验证，现场真机效果待确认。

批次记录持久化于 MES 数据库，以物理 SEG+arm 锁定目标并拒绝重复请求；模拟锁额外带 mock 前缀。查询/刷新不会再次下发。前端批次详情和 ACK 提示按臂保存，切臂不沿用另一臂记录，切回恢复本会话内记录；新会话清除旧臂缓存，旧查询迟到响应不能覆盖新批次。已尝试发送但缺少完成证据时保留 `uncertain`，真实操作需现场核实，模拟操作核对模拟记录后关闭；后端重启均不恢复旧动作。每批保存模式/地址/版本快照，模拟反馈不能驱动真实批次推进。此机制只支持单后端工作进程，不能阻止 ROS 内部或外部控制器并行发令，真机使用前必须明确目标独占。后端接收时刻只用于软件新鲜度，不证明设备时钟同步或端到端时延。

微调发送前检查由 `finetuning_preflight_enabled` 控制，默认 true，旧保存配置缺少字段时补默认值。入口为“个人中心 → 调试设置 → ROS 通信与微调 → 微调下发前检查”，自动保存并持久化，开关变更沿用连接版本及会话失效流程，需重新确认机械臂。批次冻结开关快照。

开关开启时，每轴发送前等待实时有效轴状态与位置，上限 60 秒。首轴的订阅就绪与状态准备共用一个窗口，后续轴重新建立准备窗口。关闭时跳过订阅就绪及发送前状态准备，直接进入当前轴相对增量发送。缺少有效同轴起点的批次起点、预期位置、实测增量和偏差为 null，原始反馈可按有效样本保存。页面当前相对值按所选模式的有效基准计算。

发送后完成确认按运行、有效到位事件和空闲组合推进，等待上限 60 秒。缺少完成证据时进入 `uncertain`，暂停后续轴并保留目标锁。字段及阶段处理见[接口文档 2.4.1 节](ROS_MES_前后端接口字段文档.md)。

## 5. 本次只登记、不扩展的能力

下表只收录可能对 MES 有意义的能力，**不是把所有 ROS 内部话题列为后端缺失接口**。模块握手中的 UID、组号/臂位确认、绑定及状态复核等内部消息由 ROS 节点使用，不要求前后端分别暴露 API。

| 能力/相关话题与消息 | ROS 仓库证据 | 下位机支持 | 后端/前端现状 | 后续条件 |
|---|---|---|---|---|
| 查询当前模块绑定（只读） | `hardware_node` 有状态查询桥接（CAN `0x00000020`），`module_confirme_node` 仅在握手流程内按 token 复核 `module_state` bit0/bit1 | 待确认 | MES 无独立查询入口，续接只能按自身记录恢复 | 需 ROS 侧新增只读查询命令与回执定义，本侧不改 `robot_control_backend` |
| 回零 `/control/home_cmd` / `IntCmd`、`/hardware/home_status` / `HomeStatus` | 硬件节点有处理且有 `home_supported` 限制；可发 `ack_msg=4` 软件拒绝 | 待确认 | MES 未提供本次回零操作入口或状态消费 | 先核实真实固件能力及操作条件 |
| 单轴故障复位 | 共享保护说明给出 CAN 复位帧 | 待确认 | 未发现已建立的独立 MES→ROS 复位契约 | 双方先确认对外 ROS 接口，不能直接新增 CAN 指令 |
| 独立模块状态查询 `/control/module_status_query` / `IntCmd`、`/hardware/module_status` / `ModuleStatus` | 硬件节点实现；模块确认节点内部用于状态复核；2026-11-20 起 `control_node` 用应答中的 `exist_mask` bit0~2 过滤在线轴，只等待在线轴到位 | 待确认 | MES 无独立查询入口；ROS 内部已用于时序等待集合 | 明确独立查询需求、token匹配及状态字段 |
| 图纸要求的目标角（页面“图纸要求值”） | 目标角写在共享库 `Calculation` 表（V2.0 列名）：`calculation_node` 写 `Coordinates={unit: {alpha,…}}`、`Axis_result={unit: beta}`（`Unit_id=0`），`kinematics_node` 写 `Coordinates={unit: [j1,j2,j3_cm]}`、`Axis_result={axis: 增量}`（`Unit_ID=unit`）；两节点 `DB_PATH` 都指向仓库根 `ros_database.db` | 不适用 | 前端按 C 方案只显示“实际到位”（锁定图纸基准 + 实际位置），不显示图纸要求值 | 该表由两节点按不同键空间写入、无请求号/批次号，且 `kinematics_node` 对未参与该模块的臂用 `target_j*=0.0` 写 `[0,0,0]` 占位——真 0° 目标与占位不可分辨；当前开发库该表 0 行。MES 直接读它会给页面编出假目标，故不读。要显示需 ROS 侧提供带“参与标志”和请求关联的目标角话题，本侧不改共享协议去猜 |
| 固件级完整指令追踪 | 当前消息无可靠请求关联标识 | 待确认 | 已有 MES 批次幂等及观测进度，尚不能精确匹配固件逐请求接受→执行→停止/到位 | 需双方明确设备关联能力；本次不改 ROS/固件协议 |
| 大屏 `/api/ws/ws/robot_status` 的底层数据源 | 后端端点存在，`web_data_node.py` 历史代码整段注释 | 不适用/待有效数据源 | 有受 token 保护的转发入口，不能证明大屏已有实时流 | ROS 数据源与实际页面订阅应单独核查 |

## 6. 验证与外部依赖

- 2026-11-13 图纸固定基准流程完成软件验证，前端微调相关 155/155 项、图纸 12/12 项、全后端 203/203 项通过，类型检查与生产构建通过。新增场景覆盖多臂、HTTP 期间采样、连续微调累计相对值、断链及图纸失败、迟到响应与固定/未固定快照恢复。详细结果见[改动记录](ROS_MES_前后端改动记录.md)。固定基准来自本页观测，真机运动与连续反馈效果待现场确认。
- 2026-11-13 相对微调改动完成软件验证，前端微调相关 111/111 项、图纸 12/12 项、全后端 183/183 项通过，类型检查和生产构建通过。本机后端重启后 HTTP 200，新配置字段 schema 已加载，前端 5173 开发服务运行。详细新增场景与执行环境见[改动记录 2026-11-13 条目](ROS_MES_前后端改动记录.md)。验证采用内存数据库与测试替身，真机相对运动及原始反馈跳值来源待现场确认。
- 本轮最终自动检查通过：前端微调/急停/请求/连接配置 68/68 项、图纸 12/12 项、后端 129/129 项，类型检查及生产构建通过，仅有现有资源包体积提示。新增空正式图纸库模拟、三种图纸处理互斥、历史急停不自动全屏、来源与版本校验、切臂/新会话及迟到查询/ACK 回归；详见改动记录 2026-11-07 完成条目。
- 本轮隔离浏览器完整流程通过：真实登录后空库内置图纸双臂确认、三轴草稿不立即下发、一次确认顺序完成及保存 null 图纸编号/内置来源、不使用图纸保存、模拟急停刷新提示及解除、真实空库仍要求导入、切臂记录隔离及切回恢复。全程正式图纸表为零条，共两个完成的模拟批次；急停/解除 POST 各一次且仅由主动操作产生，真实历史 stop_unknown/generation=8 保留，模拟解除后为 clear。未连接真实 ROS/串口，未写运行库业务记录。
- 临时隔离测试服务、脚本及 SQLite 已清理；本地前后端 5173/8000 正常保留，新接口字段可读取。代码尚未提交或上传 GitHub；模拟验证不能证明现场 ROS/固件/设备行为。
- 上次调试功能已有实际组件/Pinia 回归、配置保存的内存数据库测试及隔离浏览器验证，证明范围限前后端软件路径；不证明 rosbridge、ROS 或 CAN/设备行为。
- [历史全流程报告](../../docs/ROS_MES_全流程测试报告.md)为 2026-10-25 模拟下位机验证；[真机 CAN 报告](../../docs/can_real_device_debug_report.md)是指定环境的问题记录。两者保留原结论和环境，不能自动套用于当前提交和现场固件。
- 待外部确认：现场 ROS/固件版本、各类 ACK/状态/到位真实支持、到位原始单位及容差、短动作 RUN 的可观测性、压力标定与反馈频率、IMU 精度/坐标、断电重绑会话状态、独占控制条件。未取得直接证据前均为待确认；压力均值异臂采样路径交由 ROS 方核实，本侧未修改节点。
- 已发现配置差异：ROS 本体 `rob_arm.env` 的图纸话题为 `/frontend_pointcloud_topic`，共享部署模板 `deploy/config/rob_arm.env` 仍有 `/control` 前缀。仅记录，未擅改 ROS 配置或共享协议；实际部署采用哪份配置需核查。

<a id="ros2-msg-migration-preparation"></a>

## 7. ROS2 新消息契约迁移准备（2026-11-19）

### 7.1 依据、现状与保留范围

- 用户要求：已测试的 ROS1 继续使用，后续 ROS2 逐步适配新消息；新数据库由 ROS 方设计，MES 等其确定后再对接。首轮已交付新旧消息对照及隔离范围；同日后续获授权新增独立消息模块和离线验证，实际完成范围见 7.7，数据库和运行入口仍不变。
- 新契约依据：用户提供的《msg消息格式设计.md》，本机原件为 `C:\Users\DOGE\Downloads\msg消息格式设计.md`；2026-11-19 读取，SHA256 为 `882E808348C712C7C4A7A04E38E1D526BCEF87307799939F93E96BC317CA7E8A`。下文引用其章节号，只登记 MES 适配差异，不复制一套完整协议。ROS 方最终需提供仓库内可追踪版本的 `.msg`、话题与对接入口；下载目录原件不是团队共享来源。
- 当前源码参照：分支 `main`，HEAD `a2e331d35a46f0c2f43bf1dbad4ff23a0811ab81`。开始时已有前端 `.env.development` 未提交修改和根目录 `ros_database.db.bak-20261114`，本轮保留原样。该提交是源码参照，不直接认定为用户已测或现场部署的版本；现场后端、ROS 包、固件版本对应关系仍需在后续联调前记录。
- 当前实现依据：[消息构造与传输](../ros_mes_hou/app/ros/rosbridge.py)、[反馈解释](../ros_mes_hou/app/ros/normalizer.py)、[版本配置](../ros_mes_hou/app/ros/profile.py)及只读核查的 `robot_control_backend/msg/`、相关节点。源码、注释、新设计和现场行为分别标识，不互相代替。
- 当前 `ROS_VERSION` 只选择 ROS 版本对应的 profile/适配器；两版仍共享消息构造及反馈解释。后续应区分“ROS 运行版本”和“消息契约版本”，但本轮不新增配置项或默认值。按当前迁移安排，ROS1 保留旧契约，后续 ROS2 接新契约；不按收到的字段或编号自动猜契约。
- 保留范围：现有 ROS1 消息生成、反馈解释、HTTP/WS 字段、业务编号映射、数据库读写、模拟器及前端流程。未授权全局改名、切换连接、迁库或执行设备操作。用户说明的 ROS1 已测结论予以保留，本轮只增加固定报文基线检查，未复测设备。

### 7.2 身份与编号对照

| 概念 | 当前源码口径 | 新契约确定规则 | MES 后续边界 |
|---|---|---|---|
| 消息 `module_id` | 微调、校零、模块确认发送业务模块号；常规硬件反馈为 SEG；ACK 等存在混用 | §2：统一为 CAN SEG `0～14`，不能表示业务号或坐标 | 业务编号、数据库主键和 SEG 分别表达；SEG `0` 合法，新契约拒绝 `15` 或业务号 `17` 冒充 SEG |
| 轴 `device_id` | 已使用三轴布局 `1～15` | §3/§5.1：J1=`1,4,7,10,13`，J2=`2,5,8,11,14`，J3=`3,6,9,12,15` | 编号布局保留；新校验还需核对消息类别与轴类型，不能只检查总范围 |
| 机械臂 `device_id` | 旧 Unit_ID 支持 `1～5` 或 `32/64/96/128/160`；校零消息使用 `device_id=0` | §3/§5.3：臂级实体使用 `21～25` | 业务 Unit_ID、臂位 `1～5` 和消息实体 ID 分开；不得把旧业务编码直接当新实体编号 |
| 压力/失压 `device_id` | `21～25`，按话题解释 | §5.2：压力及失压事件统一为 `31～35`，臂号为 `device_id-30` | 新解析器独立识别压力段；安全事件仍属于压力设备，事件类别由话题/消息表达 |
| IMU/姿态 `device_id` | `21～25`，与压力按话题区分 | §5.2：统一为 `36～40`，臂号为 `device_id-35` | 同一 IMU 可有原始六轴及姿态结果；不把不同测量量合并为一个通用 position |
| 系统/节点 | 当前 `Heartbeat.msg` 使用 `node_id`；MES 未接入心跳 | §5.5：心跳 `device_id=0`，CAN NODE 独立为 `node` | 节点号与实体号分离；`device_id=0` 的具体含义仍结合消息类别，不能单独据此认定绑定状态 |
| 保留号及设备身份 | 旧业务配置还含 sensor_ID 等编码 | §3：`16～20`、`26～30` 预留；实体编号在模块内使用 | 预留号不认作实体；设备归属至少结合 SEG 和实体 ID，不能把 device_id 当全系统唯一主键 |
| 模块坐标 | MES 中已有业务坐标和地址编码 | §5.3：坐标不能塞入消息 module_id | 文中提及 `ModuleAddress` 不等于新库已定稿；不据此创建字段或推定主外键 |

例：假设业务模块 `17` 显式对应 SEG `0`，第二臂的新消息身份分别为：模块 `0`、轴 `4/5/6`、机械臂 `22`、压力 `32`、IMU `37`。这只是编号换算样例，不建立新的业务映射或写入任何数据库。

### 7.3 消息与功能对照

下表话题均为当前代码入口；除新设计明确给出的路径外，不能把旧话题自动视为 ROS2 已确认话题。新契约规则属于设计输入，尚未在 MES 接入或现场验证。

| 消息/功能 | 当前 MES/ROS 源码事实 | 新设计规则与差异 | 后续处理及缺口 |
|---|---|---|---|
| `RotationCmd` / `SwingCmd` / `TelescopicCmd` 微调 | `build_fine_tuning_publish_payload()` 发三轴消息，module_id 为正业务号，position 为单次增量，frame_id 为空 | §5.1：module_id=SEG；轴号按 J1/J2/J3 细分；RotationCmd 明确 frame_id=`module_{SEG}`；旋转/摆动为度、伸缩为 mm | 独立构造新消息，保留旧生成器；其余消息的 frame_id 规则由最终定义补齐 |
| 轴位置反馈 / `Feedback` | 当前三个位置话题分别使用三轴消息，按轴号与对应话题匹配；伸缩外部反馈为 mm | §5.1 列出通用 `Feedback`，position 统一写角度 | 新 Feedback 与现有三类反馈消息的使用关系、话题及伸缩单位/倍率待确认，不能直接替换订阅类型 |
| `AxisStatus` / `ArriveNotification` / `StopNotification` / `AxisFault` / `LimitEvent` | MES 已订阅并按 SEG+轴解释状态和事件，事件不是普通 position | §5.1 保留状态、到位、停止、故障、限位字段及轴段 | 可先准备逐消息解析与字段校验；到位 angle/pos_error 覆盖伸缩轴时的单位仍待确认 |
| `CmdAck` | 当前解释器处理业务号/SEG 混用，输出候选归属、未知或歧义 | §2/§5.1：module_id 统一 SEG，保留 ack_msg/result/detail | 新解析不套旧混用推断；消息仍无逐请求关联 ID，接受不等于运动完成，不能伪造严格逐命令关联 |
| `SensorCmd` / 压力均值 | 当前瞬时压力、均值均为臂级 `21～25`；均值 module_id 按业务号处理 | §5.2：压力 ID `31～35`；§2 要求 module_id 统一 SEG；§9 对下行 cmd_type 双表达仍有待定内容 | 瞬时值可按已定规则准备；均值话题是否保留、类型/来源及归属需单独补齐，发送命令参数与测量值分别解释 |
| `VacuumLoss` | 当前按 `21～25` 归属臂，并供批次管理器消费 | §5.2：压力段 `31～35`，保留 pressure_raw/loss_threshold | 更新新协议事件归属；原始值和阈值的单位/倍率在未明确前不擅自换算 |
| `GyroFeedback` / `TuoLuoYi` | 当前 MES 订阅姿态结果，按 `21～25` 解释；未订阅原始六轴 | §5.2：两者 ID `36～40`；原始加速度 m/s²、角速度 °/s；姿态角为度、坐标 cm | 先准备新消息解析；原始六轴是否需要 MES 消费单独确定。姿态旋转角顺时针为正，旋转命令逆时针为正，不直接共用同一角度含义 |
| `IntCmd` 人工校零 | `build_axis_zero_publish_payload()` 发业务 module_id、device_id=0、position=[arm] | §5.3：`/control/axis_zero` 使用 SEG、device_id=`21～25`、position=[device_id] | 新校零消息独立构造；继续表达 ROS 软件基准复位，不将其解释为 CAN 运动或硬件校零完成 |
| `IntCmd` 局部停及全局急停/解除 | `publish_local_stop()` 模块停发 `[0x08,module_id]`，臂停展开三轴，轴停发 `[0x0C,1]`；全局急停/解除各走独立话题 | §5.3 给出 `/arm/cmd_vel` 臂级 ID `21～25`；未列全各 scope 的参数及全局两个入口 | 编号范围已定，完整停止/解除消息及范围、成功含义待 ROS 方确认；“总线不变”不能证明所有上位机入口不变 |
| MES 模块确认入口 / `IntCmd` | 当前 `/control/module_cmd` 发业务 module_id、device_id=0、position=[100,seg,arm]，按业务号匹配成功/失败回执 | §5.4 给出 UID、SEG、臂位绑定内部消息，未给出完整 MES 发起与回执契约 | 不直接用 SEG 替换旧业务号并沿用握手；入口、成功/失败、超时及结果关联待补齐 |
| `UidAnnounce` / `SegAssign` / `SegConfirm` | ROS 内部绑定协议，MES 当前不直接消费；旧 SegConfirm 臂位确认帧的 seg 占位为 `15` | §5.4：臂位确认帧 seg 占位改为 `0`；UidAnnounce 豁免 ID 三件套，但其余两表也未列齐三件套 | ROS 方落实最终 `.msg` 及例外规则；不由 MES 按总则自行补字段，不自动扩展为前端 API |
| `ModuleStatus` | 旧定义无 status/device_id，字段 arm；未绑定 seg=0xFF；ROS 确认节点解释 module_state，MES 未直接订阅 | §5.4：新增 status、device_id=0；arm→arm_slot；未绑定 seg=0；status 是绑定唯一判据 | 保留路由 module_id 与绑定 seg，不能合并；status=0 禁止运动，status=1 还需核验组号正确及其他发送前条件。新状态可供 MES 使用的入口/时效待补齐 |
| `Heartbeat` | 旧定义 `uint16 node_id`，无 device_id；mask 注释含20轴；当前硬件节点心跳发布整体被注释，MES 未订阅 | §5.5：`uint8 node`、device_id=0、mask 有效位对应15轴；文中标注下位机暂未做 | 字段增删及宽度变化以最终 `.msg` 为准；不因设计存在就显示在线或自动新增心跳功能 |
| `HomeStatus` / `Kinematics` / 图纸 | MES 未接回零和 Kinematics；现图纸路径经 std_msgs/String 下发 | §5.1 回零仍以 angle 描述；§5.3 Kinematics 目标坐标为 mm，device_id=0或21～25；图纸外部入口未重新定义 | 新消息解析可分阶段准备；不顺带新增回零/坐标控制，图纸入口与伸缩回零单位等待外部契约 |

伸缩限位单独说明：当前 `TelescopicCmd.msg` 注释为 `0～30mm`，但 `telescopic_node.py` 的节点说明及新设计为 `-10～20mm`，实际上下限直接由环境配置读取，节点按累加后的绝对位置检查。不能把旧消息注释或节点说明写成 ROS1 实际行程；应由 ROS 方明确现场配置、相对增量与绝对限位的关系。MES 本轮不调整限位。

### 7.4 运行接入隔离范围（规划，未实施）

| 当前入口/范围 | 共用或耦合点 | 后续隔离要求 |
|---|---|---|
| [ROS1 适配器](../ros_mes_hou/app/ros/ros1/__init__.py)及 `ros1/native.py` | 现有 ROS1 入口及历史 rospy 兼容 | 保留现有行为；本轮及首阶段独立消息模块不改这些文件 |
| [工厂](../ros_mes_hou/app/ros/__init__.py)、[profile](../ros_mes_hou/app/ros/profile.py)、[ROS2 适配器](../ros_mes_hou/app/ros/ros2/__init__.py) | ROS2 子类目前仅指定 profile；类型串/时间戳切换不能隔离业务语义 | 先明确运行版本与消息契约选择关系；新增消息模块暂不接工厂、启动钩子或默认配置 |
| [rosbridge.py](../ros_mes_hou/app/ros/rosbridge.py) 的 `build_*`、编号映射、`stream_feedback()` | 下发与反馈规则由两版本共用 | 保留旧函数的参数、返回值及行为；新生成器/解析器独立组织，不全局改 ID 范围或替换解释器 |
| [normalizer.py](../ros_mes_hou/app/ros/normalizer.py) | 固定按旧压力/IMU段、ACK混用和压力均值业务号解释 | 新契约建立独立解析入口；未确认对 MES 的输出结构前不接 WS 或批次消费者 |
| [control.py](../ros_mes_hou/app/api/endpoints/control.py)、[finetuning.py](../ros_mes_hou/app/api/endpoints/finetuning.py)、[module.py](../ros_mes_hou/app/api/endpoints/module.py)、[coordination.py](../ros_mes_hou/app/api/endpoints/coordination.py)、[finetuning_batch.py](../ros_mes_hou/app/ros/finetuning_batch.py) | 多处直接 import 旧构造器，批次直接把业务 module_id 传给生成器，图纸协调端点也直接构造消息，会绕过适配器覆写 | 后续运行接入时逐点改为显式的契约对应入口；只增加 Ros2Dispatcher 子类不能完成迁移。此阶段等待映射、图纸入口及业务契约，暂不改调用方 |
| [schemas/local_stop.py](../ros_mes_hou/app/schemas/local_stop.py)、[stop_holds.py](../ros_mes_hou/app/ros/stop_holds.py) | 局部停沿用旧 scope 及臂号 `1～5` 校验，与 control.py 的发送/留锁流程耦合 | 随局部停入口一起评审，不能全局把旧臂号改成新实体号 `21～25`；当前校验和留锁不变 |
| `RosbridgeTransport` 初始化及 dispatch | 初始化读取持久化运行配置，dispatch 还查询急停联锁表 | 独立消息模块不以实例化此类作为起点；导入也不得间接启动应用、线程、网络或读写运行库 |
| [mock_client.py](../ros_mes_hou/app/ros/mock_client.py) | 模拟器也生成旧 `21～25` 反馈并转换业务号 | 新契约使用独立固定样例/离线替身；保留当前模拟器，防止修改模拟数据掩盖旧链路回归 |
| [设备编码](../ros_mes_front/src/api/deviceEncoding.ts)、[微调页](../ros_mes_front/src/components/Main/ModulePage/FineTuningPage.vue)、[API 类型](../ros_mes_front/src/api/rosApi.ts) | 页面压力及 IMU 都匹配旧 armLevelId；新 `31～40` 直接透传会被旧页面过滤 | 等 HTTP/WS 与数据库关系确定后再接前端；不提前全面重命名，不把传感器新编号塞进旧业务 ID |
| [schemas/finetuning.py](../ros_mes_hou/app/schemas/finetuning.py)、[db/models.py](../ros_mes_hou/app/db/models.py)、`db/schema.py` | 正业务号校验、旧 Unit 外键及配置/批次/历史快照；批次已分别存业务号与 seg | 等 ROS 方数据库设计；保留当前结构，不建新表、不迁列、不转换历史 JSON；消息字段同名不构成改库依据 |

独立范围为 ROS2 新契约专用的编号换算、消息构造/校验、反馈解析和离线样例。调用方显式传入 SEG、实体/臂位及已知绑定状态；这些是消息处理输入概念，不预定数据库列名。缺少映射或绑定证据时返回明确的不可发送/待确认结果，不默认 SEG=0，不查询旧库补猜。同日后续已在 `app/ros2_contract/` 新增上述纯消息模块（见 7.7），未改本表列出的运行调用方，也不新增 HTTP/WS 接口。

### 7.5 待 ROS 方补齐及数据库依赖

| 待确认内容 | 负责补齐/协商 | 对当前准备的影响 |
|---|---|---|
| 新 `.msg` 的版本化文件、包名/类型串、各消息话题和方向；通用 Feedback 与三轴反馈的关系 | ROS 方 | 已明确的编号和字段可先整理；未给出的话题/类型不注册或假定沿用 |
| 伸缩 Feedback、到位 angle/pos_error、HomeStatus 的单位和倍率，伸缩绝对限位与增量关系 | ROS 方 | 暂不实现这些字段的量纲转换、容差或完成判定 |
| 模块确认的 MES 发起入口、成功/失败回执、超时、token/结果关联；绑定状态查询的入口及有效期 | ROS 方与 MES 协商 | 可准备 ModuleStatus 解析；不能仅凭内存记录或旧成功响应宣称新绑定已核实 |
| 局部停各 scope、全局急停/解除、校零的完整消息和结果语义 | ROS 方与 MES 协商 | 已明确的臂 ID/校零包可列样例；未定操作不接入设备入口 |
| SensorCmd 下行 cmd_type 双表达的最终选择；压力均值的新来源/话题/ID；原始压力/阈值的倍率 | ROS 方 | 文档 §9 仍标待定，不能把其中单个选项当作最终实现；测量值与发送参数分别处理 |
| 三件套的绑定消息例外、Heartbeat 最终字段类型/有效掩码；各类 frame_id 规则 | ROS 方 | 以最终 `.msg` 为准，不据概述自行增删字段 |
| 模块业务身份、SEG、臂/轴/传感器、坐标地址的数据库结构和关系；多系统是否共库 | ROS 方设计，MES 对接评审 | 不预设表名/主外键/迁移方式；存储结构确定后再完成业务映射、持久化和历史兼容 |
| HTTP/WS 字段与内部反馈形状、配置/会话快照、历史记录迁移及切换/回退方式 | MES 在外部契约和数据库确定后设计 | 当前接口及前端保留；软件隔离样例通过后也不自动切换运行环境 |

普通 CmdAck/到位消息仍无逐请求标识，是当前新设计的能力边界，不在本轮自行加字段。后续 MES 请求号只能追踪自身业务记录，不能补出 ROS/设备没有回传的关联证据。

### 7.6 后续顺序与验收条件

1. **文档准备，已完成**：记录本节对照、源代码入口、隔离范围和待确认项；首轮仅文档的验证与后续代码验证分别记入改动记录，不把历史测试数算作本轮验证。
2. **独立消息模块，离线部分已完成**：仅实现已明确的规则和离线样例，暂不接现有运行入口。实际结果见 7.7，验收覆盖以下内容：
   - SEG `0/14` 可接受，`15`、业务号 `17`、非整数或布尔值不可作为新消息 SEG；缺映射不能回退到0。
   - 三类轴各自的 ID 集合、臂/压力/IMU 分段和保留号均校验；同一实体号在不同 SEG 下不混归属，矛盾的话题/消息类别不生成有效读数。
   - 压力 `31～35`、IMU `36～40`、失压归属及已明确的校零格式有固定期望样例；缺字段、坏值、未知消息不补成有效零值；合法数值0仍保留为有效值。
   - `ModuleStatus.status=0` 禁止生成可发送运动请求；`status=1` 不替代路由/绑定 SEG 一致性、状态时效及其他发送条件。两类 SEG 分别保留。
   - 保留原始消息；命令、位置、姿态、状态、ACK和事件分别解释；未明确的单位/话题/字段标为待确认，不猜测换算。
   - ROS1 的既有输入仍产生原有消息/反馈；新规则不进入 ROS1 默认链路。验证应使用固定旧契约样例和现有相关回归，不能用同一份新实现生成其自身期望值。
   - 全程离线，不导入 `app.main` 启动应用，不连接 ROS、串口或设备，不读写正式数据库；通过仅说明消息生成和解释符合已确认规则。
3. **数据库及外部入口确定后**：评审业务映射与存储兼容，再接 API/批次/WS/前端/模拟器，逐点覆盖当前绕过适配器的旧调用；同时验证 ROS1 保持原行为。
4. **联调与切换**：分别记录后端提交、ROS 包/契约、数据库和固件版本，按 ROS2 消息收发、设备接受、运动及完成证据分级验证；完成后再制定实际切换和回退步骤。本规划不执行部署、切换或真机操作。

### 7.7 独立消息模块及离线验证（2026-11-19，已实现、未运行接入）

开发分支为 `codex/ros2-contract-offline`。新增 [app/ros2_contract](../ros_mes_hou/app/ros2_contract/__init__.py)，与旧 `app/ros/` 并列，避免导入旧适配器时加载运行配置等依赖。模块只使用 Python 标准库，不读取环境变量、业务数据库或设备，不导入 ROS 包，也没有发送、重试或线程入口。原有工厂、ROS1/ROS2 dispatcher、HTTP/WS、批次、模拟器和前端均未接入这个包；设置 `ROS_VERSION=2` 仍使用原路径。

| 新增模块 | 已实现范围 | 边界 |
|---|---|---|
| [validation.py](../ros_mes_hou/app/ros2_contract/validation.py)、[addressing.py](../ros_mes_hou/app/ros2_contract/addressing.py) | 严格整数/有限数值、显式 ROS2 Header、SEG/实体分段/臂归属/轴类型及编号生成、模块内实体身份 | 不接收 bool、数字字符串或浮点 ID；不解释旧业务编码，不执行 CAN 总线映射 |
| [models.py](../ros_mes_hou/app/ros2_contract/models.py) | `BindingState`、`MessageDraft`、`ParsedMessage` 的纯消息数据形状；物理身份使用 addressing.py 的 `Address` | 不是数据库模型或现行 HTTP/WS schema；BindingState 不证明状态新鲜或查询已匹配；MessageDraft 内字典可编辑，未来发送边界须重新校验最终消息 |
| [commands.py](../ros_mes_hou/app/ros2_contract/commands.py) | 三轴相对微调、人工软件校零消息体；校验实体/轴类别以及显式绑定的路由 SEG、绑定 SEG、臂位一致性 | 缺少绑定证据、未绑定或目标不符即拒绝；输出仅名称/消息体/pending，不是 rosbridge 发布包，不绑定包名或话题，也不宣称运行条件/绝对限位已检查 |
| [feedback.py](../ros_mes_hou/app/ros2_contract/feedback.py) | 12 类消息：Feedback、SensorCmd、VacuumLoss、GyroFeedback、TuoLuoYi、AxisStatus、ArriveNotification、StopNotification、CmdAck、AxisFault、LimitEvent、ModuleStatus | 已知消息缺少必需字段或值非法时抛 ContractError；未知消息 is_known=false、无解释后的身份/读数，仅保留 raw；不推断运动完成 |

`parse_feedback()` 返回分开的 `address`、`values`、`units`、`pending`、`raw` 及可选 `binding`。values 保留消息数组/字段形状，valid_fields 只表示通过类型校验的字段；仍须结合 units/pending 判断含义，不能把它当成现有页面数据。伸缩位置/到位及失压原始量的未知单位设为 None 并标 pending，不换算；ACK 标记缺少逐请求关联；ModuleStatus 的 token 原样保留，状态时效和查询匹配尚未验证，module_state 只保留数值不解释。

话题/类型名由调用方明确提供，不内置新话题或包名前缀。可选 `topic_message_types` 只核对“话题→消息名”一致性，必须来自已确认的反馈方向映射；SensorCmd 下行命令与上行压力虽同名，但含义不同，不能仅凭消息名判方向。未给映射时本包只解析离线消息体，不证明该话题可信。

最小调用样例（在后端目录执行，不启动服务；样例绑定及时间戳均为离线输入）：

```python
from app.ros2_contract import BindingState, build_fine_tuning_message, parse_feedback

header = {"stamp": {"sec": 123, "nanosec": 0}, "frame_id": "module_0"}
binding = BindingState(route_seg=0, bound_seg=0, status=1, arm_slot=2, axis_base=4)
draft = build_fine_tuning_message(
    "rotation", 1.5, module_id=0, device_id=4, header=header, binding=binding,
)
assert draft.message["position"] == [1.5]
assert "runtime_checks_not_performed" in draft.pending
feedback = parse_feedback("SensorCmd", {
    "header": header, "module_id": 0, "device_id": 32, "id": 1, "position": [0.0],
})
assert feedback.address.device_id == 32
assert feedback.values["position"] == [0.0]
```

验证环境为后端 `venv` 的 Python 3.12.7。新增 ROS2 检查 **60/60**（编号/数值/Header 22 项、消息生成 11 项、反馈 26 项、独立进程隔离 1 项）；新增 ROS1 固定报文基线 **6/6**，覆盖三轴、握手、校零、旧压力/IMU编号及混用 ACK。新包的隔离测试使用 `-S` 子进程，阻断旧 ROS/数据库/应用及第三方依赖和连接行为，并分别验证 `ROS_VERSION=1/2/invalid-version` 不影响其导入和纯操作。

单独运行新增 ROS2 检查：`venv\Scripts\python.exe -m unittest discover -s tests -p "test_ros2_contract_*.py"`。旧协议基线为 `test_ros1_contract_baseline.py`。完整后端在已建表的临时内存库中 **289/289** 通过，未启动应用或连接真机；测试替身日志中“真实/指令已发送”等沿用旧文案，不作为真实通信证据。首次直接指定空内存库运行时，9 项旧局部停检查因全局批次管理器缺表报错；仅补齐内存库结构后通过，未为此改旧代码或正式库。

完整隔离回归的可复现方式（后端目录，PowerShell；只在内存建表，不运行种子脚本）：

```powershell
@'
import os
import sys
import unittest
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
from app.db import models
from app.db.database import engine
assert engine.url.database == ':memory:'
models.Base.metadata.create_all(bind=engine)
result = unittest.TextTestRunner().run(unittest.defaultTestLoader.discover('tests'))
sys.exit(not result.wasSuccessful())
'@ | & .\venv\Scripts\python.exe -
```

后续仍等待：数据库及业务映射、已确认话题/包名、模块确认/停止/解除/传感器下发等完整入口、状态时效与查询关联、未定单位。Heartbeat、HomeStatus、内部绑定消息、Kinematics 等本轮未实现专用解析；收到时按未知消息保留。尚未进行 ROS2 实际收发、设备接受/运动、前端接入或部署切换。
