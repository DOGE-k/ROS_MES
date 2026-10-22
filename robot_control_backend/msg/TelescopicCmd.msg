# 伸长轴的数据格式
std_msgs/Header header  # 标准头，用于时间同步和坐标系
uint8 module_id         # 模块编号(先默认为17)
uint16 device_id        # V2 伸缩轴 J3：AXIS=3,6,9,12,15（device_id 即轴号）
float64[] position      # 伸缩相对增量，单位：mm（轴节点累加后按 0~30mm 检查，超限丢弃，未超限换算为 0.01°；注意反馈话题中本字段为角度°）
