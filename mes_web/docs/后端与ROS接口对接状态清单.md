# 后端与 ROS 接口对接状态清单

核查日期：2026-11-07。维护范围：前后端视角的接入状态、证据和缺口。本清单不是 ROS 协议定义，不替代根 `docs/` 的[三轴版 V2.1 共享契约](../../docs/ROS_MES_前后端ROS接口清单_三轴版_V2.1.md)。前后端任务入口见 [AGENTS.md](../AGENTS.md)，HTTP/WS 字段见[接口文档](ROS_MES_前后端接口字段文档.md)，本次最终验证结果由[改动记录](ROS_MES_前后端改动记录.md)统一维护。

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
| GET/PATCH `/api/control/debug-settings`，页面选择连接 | 不新增 ROS 消息，仅配置后端传输 | ROS 节点未改 | 不适用 | 持久化模式/地址/版本，操作中拒绝切换；真实/模拟联锁分离 | 个人中心调试设置及急停遮罩共用面板，逐项手动自动应用；图纸三选 skip/mock/real 替代独立跳过开关 | [运行配置](../ros_mes_hou/app/ros/runtime_settings.py)、[模拟适配](../ros_mes_hou/app/ros/mock_client.py)、[页面面板](../ros_mes_front/src/components/Main/UserManage/RosConnectionSettings.vue)；首次默认真实，不自动降级 | 已通过隔离验证，真实地址由现场填写 |
| `POST /api/module/`，逐台确认机械臂 | `/control/module_cmd`、成功/失败回执，`IntCmd` | `module_confirme_node.py` 有 UID/组号/臂位双确认及可配置状态复核 | 当前固件会话绑定的实际支持待确认 | 构造显式 SEG/arm，逐项等待匹配回执，失败停止后续项；返回 `data.seg` | 微调初次配置使用，调试模式也必须确认 | [模块端点](../ros_mes_hou/app/api/endpoints/module.py)、[网关](../ros_mes_hou/app/ros/rosbridge.py)、[ROS 节点](../../robot_control_backend/scripts/module_confirme_node.py)；模拟握手不证明设备绑定 | P0；保留兼容；现场核对固件版本和绑定状态 |
| `POST /api/control/finetuning/batches`，三轴统一确认 | `/control/adjust_rotation_cmd`、`adjust_swing_cmd`、`adjust_telescopic_cmd`；既有三轴消息 | 三轴节点有微调转发、基准/软限位处理；本次未改 ROS | 实际运动、单位、状态/到位事件支持待确认 | 持久化幂等及物理目标锁，顺序发送；观测到运行、目标到位及空闲才推进；异常保留待核实 | 主微调页一个确认按钮，输入只改草稿；轮询/刷新恢复不重发，真实实测不取 HTTP 回显 | [批次管理器](../ros_mes_hou/app/ros/finetuning_batch.py)、[控制端点](../ros_mes_hou/app/api/endpoints/control.py)、[微调页](../ros_mes_front/src/components/Main/ModulePage/FineTuningPage.vue)；MES 请求号不是设备回显号 | P0；前后端模拟通过，现场需验证反馈、单位、时序及独占条件 |
| `POST /api/control/finetuning`，兼容单轴增量 | 同上 | 同上 | 待确认 | 保留发送语义，不等待完成；检查轴/参数/臂一致及批次锁 | 主微调页已改用批次接口；旧调用仍兼容 | [消息构造](../ros_mes_hou/app/ros/rosbridge.py)；发送≠接受≠到位 | P0；不把旧接口当作批次完成依据，不自动重发 |
| `GET /api/drawing/?for_tuning=true`、`POST /api/coordination/send`，图纸选择/路径及三视图 | `/frontend_pointcloud_topic`，`std_msgs/String`；选择列表不发送 ROS | `data_process_node.py` 有文件处理和视图服务；后续点云/逆解为 ROS 内部链路 | 本接口本身不证明后续轴运动；下位机执行待确认 | mock 可返回内置选择项并模拟下发/视图，不写正式图纸表；real 校验正式图纸，skip 拒绝下发及视图；版本变化拒绝旧请求/视图 | 三种图纸处理互斥；空库可用内置模拟图纸，保存 builtin_mock 来源及 null 图纸编号；真实空库仍要求导入 | [图纸端点](../ros_mes_hou/app/api/endpoints/drawing.py)、[协调端点](../ros_mes_hou/app/api/endpoints/coordination.py)、[ROS 图纸节点](../../robot_control_backend/scripts/data_process_node.py)；模拟预览不证明点云处理，真实视图可取不证明运动完成 | P1；真实流程需图纸可见、正确 ROS/视图地址及真实急停 |
| `POST /api/control/emergency_stop`，急停发送 | `/control/softstop` → `/arm/cmd_vel`，`IntCmd` | `softstop_node.py` 有转发，硬件节点有 CAN 下发路径 | 当前固件急停及解除状态待现场确认 | 独立发送路径保留，先持久化联锁并停止批次后续下发 | 侧栏长按急停，删除五秒自动恢复，发送结果不明保留提示 | [急停端点](../ros_mes_hou/app/api/endpoints/control.py)、[侧栏](../ros_mes_front/src/components/Main/AsidePage.vue)、[ROS 转发](../../robot_control_backend/scripts/softstop_node.py)；发送成功不是已停证据 | P0；当前不宣称设备停止确认 |
| `POST /api/control/emergency_stop/release`，解除发送；GET `/api/control/emergency_stop/status`，MES 联锁查询 | `/control/softstop_release` → `/arm/cmd_vel`，既有 `IntCmd`；查询只读 MES 数据库 | ROS 有独立解除转发 | 待确认 | 记录解除发送状态与联锁版本，不恢复旧批次；模拟解除不清除真实联锁 | 侧栏已实际调用；历史/轮询/刷新仅持续提示，全屏由长按或手动查看打开且可返回页面保留状态；真实发送成功仍待确认，模拟解除成功可关闭 | 同上；恢复提示不发送新的急停，解除急停与轴故障复位不同，状态查询不是设备实测 | P0；软件链路模拟通过，实际解除待现场确认 |
| `GET /api/ros/send_ros`，通用测试消息 | `/web_cmd`，`std_msgs/String` | 测试通道，具体接收/业务动作需按 ROS 节点核查 | 不适用，不证明硬件动作 | 两版适配统一经 rosbridge 发布 | `RosTestPage.vue` 使用 | [测试端点](../ros_mes_hou/app/api/endpoints/ros.py)、[测试页](../ros_mes_front/src/components/Main/RosTestPage.vue)；页面历史“模拟”文案不等于 API 固定使用模拟 | P2；区分环境模拟和真实通道 |
| `GET /api/ros/get_ros_status`，订阅状态快照 | `/robot_status`，状态消息 | 发布者有效输出/现场部署待确认 | 不适用 | 常驻订阅器维护连接与最近状态 | 测试页使用 | [profile](../ros_mes_hou/app/ros/profile.py)、[状态订阅器](../ros_mes_hou/app/ros/rosbridge.py)；`ros_ready` 不证明机械臂在线，默认电量等不能作设备实测 | P1；需真实发布者和可辨识数据来源 |
| 串口测试、硬件实时状态 HTTP 工具 | 子进程 `serial_test_node.py` / `hardware_node.py`，非独立 ROS 对外话题契约 | 脚本依赖运行环境/硬件；存在文件不保证输出符合接口模型 | 待确认 | `app/ros/base.py` 有超时子进程工具 | 顶栏使用串口测试；实时硬件状态未发现页面消费 | [基类工具](../ros_mes_hou/app/ros/base.py)、[控制端点](../ros_mes_hou/app/api/endpoints/control.py)；未在本次自动启动硬件脚本 | P2；隔离设计及硬件环境就绪后验证 |

