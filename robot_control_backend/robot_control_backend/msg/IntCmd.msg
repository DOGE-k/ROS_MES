# 反馈的数据格式(压力传感器除外)
std_msgs/Header header  # 标准头，用于时间同步和坐标系
uint8 module_id         # 模块编号(先默认为17)
uint8 device_id         # 这里来指代反馈的部件,例如41指第一个机械臂的旋转轴的编码器;42指旋摆动的编码器;43指伸长轴的编码器
int32[] position        # 传回来的数据