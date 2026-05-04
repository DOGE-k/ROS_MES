#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import rospy
from robot_control_backend.msg import IntCmd
from std_msgs.msg import Header

def publish_test():
    rospy.init_node('test_data_publisher')
    pub = rospy.Publisher('/arm/cmd_vel', IntCmd, queue_size=10)
    rate = rospy.Rate(1)  # 1秒发一次

    while not rospy.is_shutdown():
        msg = IntCmd()
        msg.header = Header()
        msg.header.stamp = rospy.Time.now()
        msg.module_id = 17
        msg.device_id = 33
        msg.position = [18000]
        pub.publish(msg)
        rospy.loginfo("发布数据：module=%d device_id=%d position=%s", 
                      msg.module_id, msg.device_id, msg.position) 
        rate.sleep()

if __name__ == '__main__':
    try:
        publish_test()
    except rospy.ROSInterruptException:
        pass