## 3. 已订阅的对外反馈

以下 13 路由 [profile](../ros_mes_hou/app/ros/profile.py)、[反馈流](../ros_mes_hou/app/ros/rosbridge.py)和[归一化](../ros_mes_hou/app/ros/normalizer.py)接入。新增五类事件由后端批次管理器消费，前端通过批次查询显示结果；每一路的下位机“本版本已发送”和“真机已验证”目前均待确认。

| 话题/消息 | 用途与编号语义 | ROS 源码实现状态 | 下位机支持 | 后端接入 | 前端使用 | 验证证据/缺口 | 优先级及后续条件 |
|---|---|---|---|---|---|---|---|
| `/hardware/rotation_feedback` / `RotationCmd` | 旋转角度，`module_id` 为 CAN SEG | `feedback_node.py` 换算 CAN 位置并透传 SEG | 待确认 | 已转发；本次补有效性标记 | 主微调页已消费；本次补 SEG/臂核验及逐项时效 | [反馈节点](../../robot_control_backend/scripts/feedback_node.py)；需与当前固件单位和现场版本核对 | P0；未归属或无效样本不更新实际值 |
| `/hardware/swing_feedback` / `SwingCmd` | 摆动角度，CAN SEG | 同上 | 待确认 | 同上 | 同上 | 同上；不能按轴号单独跨模块匹配 | P0；同上 |
| `/hardware/telescope_feedback` / `TelescopicCmd` | 实测长度 mm，CAN SEG | ROS 内部把 CAN 0.01mm 换算为 mm | 待确认 | 原样传 mm；本次补有效性标记 | 主微调页消费，不能再做重复 ×100/÷100 | [伸缩消息](../../robot_control_backend/msg/TelescopicCmd.msg)、反馈节点；固件单位需同版本核实 | P0；保留明确单位与基准依赖 |
| `/hardware/sensor_feedback` / `SensorCmd` | 瞬时压力，CAN SEG、臂级编号 | 反馈节点转换及发布 | 待确认 | 已转发 | 主微调页消费；本次改为独立等待/时效状态 | 不能因为轴已反馈就把默认压力 0 显示为实测 | P0；压力实际频率、标定单位待确认 |
| `/hardware/imu_angles` / `TuoLuoYi` | 姿态/坐标分量，沿硬件链路透传 CAN SEG | `tuo_luo_yi.py` 分模块/臂维护并发布 | 待确认 | 已转发；本次分量独立有效性 | 主微调页消费；本次分量独立时效 | [IMU 节点](../../robot_control_backend/scripts/tuo_luo_yi.py)；缺失/非法分量不能补成零 | P0；现场标定、精度与坐标语义另行验证 |
| `/hardware/pressure_avg` / `SensorCmd` | 采样窗口均值，`module_id` 来自触发上下文的业务编号 | `imu_average_calculator_node.py` 已发布，但存在异臂样本进入同一窗口的路径 | 待确认 | 已转发 `pressure_average`，不能一律当 SEG | **前端未展示** | [均值节点](../../robot_control_backend/scripts/imu_average_calculator_node.py)；只提示来源问题，本次不修改 ROS 或把界面接通当作均值正确 | P2；ROS 侧先核实采样归属、触发和窗口 |
| `/hardware/vacuum_loss` / `VacuumLoss` | 失压事件，硬件 CAN SEG 与臂级编号 | 硬件节点有事件解析与发布 | 待确认 | 转发事件及压力/阈值字段；所属臂事件中止批次后续下发 | 通过批次待核实原因提示；未新增独立告警页 | [批次管理器](../ros_mes_hou/app/ros/finetuning_batch.py)；现场压力单位和防误报条件待核对 | P1；模拟中止路径已接入，设备保护效果未验证 |
| `/hardware/cmd_ack` / `CmdAck` | 接受/拒绝事件；软件回执用业务号，CAN 回执用 SEG | 三轴节点软件拒绝、硬件节点 CAN ACK及回零软件拒绝均可发布到此话题 | 各类 ACK 的实际发送支持待确认 | 转发 result/detail/raw 及保守归属元数据；可能属于当前臂的非零拒绝保守中止，接受不推进 | 可归属及归属待确认事件提示，批次另行显示中止结果 | [CmdAck](../../robot_control_backend/msg/CmdAck.msg)、[硬件节点](../../robot_control_backend/scripts/hardware_node.py)；没有发布者来源或请求 ID | P0；不能关联为某次请求最终结果 |
| `/hardware/axis_status` / `AxisStatus` | SEG、轴号、状态字/运行状态/基准有效性 | 硬件节点解析并发布 | 待确认 | 新鲜有效空闲用于发送前检查；新 RUN 及后续空闲用于批次完成判定 | 批次进度间接消费，未增加独立状态仪表 | [归一化](../ros_mes_hou/app/ros/normalizer.py)、批次管理器；缺字段不补默认值 | P0；需核实状态位与实际发布频率，短动作漏 RUN 时停止后续发送 |
| `/hardware/arrive_notification` / `ArriveNotification` | SEG、轴号、原始位置/误差及有效标志 | 硬件节点有 CAN 事件解析 | 待确认 | 同轴新 RUN 后检查目标、误差和有效标志，配合空闲判定；不凭到位事件单独推进 | 通过批次查询显示完成/待核实 | 消息无设备请求号；伸缩原始单位等需按现场版本核实 | P0；软件观测完成不等于固件级逐请求关联 |
| `/hardware/stop_notification` / `StopNotification` | SEG、轴号、停止原因/输出 | 硬件节点有解析 | 待确认 | 非正常到位停止中止后续下发；正常停止本身不替代到位判定 | 通过批次原因提示 | `StopReason`、作用域和现场版本待核实 | P0；未由发送结果推断停机 |
| `/hardware/axis_fault` / `AxisFault` | SEG、轴号、故障字段 | 消息及解析存在；协议说明记载部分固件判断关闭 | 待确认 | 所属臂故障事件中止后续下发 | 通过批次原因提示，无新增故障复位入口 | 不凭消息定义推断实际报告种类 | P0；现场固件实际支持待核实 |
| `/hardware/limit_event` / `LimitEvent` | SEG、轴号、限位类型/输出 | 硬件节点有解析 | 待确认 | 所属臂限位事件中止后续下发 | 通过批次原因提示 | 软件拒绝、物理限位和锁存故障仍需区分 | P0；不自动复位或重发 |

