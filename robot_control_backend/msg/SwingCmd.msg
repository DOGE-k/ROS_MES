# 摆动轴的数据格式
std_msgs/Header header  # 标准头，用于时间同步和坐标系
uint8 module_id         # 模块编号
uint16 device_id        # V2 摆动轴 J2：AXIS=2,5,8,11,14（device_id 即轴号）
float64[] position      # V2: 摆动相对增量角度，单位：度（轴节点累加后按 0~MAX_SWING_ANGLE 检查，超限丢弃）