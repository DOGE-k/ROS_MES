cmake_minimum_required(VERSION 3.8)
project(robot_control_backend)

# ============ 1. ament 与消息生成 ============
find_package(ament_cmake REQUIRED)
find_package(std_msgs REQUIRED)
find_package(rosidl_default_generators REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/RotationCmd.msg"
  "msg/SwingCmd.msg"
  "msg/TelescopicCmd.msg"
  "msg/Feedback.msg"
  "msg/SensorCmd.msg"
  "msg/Kinematics.msg"
  "msg/IntCmd.msg"
  "msg/GyroFeedback.msg"
  "msg/TuoLuoYi.msg"
  "msg/Heartbeat.msg"
  "msg/AxisStatus.msg"
  "msg/ArriveNotification.msg"
  "msg/StopNotification.msg"
  "msg/CmdAck.msg"
  "msg/HomeStatus.msg"
  "msg/AxisFault.msg"
  "msg/LimitEvent.msg"
  "msg/VacuumLoss.msg"
  "msg/UidAnnounce.msg"
  "msg/SegAssign.msg"
  "msg/SegConfirm.msg"
  "msg/ModuleStatus.msg"
  DEPENDENCIES std_msgs
)

ament_export_dependencies(rosidl_default_runtime)

# ============ 2. 安装 Python 节点 ============
install(PROGRAMS
  scripts/calculation_node.py
  scripts/data_process_node.py
  scripts/kinematics_node.py
  scripts/feedback_node.py
  scripts/hardware_node.py
  scripts/control.py
  scripts/ros_control.py
  scripts/rosbridge_gateway.py
  DESTINATION lib/${PROJECT_NAME}
)

# ============ 3. 配置文件 ============
# 注意：节点内部用 os.path.join(os.path.dirname(__file__), '../rob_arm.env') 找配置，
# 从 install/lib/robot_control_backend/ 往上一级就是 install/lib/，
# 所以 rob_arm.env 必须装在 lib 下，节点才能读到（这一行不能改成 share）。
install(FILES rob_arm.env DESTINATION lib)
# 同时留一份在 share 下，方便日后改成 ament_index 读取
install(FILES rob_arm.env DESTINATION share/${PROJECT_NAME})

# ============ 4. launch ============
install(FILES launch/ros_robot.launch.py
  DESTINATION share/${PROJECT_NAME}/launch)

ament_package()
