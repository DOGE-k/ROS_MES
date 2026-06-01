# Robot Control Backend 话题汇总

## 一、话题总览

### 1. 控制指令话题（Control Commands）

| 话题名称                                 | 消息类型            | 发布节点              | 订阅节点                              | 说明              |
| ------------------------------------ | --------------- | ----------------- | --------------------------------- | --------------- |
| `/control/kinematics_rotation_cmd`   | `RotationCmd`   | `kinematics_node` | `control_node`                    | 运动学解算旋转指令（增量角度） |
| `/control/kinematics_swing_cmd`      | `SwingCmd`      | `kinematics_node` | `control_node`                    | 运动学解算摆动指令（增量角度） |
| `/control/kinematics_telescopic_cmd` | `TelescopicCmd` | `kinematics_node` | `control_node`                    | 运动学解算伸缩指令（增量长度） |
| `/control/adjust_rotation_cmd`       | `RotationCmd`   | 前端/Web            | `control_node`, `rotation_node`   | 前端微调旋转指令        |
| `/control/adjust_swing_cmd`          | `SwingCmd`      | 前端/Web            | `control_node`, `swing_node`      | 前端微调摆动指令        |
| `/control/adjust_telescopic_cmd`     | `TelescopicCmd` | 前端/Web            | `control_node`, `telescopic_node` | 前端微调伸缩指令        |

### 2. 时序控制话题（Sequenced Commands）

| 话题名称                                           | 消息类型            | 发布节点           | 订阅节点              | 说明      |
| ---------------------------------------------- | --------------- | -------------- | ----------------- | ------- |
| `/control/kinematics_rotation_cmd_sequenced`   | `RotationCmd`   | `control_node` | `rotation_node`   | 时序化旋转指令 |
| `/control/kinematics_swing_cmd_sequenced`      | `SwingCmd`      | `control_node` | `swing_node`      | 时序化摆动指令 |
| `/control/kinematics_telescopic_cmd_sequenced` | `TelescopicCmd` | `control_node` | `telescopic_node` | 时序化伸缩指令 |
| `/control/adjust_rotation_cmd_sequenced`       | `RotationCmd`   | `control_node` | `rotation_node`   | 时序化微调旋转 |
| `/control/adjust_swing_cmd_sequenced`          | `SwingCmd`      | `control_node` | `swing_node`      | 时序化微调摆动 |
| `/control/adjust_telescopic_cmd_sequenced`     | `TelescopicCmd` | `control_node` | `telescopic_node` | 时序化微调伸缩 |

### 3. 硬件层话题（Hardware Layer）

| 话题名称                           | 消息类型            | 发布节点              | 订阅节点                                 | 说明            |
| ------------------------------ | --------------- | ----------------- | ------------------------------------ | ------------- |
| `/arm/cmd_vel`                 | `IntCmd`        | `feedback_node`   | `hardware_node`                      | 最终硬件控制指令（编码值） |
| `/hardware/rotation_output`    | `IntCmd`        | `rotation_node`   | `feedback_node`                      | 旋转轴输出指令       |
| `/hardware/swing_output`       | `IntCmd`        | `swing_node`      | `feedback_node`                      | 摆动轴输出指令       |
| `/hardware/telescope_output`   | `IntCmd`        | `telescopic_node` | `feedback_node`                      | 伸缩轴输出指令       |
| `/hardware/all_feedback`       | `Feedback`      | `hardware_node`   | `feedback_node`                      | 所有硬件原始反馈      |
| `/hardware/rotation_feedback`  | `RotationCmd`   | `feedback_node`   | `kinematics_node`, `rotation_node`   | 旋转轴角度反馈       |
| `/hardware/swing_feedback`     | `RotationCmd`   | `feedback_node`   | `kinematics_node`, `swing_node`      | 摆动轴角度反馈       |
| `/hardware/telescope_feedback` | `TelescopicCmd` | `feedback_node`   | `kinematics_node`, `telescopic_node` | 伸缩轴长度反馈       |
| `/hardware/sensor_feedback`    | `SensorCmd`     | `feedback_node`   | -                                    | 压力传感器反馈       |
| `/hardware/gyroscope_feedback` | `GyroFeedback`  | `hardware_node`   | -                                    | 陀螺仪六轴数据反馈     |
| `/hardware/module_cmd`         | `IntCmd`        | `feedback_node`   | -                                    | 模块控制指令        |

### 4. 点云处理话题（Point Cloud Processing）

