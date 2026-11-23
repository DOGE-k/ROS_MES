# SegConfirm.msg —— 绑定确认（hardware_node → 模块确认节点）
# 新固件绑定成功后模块会回两帧，本消息按 arm 字段区分：
#   arm == 0：组号确认帧 0x15BC0050，data[7]=(SEG<<4)|Result → seg/result 有效
#   arm 1~5：臂位确认帧 0x15BC0060，data[7]=(ARM<<4)|AxisBase → arm/axis_base 有效（seg 填 15 占位）
std_msgs/Header header
uint64 uid56            # 设备 UID 低 56 位
uint8 seg               # 组号确认帧：设备写入的 SEG；臂位确认帧：填 15（无效占位）
uint8 result            # 组号确认帧：0=绑定成功，其他=失败；臂位确认帧：无意义
uint8 arm               # 臂位确认帧：臂位 1~5；组号确认帧：填 0
uint8 axis_base         # 臂位确认帧：本臂起始全局AXIS（1/4/7/10/13）；组号确认帧：填 0
