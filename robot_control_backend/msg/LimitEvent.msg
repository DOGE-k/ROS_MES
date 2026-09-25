# LimitEvent.msg —— V2 限位事件
std_msgs/Header header      # 标准头
uint8 module_id             # 模块号
uint16 device_id            # V2 轴号 AXIS：1~20（device_id 即 axis）
uint8 limit_type            # 1=上限位 2=下限位
uint8 output_level          # 触发时输出档位
