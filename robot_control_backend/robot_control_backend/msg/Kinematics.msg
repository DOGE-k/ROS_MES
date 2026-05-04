# 坐标的数据格式
std_msgs/Header header  # 标准头，用于时间同步和坐标系
uint8 module_id         # 模块编号(先默认为17)
uint8 device_id         # 为0
float64[] position      # 坐标数组，单位为mm