# ROS_MES 前端 V1.0 → V1.1 修改清单（执行版）

> 原清单基于前端静态分析生成（2026-10-05，26 项）。本文件为**对照 V1.1 事实核验后的执行记录**：
> 每项先核对 v1.1 后端接口 / ROS msg 定义 / 数据库种子，前提成立才修改，前提不成立的标注证据。
> 核对依据：《ROS_MES_前后端接口字段文档》、`robot_control_backend/msg/*.msg`、`ros_mes_hou` v1.1 代码（commit b03b57a）、`sqlite_create.py` 种子数据。
>
> **执行日期：2026-10-05　类型检查：vue-tsc 通过（0 错误）**

## 状态汇总

| 结果 | 数量 | 编号 |
|---|---|---|
| ✓ 已修改 | 10 | P0-01~05、P1-05、P1-06、P1-07、P2-01(部分)、P2-03 |
| ✗ 无需修改（前提不成立） | 9 | P0-06~09、P1-01、P1-03、P2-04~06 |
| ⏸ 暂缓（后端未支持/留后续版本） | 7 | P1-02(部分)、P1-04、P1-08、P1-09、P2-02、P2-07、P2-08 |

## 逐项执行结果

### 🔴 P0

| 编号 | 状态 | 结论 |
|---|---|---|
| P0-01 armList 硬编码 41/42/43 | ✓ 已修改 | `FineTuningPage.vue`：deviceId 由 `applyAxisEncoding()` 按 V2 轴号动态填充（选臂后重算）；顺带修复微调下发原来三个轴都发 `initConfig.deviceId` 的错误——现在发各轴自身 `device_id` |
| P0-02 feedbackDeviceIndex 含旧编码 | ✓ 已修改 | 删除 33/34/35 与 41/42/43 硬编码，`rebuildFeedbackIndex()` 按当前臂轴号动态构建 |
| P0-03 IMU device_id===50 | ✓ 已修改 | 仅按 `type === "imu_pose"` 判断（V2 中 IMU 为臂级 21~25，与压力共用 device_id，按 data_type 区分） |
| P0-04 noRosDebug feedbackDeviceMap 41/42/43 | ✓ 已修改 | 改用 `axisDeviceId(1, …)` → 1/2/4（一号臂 V2 轴号），经统一编码模块引用 |
| P0-05 noRosDebug IMU 50 | ✓ 已修改 | `device_id: 50` → `armLevelDeviceId(1)` = 21 |
| P0-06 ARM_OPTIONS 32/64/96 | ✗ 无需修改 | v1.1 数据库种子 `sqlite_create.py` 机械臂 Unit_ID 仍为 32/64/96，编码未变；动态化并入 P2-02 后续版本 |
| P0-07 SENSOR_OPTIONS offset 硬编码 | ✗ 无需修改 | offset 与 v1.1 种子完全吻合（32+1=33 电机、32+9=41 编码器、32+17=49 压力、32+18=50 陀螺仪）；新增传感器类型时再同步 |
| P0-08 getSensorId = unitId+offset | ✗ 无需修改 | 公式与种子吻合；注意 sensor_id（sensors 表业务号）与 device_id（V2 轴号）是两套命名空间 |
| P0-09 adjustmentKeys 三轴参数名 | ✗ 无需修改 | v1.1 后端 `FINE_TUNING_TOPIC_MAP` 就是 rotation/swing/telescopic |

### 🟡 P1

