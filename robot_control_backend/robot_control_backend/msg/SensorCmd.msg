# 压力传感器的数据格式
std_msgs/Header header  # 标准头，用于时间同步和坐标系
uint8 id                # 用于自增，防止重复
uint8 module_id         # 模块编号(先默认为17)
uint8 device_id         # 这里来指代要执行的部件,例如49指第一个机械臂的压力传感器
float64[] position      # 压力传感器数据，单位：N