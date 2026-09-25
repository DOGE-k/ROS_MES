# CmdAck.msg —— V2 命令应答（接受/轴忙/基准无效/越界/故障/急停锁存）
std_msgs/Header header      # 标准头
uint8 module_id             # 模块号
uint16 device_id            # V2 轴号 AXIS：1~20（device_id 即 axis）
uint8 ack_msg               # 对应的下行命令 MSG 号
uint8 result                # 0=接受 1=轴忙 2=基准无效 3=参数越界 4=轴故障 5=急停锁存
uint8 detail                # 详细信息（越界轴号等）
