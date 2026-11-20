# 旋转轴的数据格式
std_msgs/Header header  # 标准头，用于时间同步和坐标系
uint8 module_id         # 模块编号(先默认为17)
uint16 device_id        # V2 旋转轴 J1：AXIS=1,4,7,10,13（device_id 即轴号）
float64[] position      # 旋转相对增量角度，单位：度（正=逆时针；轴节点检查限位后原样透传增量）
uint64 request_id       # 应用层回执ID：>0 时 control_node 收到微调后回 /control/adjust_ack；0=不要求回执（图纸逆解等默认0）
