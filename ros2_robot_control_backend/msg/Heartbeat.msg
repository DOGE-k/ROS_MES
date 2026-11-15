# Heartbeat.msg —— V2 CAN 节点心跳（DLC=8，节点级报文 AXIS=0）
std_msgs/Header header      # 标准头
uint8 module_id             # 模块号（SEG）
uint16 node_id            # 节点级：填 CAN NODE 号（0=广播 1=主控 2~21=驱动），与轴/臂级 1~25 寻址区分
uint8 state                 # 0=BOOT 1=IDLE 2=RUN 3=FAULT
uint32 run_axis_mask        # 运行轴掩码（bit0..bit19 对应轴1~轴20）
uint32 base_valid_mask      # 基准有效掩码（bit0..bit19 对应轴1~轴20）
