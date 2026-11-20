# 微调指令应用层回执：control_node 收到前端微调后发布，后端据此确认"指令已送达控制节点"
std_msgs/Header header
uint8 module_id       # 原样回显微调指令的模块号
uint16 device_id      # 原样回显微调轴号
uint64 request_id     # 原样回显微调指令的 request_id，后端用它匹配在途请求
uint8 result          # 0=已接收并转发到轴节点；1=device_id 非法；2=处理异常
string message        # 结果描述（拒绝原因等，便于后端提示）