## 4. 回执、时间和状态边界

兼容单轴接口的 `sent` 是 WebSocket 写出证据，`confirmed=null/confirmation_status=not_requested` 表示未等待设备确认。批次接口的 HTTP 202 只表示登记；`completed` 表示在目标独占条件下观测到发送后的运行、目标到位及空闲组合，仍受无设备请求序号的关联边界限制。模块确认通过专用回执核验后保留 `confirmed=true`；不能用普通微调的语义更改破坏该分支。急停/解除仍使用独立兼容下行路径。

CmdAck 同一话题混合不同编号空间，`header` 目前也没有可靠的发布者来源标记。`raw` 能保存已有信息，不能恢复消息中不存在的来源或请求编号。即便模块和轴唯一可归属，迟到 ACK 与同轴连续增量命令仍不能可靠逐条关联；接受事件不等于运动完成，没有回执也不等于拒绝。

本次归属规则只增加后端 WebSocket 元数据，不改 ROS 消息：正业务号保留为候选；原号在 0～14 时再按显式 `ROS_MODULE_SEG_MAP` 收集 SEG 对应候选。配置无效或 SEG 无映射为 unknown，多候选为 ambiguous，仅无未决解释且唯一时为 resolved；保留原号和 raw。普通遥测、压力均值、混合回执不能共用一个无条件转换规则。

