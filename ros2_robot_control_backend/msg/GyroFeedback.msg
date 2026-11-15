# GyroFeedback.msg —— V2 IMU 为臂级传感器（AXIS 21~25）
std_msgs/Header header
uint8 module_id
uint16 device_id        # 臂级 IMU：AXIS=21~25（臂号=device_id-20），device_id 即 axis

# 线性加速度 (单位: m/s^2，由 hardware_node 按标定系数从 int16 换算)
float32 accel_x
float32 accel_y
float32 accel_z

# 角速度 (单位: °/s，由 hardware_node 按标定系数从 int16 换算)
float32 gyro_x
float32 gyro_y
float32 gyro_z