| 编号 | 状态 | 结论 |
|---|---|---|
| P1-01 module_id = x*16+y | ✗ 无需修改 | v1.1 后端 `/module/` 仍按 `x*16+y` 推算，编码未变 |
| P1-02 data_type 判断 | ⏸ 部分暂缓 | 现有枚举与 v1.1 网关归一化输出一致，无需改；新增限位/故障/心跳类型等后端接入后补（同 P1-08/P2-07） |
| P1-03 IMU 字段名 | ✗ 无需修改 | swing_angle/rotation_angle/x/y/z 与 `TuoLuoYi.msg` 及网关归一化字段逐字一致 |
| P1-04 压力固定在 device[3] | ⏸ 暂缓 | V2 规范固定 3 有效轴（J3 空置），索引 3 = 压力项符合规范；v-for 动态化留后续版本 |
| P1-05 sensorId 误取轴 deviceId | ✓ 已修改 | 新增 `loadSensorsForUnit()`：调 `getSensorsByUnitApi` 取传感器列表，按描述含"压力"（兜底 Unit_address=0）选压力传感器，用其 `sensor_ID` |
| P1-06 RosTestPage 硬编码测试数据 | ✓ 已修改 | module_id/device_id/unit_id/unit_row_id/drawing_id/parameter_name/position 全部输入框化（默认 V2 有效值）；顺带修正 coordination 测试 payload 缺 unit_id/unit_row_id/drawing_id、fine-tuning 测试缺 unit_id/parameter_name 且 position 传字符串的契约问题 |
| P1-07 保存配置 device_id/sensor_id 混淆 | ✓ 已修改 | 三轴项只带 `device_id`；仅臂级压力项带 `sensor_id`（来自传感器列表）；顶层 `sensor_id` 同步为压力传感器 ID |
| P1-08 缺心跳处理 | ⏸ 暂缓 | v1.1 后端 `rosbridge_gateway.py` 只订阅 5 个反馈话题、不含 Heartbeat，前端处理是死代码；等后端接入后补 |
| P1-09 缺急停通知处理 | ⏸ 暂缓 | 后端未推送 StopNotification；前端侧已先启用急停遮罩（P2-03），通知联动等后端支持 |

### 🟢 P2

| 编号 | 状态 | 结论 |
|---|---|---|
| P2-01 单位显示不统一 | ✓ 部分修改 | 旋转/摆动 "(度)" → "(°)" 统一；mm（伸缩指令）与 cm（IMU 坐标）与 V2 消息定义单位一致，保留；单位配置化留后续 |
| P2-02 轴数写死 3 | ⏸ 暂缓 | V2 规范即 3 有效轴（J1/J2/J4），UI 动态化留后续版本 |
| P2-03 急停遮罩被注释 | ✓ 已修改 | `AsidePage.vue` 遮罩已启用；"解除急停(仅调试)"按钮保留并注明生产环境需权限控制 |
| P2-04 Dashboard mock 硬编码 | ✗ 无需修改 | v1.1 已按 `VITE_USE_MOCK` 分流：false 时调真实 `getDashboardStats()`，mock 仅调试模式；初始占位 '---' 不误导 |
| P2-05 AddItem.vue value 硬编码 | ✗ 不处理 | 该组件未挂载任何路由、调用不存在的 `/hardware` 接口，属死代码，待清理（见交接日志） |
| P2-06 "聚类阈值(mm)" 硬编码 | ✗ 无需修改 | 与图纸 JSON 解析输出的字段名一致 |
| P2-07 缺限位/故障显示 | ⏸ 暂缓 | 后端未订阅 LimitEvent/AxisFault 话题，前端无数据源；等后端接入 |
| P2-08 缺真空吸盘支持 | ⏸ 暂缓 | v1.1 数据库种子与后端均无真空吸盘传感器支持 |

## 本次实际改动文件

| 文件 | 改动 |
|---|---|
| `src/api/deviceEncoding.ts` | **新增**：V2 编码唯一出处（armIndexFromUnitId / axisDeviceId / armLevelDeviceId） |
| `src/components/Main/ModulePage/FineTuningPage.vue` | 动态轴号、动态反馈映射、按轴下发 device_id、IMU 判断改 type、sensorId 取自传感器列表、保存配置字段分离、单位统一 |
| `src/api/noRosDebug.ts` | 调试模拟改用 V2 编码（1/2/4、臂级 21） |
| `src/components/Main/RosTestPage.vue` | 测试 ID 输入框化 + 测试 payload 对齐后端契约 |
| `src/components/Main/AsidePage.vue` | 启用急停遮罩 |

> 后续待办：P1-08 / P1-09 / P2-07 等后端接入心跳、急停通知、限位故障话题后在 `applyFeedback` 补充分支；P2-02 / P2-08 留后续版本。