| 话题名称                         | 消息类型     | 发布节点                | 订阅节点                | 说明              |
| ---------------------------- | -------- | ------------------- | ------------------- | --------------- |
| `/frontend_pointcloud_topic` | `String` | 前端/Web              | `data_process_node` | 前端点云数据输入（JSON）  |
| `/module_arm_task`           | `String` | `data_process_node` | `calculation_node`  | 模块切分结果          |
| `/arm_alpha_beta`            | `String` | `calculation_node`  | `kinematics_node`   | 最优托举点计算结果（JSON） |
| `/arm_fusion_stats`          | `String` | `calculation_node`  | -                   | 算法统计信息          |

### 5. 传感器触发话题（Sensor Trigger）

| 话题名称                  | 消息类型     | 发布节点                                             | 订阅节点                  | 说明             |
| --------------------- | -------- | ------------------------------------------------ | --------------------- | -------------- |
| `/control/sensor_cmd` | `IntCmd` | `rotation_node`, `swing_node`, `telescopic_node` | `sensor_control_node` | 压力传感器触发信号（立即响应） |

### 6. 陀螺仪话题（Gyroscope）

| 话题名称                        | 消息类型         | 发布节点           | 订阅节点       | 说明           |
| --------------------------- | ---------- | -------------- | ---------- | ------------ |
| `/hardware/gyroscope_feedback` | `GyroFeedback` | `hardware_node` | `tuo_luo_yi` | 陀螺仪六轴数据反馈 |
| `/hardware/imu_angles`                 | `TuoLuoYi`     | `tuo_luo_yi`    | `前端`        | IMU计算的角度数据 |

### 7. 急停控制话题（Emergency Stop）

| 话题名称              | 消息类型    | 发布节点   | 订阅节点         | 说明               |
| ----------------- | ------- | ------ | ------------ | ---------------- |
| `/control/softstop` | `IntCmd` | 前端/Web | `softstop_node` | 急停触发指令（device_id=1） |

### 8. 模块确认话题（Module Confirm）

| 话题名称                          | 消息类型    | 发布节点                 | 订阅节点                 | 说明          |
| ----------------------------- | ------- | -------------------- | -------------------- | ----------- |
| `/control/module_cmd`          | `IntCmd` | 前端/Web, `feedback_node` | `module_confirme_node` | 模块控制指令    |
| `/control/module_confirm_success` | `IntCmd` | `module_confirme_node`  | -                    | 模块确认成功信号 |
| `/hardware/module_cmd`         | `IntCmd` | `hardware_node`         | `module_confirme_node` | 模块硬件反馈    |

---

## 二、环境变量与话题映射

### rob_arm.env 关键配置

| 环境变量 | 映射话题 | 说明 |
|---------|---------|------|
| `ROS_TOPIC_KINEMATICS_ROTATION_CMD` | `/control/kinematics_rotation_cmd_sequenced` | **注意**：实际指向 control_node 的时序化输出 |
| `ROS_TOPIC_KINEMATICS_SWING_CMD` | `/control/kinematics_swing_cmd_sequenced` | **注意**：实际指向 control_node 的时序化输出 |
| `ROS_TOPIC_KINEMATICS_TELESCOPIC_CMD` | `/control/kinematics_telescopic_cmd_sequenced` | **注意**：实际指向 control_node 的时序化输出 |
| `ROS_TOPIC_ADJUST_ROTATION_CMD` | `/control/adjust_rotation_cmd` | 前端微调指令 |
| `ROS_TOPIC_ADJUST_SWING_CMD` | `/control/adjust_swing_cmd` | 前端微调指令 |
| `ROS_TOPIC_ADJUST_TELESCOPIC_CMD` | `/control/adjust_telescopic_cmd` | 前端微调指令 |
| `ROS_TOPIC_ARM_CMD_VEL` | `/arm/cmd_vel` | 最终硬件控制指令 |
| `ROS_TOPIC_HARDWARE_ALL_FEEDBACK` | `/hardware/all_feedback` | 硬件原始反馈 |

---

## 三、节点-话题关系图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           前端/Web层                                   │
│  ┌──────────────────────────┐  ┌──────────────────────────────────┐   │
│  │ /frontend_pointcloud_topic│  │ /control/adjust_*_cmd           │   │
│  │   (点云JSON数据)          │  │   (前端微调指令)                │   │
│  └──────────┬───────────────┘  └───────────────┬──────────────────┘   │
└─────────────┼───────────────────────────────────┼─────────────────────┘
              │                                   │
              ▼                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        数据处理层                                      │