前端逐轴、压力、IMU 分量用浏览器接收的单调时间判断显示新鲜度；默认轴/IMU 5 秒、压力 10 秒，可配置，属于暂定 UI 策略，不是硬件周期或故障判定。缓存恢复为历史值，断线使已有值过期；坏样本不刷新时效、不补零、不终止整个反馈流。真实零值仍应正常显示。

批次记录持久化于 MES 数据库，以物理 SEG+arm 锁定目标并拒绝重复请求；模拟锁额外带 mock 前缀。查询/刷新不会再次下发。前端批次详情和 ACK 提示按臂保存，切臂不沿用另一臂记录，切回恢复本会话内记录；新会话清除旧臂缓存，旧查询迟到响应不能覆盖新批次。已尝试发送但缺少完成证据时保留 `uncertain`，真实操作需现场核实，模拟操作核对模拟记录后关闭；后端重启均不恢复旧动作。每批保存模式/地址/版本快照，模拟反馈不能驱动真实批次推进。此机制只支持单后端工作进程，不能阻止 ROS 内部或外部控制器并行发令，真机使用前必须明确目标独占。后端接收时刻只用于软件新鲜度，不证明设备时钟同步或端到端时延。

## 5. 本次只登记、不扩展的能力

下表只收录可能对 MES 有意义的能力，**不是把所有 ROS 内部话题列为后端缺失接口**。模块握手中的 UID、组号/臂位确认、绑定及状态复核等内部消息由 ROS 节点使用，不要求前后端分别暴露 API。

