# 反馈的数据格式（压力传感器除外）
std_msgs/Header header  # 标准头，用于时间同步和坐标系
uint8 module_id         # 模块编号
uint16 device_id        # V2 寻址单元 AXIS：1~20=轴号 21~25=臂级（device_id 即 axis）
float64[] position      # V2: 位置量为相对角度（0.01°），不再使用编码器计数
