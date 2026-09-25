# ArriveNotification.msg —— V2 CAN 到位通知事件（Angle+PosError+StatusBits+Flags）
std_msgs/Header header      # 标准头
uint8 module_id             # 模块号
uint16 device_id            # V2 轴号 AXIS：1~20（device_id 即 axis；0.01° 角度随帧携带，无需节点号）
int32 angle                 # 到位角度（0.01°）
int16 pos_error             # 到位误差（0.01°）
uint8 status_bits           # 轴状态字低 8 位：bit0=使能 bit1=运行 **bit2=到位** bit3=上限位 bit4=下限位 bit5=故障 bit6=轴忙 bit7=急停锁存
uint8 flags                 # bit0=基准有效 bit1=限位内