| 能力/相关话题与消息 | ROS 仓库证据 | 下位机支持 | 后端/前端现状 | 后续条件 |
|---|---|---|---|---|
| 回零 `/control/home_cmd` / `IntCmd`、`/hardware/home_status` / `HomeStatus` | 硬件节点有处理且有 `home_supported` 限制；可发 `ack_msg=4` 软件拒绝 | 待确认 | MES 未提供本次回零操作入口或状态消费 | 先核实真实固件能力及操作条件 |
| 单轴故障复位 | 共享保护说明给出 CAN 复位帧 | 待确认 | 未发现已建立的独立 MES→ROS 复位契约 | 双方先确认对外 ROS 接口，不能直接新增 CAN 指令 |
| 独立模块状态查询 `/control/module_status_query` / `IntCmd`、`/hardware/module_status` / `ModuleStatus` | 硬件节点实现；模块确认节点内部用于状态复核 | 待确认 | 模块确认内部使用，不等于 MES 有独立查询入口 | 明确独立查询需求、token匹配及状态字段 |
| 固件级完整指令追踪 | 当前消息无可靠请求关联标识 | 待确认 | 已有 MES 批次幂等及观测进度，尚不能精确匹配固件逐请求接受→执行→停止/到位 | 需双方明确设备关联能力；本次不改 ROS/固件协议 |
| 大屏 `/api/ws/ws/robot_status` 的底层数据源 | 后端端点存在，`web_data_node.py` 历史代码整段注释 | 不适用/待有效数据源 | 有受 token 保护的转发入口，不能证明大屏已有实时流 | ROS 数据源与实际页面订阅应单独核查 |

## 6. 验证与外部依赖

- 本轮最终自动检查通过：前端微调/急停/请求/连接配置 68/68 项、图纸 12/12 项、后端 129/129 项，类型检查及生产构建通过，仅有现有资源包体积提示。新增空正式图纸库模拟、三种图纸处理互斥、历史急停不自动全屏、来源与版本校验、切臂/新会话及迟到查询/ACK 回归；详见改动记录 2026-11-07 完成条目。
- 本轮隔离浏览器完整流程通过：真实登录后空库内置图纸双臂确认、三轴草稿不立即下发、一次确认顺序完成及保存 null 图纸编号/内置来源、不使用图纸保存、模拟急停刷新提示及解除、真实空库仍要求导入、切臂记录隔离及切回恢复。全程正式图纸表为零条，共两个完成的模拟批次；急停/解除 POST 各一次且仅由主动操作产生，真实历史 stop_unknown/generation=8 保留，模拟解除后为 clear。未连接真实 ROS/串口，未写运行库业务记录。
- 临时隔离测试服务、脚本及 SQLite 已清理；本地前后端 5173/8000 正常保留，新接口字段可读取。代码尚未提交或上传 GitHub；模拟验证不能证明现场 ROS/固件/设备行为。
- 上次调试功能已有实际组件/Pinia 回归、配置保存的内存数据库测试及隔离浏览器验证，证明范围限前后端软件路径；不证明 rosbridge、ROS 或 CAN/设备行为。
- [历史全流程报告](../../docs/ROS_MES_全流程测试报告.md)为 2026-10-25 模拟下位机验证；[真机 CAN 报告](../../docs/can_real_device_debug_report.md)是指定环境的问题记录。两者保留原结论和环境，不能自动套用于当前提交和现场固件。
- 待外部确认：现场 ROS/固件版本、各类 ACK/状态/到位真实支持、到位原始单位及容差、短动作 RUN 的可观测性、压力标定与反馈频率、IMU 精度/坐标、断电重绑会话状态、独占控制条件。未取得直接证据前均为待确认；压力均值异臂采样路径交由 ROS 方核实，本侧未修改节点。
- 已发现配置差异：ROS 本体 `rob_arm.env` 的图纸话题为 `/frontend_pointcloud_topic`，共享部署模板 `deploy/config/rob_arm.env` 仍有 `/control` 前缀。仅记录，未擅改 ROS 配置或共享协议；实际部署采用哪份配置需核查。
