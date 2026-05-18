# robot_control_backend 整体流程图

## 🔄 数据流流程图

```mermaid
flowchart TD
    subgraph 前端层
        A[前端JSON数据]
    end
    
    subgraph 处理层
        B[data_process_node]
        C[calculation_node]
        D[kinematics_node]
    end
    
    subgraph 轴控制层
        E[rotation_node]
        F[swing_node]
        G[telescopic_node]
    end
    
    subgraph 传感器控制
        H[sensor_control_node]
    end
    
    subgraph 下位机
        I[机械臂执行器]
        J[压力传感器]
    end
    
    subgraph 时序控制
        K{间隔≥8秒?}
        L[延迟7秒]
    end

    %% 主数据流
    A -->|/frontend_pointcloud_topic| B
    B -->|/module_arm_task| C
    C -->|/arm_alpha_beta| D
    
    %% kinematics带间隔控制
    D --> K
    K -->|是| D_output[发布轴指令]
    K -->|否| D_wait[等待下一轮]
    
    D_output -->|/control/kinematics_rotation_cmd| E
    D_output -->|/control/kinematics_swing_cmd| F
    D_output -->|/control/kinematics_telescopic_cmd| G
    
    D_wait -.->|8秒后重新检查| K
    
    %% 轴节点触发传感器
    E -->|/control/sensor_cmd| L
    F -->|/control/sensor_cmd| L
    G -->|/control/sensor_cmd| L
    
    %% 传感器延迟发送
    L --> H
    
    %% 下发到下位机
    E -->|/hardware/rotation_output| I
    F -->|/hardware/swing_output| I
    G -->|/hardware/telescope_output| I
    H -->|/arm/cmd_vel| J

    %% 样式
    style A fill:#f9f,stroke:#333,stroke-width:2px
    style I fill:#9f9,stroke:#333,stroke-width:2px
    style J fill:#9f9,stroke:#333,stroke-width:2px
    style K fill:#ff9,stroke:#333,stroke-width:2px
    style L fill:#ff9,stroke:#333,stroke-width:2px
```

## ⏱️ 时序图

```mermaid
sequenceDiagram
    participant 前端 as 前端系统
    participant DP as data_process_node
    participant CAL as calculation_node
    participant KIN as kinematics_node
    participant ROT as rotation_node
    participant SEN as sensor_control_node
    participant HW as 下位机

    前端->>DP: /frontend_pointcloud_topic (JSON数据)
    DP->>CAL: /module_arm_task (处理后数据)
    CAL->>KIN: /arm_alpha_beta (最优托举点)
    
    Note over KIN: 检查间隔是否≥8秒
    
    alt 间隔≥8秒
        KIN->>ROT: /control/kinematics_rotation_cmd (旋转增量)
        KIN->>ROT: /control/kinematics_swing_cmd (摆动增量)
        KIN->>ROT: /control/kinematics_telescopic_cmd (伸缩增量)
        
        ROT->>HW: /hardware/rotation_output (轴指令)
        
        Note over ROT,SEN: 触发传感器节点
        ROT->>SEN: /control/sensor_cmd (触发信号)
        
        Note over SEN: 延迟7秒
        SEN->>HW: /arm/cmd_vel (传感器指令序列)
    else 间隔<8秒
        Note over KIN: 等待，8秒后重试
    end
```

## 📊 节点职责表

| 节点名称 | 核心职责 | 发布话题 | 订阅话题 |
|---------|---------|---------|---------|
| `data_process_node` | 点云数据处理 | `/module_arm_task` | `/frontend_pointcloud_topic` |
| `calculation_node` | 最优托举点计算 | `/arm_alpha_beta` | `/module_arm_task` |
| `kinematics_node` | 运动学解算+8秒间隔控制 | `/control/kinematics_*_cmd` | `/arm_alpha_beta` |
| `rotation_node` | 旋转轴控制 | `/hardware/rotation_output` | `/control/kinematics_rotation_cmd` |
| `swing_node` | 摆动轴控制 | `/hardware/swing_output` | `/control/kinematics_swing_cmd` |
| `telescopic_node` | 伸缩轴控制 | `/hardware/telescope_output` | `/control/kinematics_telescopic_cmd` |
| `sensor_control_node` | 压力传感器控制(7秒延迟) | `/arm/cmd_vel` | `/control/sensor_cmd` |

## ⚙️ 时序参数配置

| 参数 | 值 | 配置位置 | 作用 |
|------|-----|---------|------|
| `CYCLE_INTERVAL` | 8.0s | `rob_arm.env` | 每个机械臂的轴指令间隔 |
| `SENSOR_DELAY` | 7.0s | `rob_arm.env` | 轴指令后延迟发送传感器指令 |

## 🔍 执行流程图

```mermaid
flowchart LR
    A[开始] --> B[前端发送JSON数据]
    B --> C[点云处理]
    C --> D[最优托举点计算]
    D --> E{间隔≥8秒?}
    E -->|是| F[发送轴指令到三个轴节点]
    E -->|否| G[等待8秒]
    G --> E
    F --> H[轴节点下发指令到下位机]
    F --> I[触发传感器节点]
    I --> J[延迟7秒]
    J --> K[发送压力传感器指令]
    K --> L[下位机执行]
    L --> M[返回步骤D]
```

## 📝 运行逻辑总结

1. **前端输入**：发送JSON格式的点云数据到 `/frontend_pointcloud_topic`
2. **点云处理**：`data_process_node` 处理后发布到 `/module_arm_task`
3. **最优计算**：`calculation_node` 计算最优托举点发布到 `/arm_alpha_beta`
4. **运动学解算**：`kinematics_node` 进行运动学解算，**每8秒发送一条轴指令**
5. **轴控制**：三个轴节点接收指令并下发到下位机
6. **传感器触发**：轴节点发布触发信号到 `/control/sensor_cmd`
7. **延迟发送**：`sensor_control_node` 收到触发后**延迟7秒**发送压力传感器指令
8. **循环执行**：持续监听新指令，重复上述流程
