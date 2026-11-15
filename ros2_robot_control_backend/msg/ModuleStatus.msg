# ModuleStatus.msg —— 模块状态查询应答（hardware_node → 模块确认节点/后端）
# 对应 CAN 应答帧 ID = 0x00002060 + (SEG<<18)，DLC=8
#   data[0]=协议版本(1)  data[1]=SEG(0xFF=未绑定)  data[2]=(ARM<<4)|AxisBase
#   data[3]=电机存在掩码  data[4]=电机就绪掩码  data[5]=模块状态  data[6..7]=Token低16位
std_msgs/Header header
uint8 module_id         # 帧 ID 的 SEG 位域（模块号）
uint8 seg               # data[1]：组号，0xFF 表示未绑定
uint8 arm               # data[2] 高 4 位：臂位 1~5
uint8 axis_base         # data[2] 低 4 位：本臂起始全局AXIS（1/4/7/10/13）
uint8 exist_mask        # 电机存在掩码：bit0~2 = 电机1~3（三电机正常 0x07）
uint8 ready_mask        # 电机就绪掩码：bit0~2 = 电机1~3（三电机正常 0x07）
uint8 module_state      # bit0=已绑定 bit1=允许运动 bit2=急停锁存 bit3=轴限位/编码器故障
uint16 token            # 请求 Token 低 16 位（用于应答匹配）
