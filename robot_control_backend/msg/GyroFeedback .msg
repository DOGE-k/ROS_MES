# GyroFeedback.msg
std_msgs/Header header
uint8 module_id
uint8 device_id

# 线性加速度 (单位推荐: g 或 m/s^2)
float32 accel_x
float32 accel_y
float32 accel_z

# 角速度 (单位推荐: °/s 或 rad/s)
float32 gyro_x
float32 gyro_y
float32 gyro_z