│  ┌──────────────────┐                    ┌──────────────────────────┐  │
│  │ data_process_node│                    │      control_node        │  │
│  │  点云处理/模块切分│                    │  时序控制核心           │  │
│  └────────┬─────────┘                    └──────────┬───────────────┘  │
│           │                                         │                   │
│           ▼                                         ▼                   │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │              /module_arm_task           /control/*_cmd_sequenced│    │
│  └───────────────┬───────────────────────┬─────────────────────────┘    │
│                  │                       │                               │
│                  ▼                       ▼                               │
│  ┌──────────────────┐          ┌──────────────────────────────┐        │
│  │ calculation_node  │          │       kinematics_node       │        │
│  │   最优托举点计算  │          │    运动学逆解/增量计算      │        │
│  └────────┬─────────┘          └──────────────┬───────────────┘        │
│           │                                  │                          │
│           └──────────────┬───────────────────┘                          │
│                          ▼                                             │
│                    /arm_alpha_beta                                     │
│                          │                                             │
└──────────────────────────┼─────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        轴控制层                                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐               │
│  │rotation_node│  │ swing_node  │  │telescopic_node  │               │
│  │   旋转轴控制 │  │   摆动轴控制│  │   伸缩轴控制    │               │
│  └──────┬──────┘  └──────┬──────┘  └────────┬────────┘               │
│         │               │                   │                         │
│         └───────────────┼───────────────────┘                         │
│                         ▼                                             │
│              /hardware/*_output                                       │
│                         │                                             │
└──────────────────────────┼─────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        反馈处理层                                      │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                     feedback_node                                │  │
│  │  硬件反馈解析 / 指令转发 / 数据存储                              │  │
│  └───────────────────────────┬──────────────────────────────────────┘  │
│                              │                                        │
│              ┌───────────────┼───────────────┐                        │
│              ▼               ▼               ▼                        │
│    /hardware/*_feedback  /arm/cmd_vel   /hardware/sensor_feedback     │
│              │               │                                        │
└──────────────┼───────────────┼────────────────────────────────────────┘
               │               │
               ▼               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        硬件桥接层                                      │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                     hardware_node                                │  │
│  │     STM32串口通信 / 数据解析 / SQLite存储                         │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 四、消息类型说明

| 消息类型            | 核心字段                                                  | 说明                 | 状态       |
| --------------- | ----------------------------------------------------- | ------------------ | -------- |
| `RotationCmd`   | `module_id`, `device_id`, `position[]`                | 旋转角度指令（度）        | ✅ 正在使用   |
| `SwingCmd`      | `module_id`, `device_id`, `position[]`                | 摆动角度指令（度）        | ✅ 正在使用   |
| `TelescopicCmd` | `module_id`, `device_id`, `position[]`                | 伸缩长度指令（mm）       | ✅ 正在使用   |
| `IntCmd`        | `module_id`, `device_id`, `position[]`                | 整数编码指令           | ✅ 正在使用   |
| `Feedback`      | `module_id`, `device_id`, `position[]`                | 原始硬件反馈           | ✅ 正在使用   |
| `SensorCmd`     | `id`, `module_id`, `device_id`, `position[]`          | 传感器数据            | ✅ 正在使用   |
| `GyroFeedback`  | `module_id`, `device_id`, `accel_x/y/z`, `gyro_x/y/z` | 陀螺仪数据            | ✅ 正在使用   |
| `Kinematics`    | `header`, `module_id`, `device_id`, `position[]`      | 坐标数据格式（预留接口）    | ⚠️ 未实际使用 |
| `String`        | `data`                                                | JSON格式字符串          | ✅ 正在使用   |

### Kinematics 消息类型说明

`Kinematics.msg` 定义了坐标数据格式，用于未来实现基于坐标（x, y, z）的运动控制功能：

```
std_msgs/Header header  # 标准头，用于时间同步和坐标系
uint8 module_id         # 模块编号(先默认为17)
uint8 device_id         # 为0
float64[] position      # 坐标数组，单位为mm
```

**目前使用状态**：
- `feedback_node.py` 导入但未实际使用
- `web_data_node.py` 中的相关代码已注释
- `test_c.py` 中使用的是 `Feedback` 类型而非 `Kinematics`

### TuoLuoYi 消息类型说明

`TuoLuoYi.msg` 定义了陀螺仪计算后的角度数据格式：

```
uint8 module_id         # 模块编号
uint8 device_id         # 设备编号
float64 swing           # 摆动角度（度）
float64 rotation        # 旋转角度（度）
float64 x               # X轴加速度
float64 y               # Y轴加速度
float64 z               # Z轴加速度
```

---

## 五、数据流路径

### 完整运动控制流程

```
前端点云 → data_process_node → /module_arm_task → calculation_node → /arm_alpha_beta
                                                                       │
                                                                       ▼
                                                            kinematics_node → /control/kinematics_*_cmd
                                                                       │
                                                                       ▼
                                                           control_node (三阶段时序控制)
                                                                       │
                        ┌──────────────────────────────────────────────┼──────────────────────────────────────────────┐
                        ▼                                              ▼                                              ▼
              /control/kinematics_rotation_cmd_sequenced    /control/kinematics_swing_cmd_sequenced    /control/kinematics_telescopic_cmd_sequenced
                        │                                              │                                              │
                        ▼                                              ▼                                              ▼
              rotation_node → /hardware/rotation_output    swing_node → /hardware/swing_output    telescopic_node → /hardware/telescope_output
                        │                                              │                                              │
                        └──────────────────────────────────────────────┼──────────────────────────────────────────────┘
                                                                       │
                                                                       ▼
                                                           feedback_node → /arm/cmd_vel
                                                                       │
                                                                       ▼
                                                           hardware_node → STM32串口
                                                                       │
                                                                       ▼
                                                           STM32 → /hardware/all_feedback → feedback_node
                                                                       │
                                                                       ▼
                                                     /hardware/*_feedback → 各轴节点 (角度闭环)
```

### 前端微调流程

```
前端调节指令 → /control/adjust_*_cmd → control_node → /control/adjust_*_cmd_sequenced → 对应轴节点 → 硬件
```

### 数据存储流程

```
轴节点执行指令 → sensor_log 表 (SQLite)
硬件反馈数据 → sensor_feedback 表 (SQLite)
陀螺仪数据 → tuo_luo_yi 节点处理 → 数据库
```

---

## 六、关键设计说明

### 1. 时序控制机制

`control_node` 实现了**三阶段时序执行**：

1. **旋转阶段**：所有机械臂同时旋转（约8秒）
2. **摆动阶段**：所有机械臂同时摆动（约8秒）
3. **伸缩阶段**：所有机械臂同时伸缩（带压力传感器监控）

### 2. Device ID 编码规则

| 设备类型  | Arm1 | Arm2 | Arm3 |
| ----- | ---- | ---- | ---- |
| 旋转控制  | 33   | 65   | 97   |
| 摆动控制  | 34   | 66   | 98   |
| 伸缩控制  | 35   | 67   | 99   |
| 旋转编码器 | 41   | 73   | 105  |
| 摆动编码器 | 42   | 74   | 106  |
| 伸缩编码器 | 43   | 75   | 107  |
| 压力传感器 | 49   | 81   | 113  |
| 陀螺仪   | 50   | 82   | 114  |

### 3. 模块编号规则

`module_id = (i + 1) * 16 + (j + 1)`，其中：

- `i`：X方向模块索引（从0开始）
- `j`：Y方向模块索引（从0开始）

---

## 七、节点列表

| 节点文件                     | 节点名称                      | 功能描述              |
| ------------------------ | ------------------------- | ----------------- |
| `data_process_node.py`   | `data_process_node`       | 点云处理与模块切分        |
| `calculation_node.py`    | `calculation_node`        | 最优托举点计算          |
| `kinematics_node.py`     | `kinematics_node`         | 运动学逆解与增量计算       |
| `control_node.py`        | `control_node`            | 时序控制核心节点（三阶段执行）   |
| `rotation_node.py`       | `rotation_node`           | 旋转轴功能节点          |
| `swing_node.py`          | `swing_node`              | 摆动轴功能节点          |
| `telescopic_node.py`     | `telescopic_node`         | 伸缩轴功能节点          |
| `sensor_control_node.py` | `sensor_control_node`     | 压力传感器控制（立即响应模式）    |
| `feedback_node.py`       | `feedback_node`           | 反馈处理与指令转发         |
| `hardware_node.py`       | `hardware_node`           | STM32硬件桥接         |
| `tuo_luo_yi.py`          | `tuo_luo_yi`              | 陀螺仪数据解析与角度计算      |
| `softstop_node.py`       | `softstop_node`           | 急停控制（device_id=1触发） |
| `module_confirme_node.py` | `module_confirme_node`   | 模块确认控制            |


```
kinematics_node (发布) 
    → /control/kinematics_rotation_cmd
    → control_node (订阅并时序化后发布)
    → /control/kinematics_rotation_cmd_sequenced
    → rotation_node (订阅)
    → /hardware/rotation_output
    → feedback_node (订阅)
    → /arm/cmd_vel
    → hardware_node → STM32
```