# 摆动轴的数据格式
std_msgs/Header header  # 标准头，用于时间同步和坐标系
uint8 module_id       # 模块编号(先默认为17)
uint8 device_id       #这里来指代要执行的部件,例如34指第一个机械臂的摆动轴
float64[] position      # 摆动轴角度，单位：编码
