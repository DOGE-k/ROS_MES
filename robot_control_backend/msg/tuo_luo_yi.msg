std_msgs/Header header
uint8 module_id          # 模块ID
uint8 device_id          # 陀螺仪设备ID
float64 swing_angle      # 摆动角（度），前倾为正
float64 rotation_angle   # 旋转角（度），顺时针为正
float64 x                # 末端在世界坐标系下的 X 坐标 (cm)
float64 y                # 末端在世界坐标系下的 Y 坐标 (cm)
float64 z                # 末端在世界坐标系下的 Z 坐标 (cm)