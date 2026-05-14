# #!/usr/bin/env python3
# # -*- coding: utf-8 -*-
# import rospy
# import os
# import time
# import sqlite3
# import json
# from std_msgs.msg import Header
# from robot_control_backend.msg import IntCmd

# def load_env_config():
#     env_path = os.path.join(os.path.dirname(__file__), '../rob_arm.env')
#     if os.path.exists(env_path):
#         with open(env_path, 'r') as f:
#             for line in f:
#                 line = line.strip()
#                 if line and not line.startswith('#'):
#                     key, value = line.split('=', 1)
#                     os.environ[key] = value

# # ====================== 数据库：强制建表，绝对成功 ======================
# def setup_database():
#     # 直接用工作目录下的 ros_database.db，和节点A/B 完全一致
#     db_path = "ros_database.db"
    
#     # 线程安全，防止ROS报错
#     conn = sqlite3.connect(db_path, check_same_thread=False)
#     cursor = conn.cursor()

#     # 强制建表，不存在就创建
#     cursor.execute("""
#     CREATE TABLE IF NOT EXISTS sensor_logs (
#         Createtime DATETIME NOT NULL PRIMARY KEY DEFAULT CURRENT_TIMESTAMP,
#         creater_id INTEGER NOT NULL DEFAULT 1,
#         Work_ID INTEGER NOT NULL DEFAULT 1,
#         sensor_ID INTEGER NOT NULL,
#         isread INTEGER NOT NULL DEFAULT 2,
#         data TEXT NOT NULL,
#         del_flag INTEGER NOT NULL DEFAULT 0,
#         Notes TEXT NOT NULL
#     );
#     """)
#     conn.commit()
#     rospy.loginfo("✅ 数据库表 sensor_logs 已创建/已存在")
#     return conn

# # ====================== 写入数据库 ======================
# def log_sensor_state(conn, sensor_id, state, action_desc):
#     try:
#         cursor = conn.cursor()
#         data_json = json.dumps({"state": state}, ensure_ascii=False)
#         notes_json = json.dumps({"action": action_desc}, ensure_ascii=False)

#         cursor.execute("""
#         INSERT INTO sensor_logs (sensor_ID, data, Notes)
#         VALUES (?, ?, ?)
#         """, (sensor_id, data_json, notes_json))
#         conn.commit()
#         rospy.loginfo(f"✅ 数据库写入成功：sensor={sensor_id}, state={state}")
#     except Exception as e:
#         rospy.logerr(f"❌ 数据库写入失败：{e}")

# # ====================== 主节点 ======================
# class PressureSensorControlNode:
#     def __init__(self):
#         load_env_config()
#         rospy.init_node("pressure_sensor_control_node")
#         rospy.loginfo("✅ 压力传感器控制节点已启动")

#         # 话题
#         TOPIC_ARM_CMD_VEL = os.environ.get('ROS_TOPIC_ARM_CMD_VEL', '/arm/cmd_vel')
#         TOPIC_SENSOR_CMD = os.environ.get('ROS_TOPIC_SENSOR_CMD', '/control/sensor_cmd')
#         self.DEV_SENSOR = int(os.environ.get('DEV_SENSOR', 49))

#         # 发布&订阅
#         self.pub_sensor_cmd = rospy.Publisher(TOPIC_ARM_CMD_VEL, IntCmd, queue_size=10)
#         rospy.Subscriber(TOPIC_SENSOR_CMD, IntCmd, self.trigger_callback)

#         # 数据库（自动建表）
#         self.db_conn = setup_database()

#     def trigger_callback(self, msg):
#         rospy.loginfo("📩 收到触发指令，开始传感器采集")
#         mid = msg.module_id

#         # 等待机械臂到位
#         rospy.loginfo("⏳ 等待7秒...")
#         time.sleep(7)

#         # 开启传感器
#         cmd1 = IntCmd()
#         cmd1.header = Header(stamp=rospy.Time.now())
#         cmd1.module_id = mid
#         cmd1.device_id = self.DEV_SENSOR
#         cmd1.position = 1
#         self.pub_sensor_cmd.publish(cmd1)
#         log_sensor_state(self.db_conn, self.DEV_SENSOR, 1, "开启压力传感器")

#         time.sleep(0.5)

#         # 关闭传感器
#         cmd2 = IntCmd()
#         cmd2.header = Header(stamp=rospy.Time.now())
#         cmd2.module_id = mid
#         cmd2.device_id = self.DEV_SENSOR
#         cmd2.position = 0
#         self.pub_sensor_cmd.publish(cmd2)
#         log_sensor_state(self.db_conn, self.DEV_SENSOR, 0, "关闭压力传感器")

#         rospy.loginfo("🎉 传感器流程完成，数据已入库！")

#     def shutdown_hook(self):
#         self.db_conn.close()
#         rospy.loginfo("✅ 数据库连接已关闭")

# if __name__ == '__main__':
#     try:
#         node = PressureSensorControlNode()
#         rospy.on_shutdown(node.shutdown_hook)
#         rospy.spin()
#     except rospy.ROSInterruptException:
#         rospy.loginfo("❌ 节点已停止")