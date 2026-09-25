# HomeStatus.msg —— V2 回零状态
std_msgs/Header header      # 标准头
uint8 module_id             # 模块号
uint16 device_id            # V2 轴号 AXIS：1~20（device_id 即 axis）
uint8 home_result           # 0=成功 1=失败 2=进行中
uint8 base_valid            # 0=基准无效 1=基准有效
int32 angle                 # 回零后角度（0.01°）
