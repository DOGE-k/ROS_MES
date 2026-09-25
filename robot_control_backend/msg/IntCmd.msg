# 指令/反馈的数据格式(压力传感器除外)
std_msgs/Header header  # 标准头，用于时间同步和坐标系
uint8 module_id         # 模块编号(先默认为17)
uint16 device_id        # V2 寻址单元 AXIS：0=系统级 1~20=轴号(4轴ID布局,5臂) 21~25=臂级(臂号=device_id-20)
int32[] position        # 传回来的数据
