# UidAnnounce.msg —— 会话式模块确认：F407 未编号宣告（hardware_node → 模块确认节点）
# 对应 CAN 帧 ID = 0x15BC0080 + (UID低4位 × 4)，DLC=8
std_msgs/Header header
uint8 device_type       # 设备类型（宣告帧 data[0]）
uint64 uid56            # 设备 UID 低 56 位（宣告帧 data[1..7]，大端）
uint8 slot              # 宣告槽位 0~15（由 (CAN_ID - 0x15BC0080) / 4 得出）
