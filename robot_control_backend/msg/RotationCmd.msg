# 旋转轴的数据格式
std_msgs/Header header  # 标准头，用于时间同步和坐标系
uint8 module_id         # 模块编号(先默认为17)
uint16 device_id        # V2 旋转轴 J1：AXIS=1,5,9,13,17（device_id 即轴号）
float64[] position      # 旋转相对增量角度，单位：度（正=逆时针；轴节点与当前反馈角累加为绝对目标后下发）
