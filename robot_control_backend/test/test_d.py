#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import rospy
from robot_control_backend.msg import IntCmd  # 导入你的IntCmd消息类型

def pub_module_cmd_test():
    # 初始化ROS节点（命名为test_module_cmd_publisher）
    rospy.init_node('test_module_cmd_publisher', anonymous=True)
    
    # 创建发布者，发布到/control/module_cmd话题，消息类型IntCmd
    pub = rospy.Publisher('/control/module_cmd', IntCmd, queue_size=10)
    
    # 等待1秒，确保发布者完成初始化
    rospy.sleep(1)
    
    # 构造模块确认指令消息
    cmd_msg = IntCmd()
    cmd_msg.header.stamp = rospy.Time.now()  # 设置时间戳
    cmd_msg.module_id = 17                   # 模块ID（和你的硬件一致）
    cmd_msg.device_id = 0                    # 触发module节点的核心标识（必须为0）
    cmd_msg.position = [0]                   # 初始位置值
    
    # 发布指令
    pub.publish(cmd_msg)
    rospy.loginfo("✅ 测试指令已发布到 /control/module_cmd")
    rospy.loginfo(f"   - module_id: {cmd_msg.module_id}")
    rospy.loginfo(f"   - device_id: {cmd_msg.device_id}")
    rospy.loginfo(f"   - position: {cmd_msg.position}")
    
    # 等待0.5秒，确保消息发送完成
    rospy.sleep(0.5)
    rospy.loginfo("📌 测试发布完成！")

if __name__ == '__main__':
    try:
        pub_module_cmd_test()
    except rospy.ROSInterruptException:
        rospy.logerr("❌ 测试节点被中断")
    except Exception as e:
        rospy.logerr(f"❌ 发布失败：{str(e)}")