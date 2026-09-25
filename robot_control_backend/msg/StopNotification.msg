# StopNotification.msg —— V2 CAN 停止通知事件
std_msgs/Header header      # 标准头
uint8 module_id             # 模块号
uint16 device_id            # V2 轴号 AXIS：1~20（device_id 即 axis）
uint8 stop_reason           # 1=到位 2=急停 3=指令停止 4=限位 5=故障 6=看门狗
uint8 output_level          # 停止瞬间输出档位
