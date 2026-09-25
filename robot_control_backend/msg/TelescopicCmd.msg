# 伸长轴的数据格式
std_msgs/Header header  # 标准头，用于时间同步和坐标系
uint8 module_id         # 模块编号(先默认为17)
uint16 device_id        # V2 伸缩轴 J4：AXIS=4,8,12,16,20（device_id 即轴号，J3 空置）
float64[] position      # 伸缩相对增量，单位：mm（轴节点与当前反馈长度累加，再换算为绝对角度 0.01°；注意反馈话题中本字段为角度°）
