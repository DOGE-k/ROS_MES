# SegAssign.msg —— 组号+臂位绑定请求（模块确认节点 → hardware_node）
# 对应 CAN 帧 ID = 0x15BC0020，DLC=8，data[0..6]=UID低56位，data[7]=(SEG<<3)|(ARM-1)
std_msgs/Header header
uint64 target_uid56     # 目标设备 UID 低 56 位（必须等于宣告帧解析出的值）
uint8 seg               # 组号 0~14
uint8 arm               # 组内臂位 1~5（决定本臂占用的全局AXIS：(ARM-1)*3+1 ~ (ARM-1)*3+3）
