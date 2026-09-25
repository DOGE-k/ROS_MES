# AxisStatus.msg —— V2 CAN 轴状态字（9位状态字）
std_msgs/Header header      # 标准头
uint8 module_id             # 模块号
uint16 device_id            # V2 轴号 AXIS：1~20（device_id 即 axis）
uint16 status_bits          # bit0使能 bit1运行 bit2到位 bit3上限位 bit4下限位 bit5故障 bit6轴忙 bit7急停锁存 bit8基准有效
uint8 axis_state            # 0=IDLE 1=RUN 2=ARRIVE 3=FAULT
uint8 base_valid            # 0=基准无效 1=基准有效
