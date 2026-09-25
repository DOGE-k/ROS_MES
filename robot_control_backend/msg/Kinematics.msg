# 坐标的数据格式
std_msgs/Header header  # 标准头，用于时间同步和坐标系
uint8 module_id         # 模块编号(先默认为17)
uint16 device_id        # V2 寻址单元 AXIS：0=系统级 1~20=轴号 21~25=臂级
float64[] position      # 坐标数组，单位为mm
