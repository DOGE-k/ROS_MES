# TelescopicCmd.msg —— 伸缩轴 J3（命令 / 反馈共用同一类型，按话题区分）
# 依据《msg消息格式设计》§4 通用字段规范、§5.1 轴类（device_id ∈ 1~15）
std_msgs/Header header  # 标准头；frame_id=module_{SEG}，用于时间同步和坐标系
uint16 module_id        # CAN SEG 工位组号：0~14（不再表示业务模块号 17，也不装坐标）
uint16 device_id        # 伸缩轴寻址单元 AXIS：3,6,9,12,15 = (arm-1)*3+3，arm=1~5；device_id 即轴号
float64[] position      # 命令话题：相对增量（mm），行程限位 -10~20mm（TELESCOPIC_MIN_MM~MAX_MM），正为向上（伸出），delta 限幅 ±20mm
                        # 反馈话题：实测长度（mm），CAN 字段为 0.01mm，由 feedback_node 换算
# 校验（发布/接收前必过）：module_id ∈ 0..14；device_id ∈ 1..15，越界静默丢弃
