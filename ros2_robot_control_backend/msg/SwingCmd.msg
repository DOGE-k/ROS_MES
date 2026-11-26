# SwingCmd.msg —— 摆动轴 J2（命令 / 反馈共用同一类型，按话题区分）
# 依据《msg消息格式设计》§4 通用字段规范、§5.1 轴类（device_id ∈ 1~15）
std_msgs/Header header  # 标准头；frame_id=module_{SEG}，用于时间同步和坐标系
uint16 module_id        # CAN SEG 工位组号：0~14（不再表示业务模块号 17，也不装坐标）
uint16 device_id        # 摆动轴寻址单元 AXIS：2,5,8,11,14 = (arm-1)*3+2，arm=1~5；device_id 即轴号
float64[] position      # 命令话题：相对增量角度（度），绝对限位 SWING_MIN_ANGLE(-15)~MAX_SWING_ANGLE(+15)，负为回正方向，delta 限幅 ±15°
                        # 反馈话题：实测绝对角度（度），由 CAN 0.01° 换算
# 校验（发布/接收前必过）：module_id ∈ 0..14；device_id ∈ 1..15，越界静默丢弃
