# VacuumLoss.msg —— V2 吸盘失压事件（高优先级 PRI=0）
std_msgs/Header header      # 标准头
uint8 module_id             # 模块号
uint16 device_id            # V2 臂级 AXIS：21~25（臂号=device_id-20，device_id 即 axis）
int32 pressure_raw          # 失压时压力原始值
uint16 loss_threshold       # 失压判定阈值
