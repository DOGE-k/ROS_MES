# AxisFault.msg —— V2 轴故障事件
std_msgs/Header header      # 标准头
uint8 module_id             # 模块号
uint16 device_id            # V2 轴号 AXIS：1~20（device_id 即 axis）
uint16 fault_bits           # bit0堵转 bit1电机无响应 bit2编码器异常 bit3上限位 bit4下限位 bit5位置超差 bit6驱动故障
uint8 local_action          # 1=已失能输出并清方向脚
uint8 detail                # 详细故障代码
uint16 duration_ms          # 故障持续时长（ms）
