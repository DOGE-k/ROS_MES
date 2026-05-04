#!/usr/bin/env python3
import rospy
import math
from std_msgs.msg import Header
from robot_control_backend.msg import (
    Kinematics,
    RotationCmd,
    SwingCmd,
    TelescopicCmd
)

class IKCalculationNode:
    def __init__(self):
        rospy.init_node('ik_calculation_node', anonymous=True)

        self.coord_sub = rospy.Subscriber(
            '/control/kinematics_pose',
            Kinematics,
            self.coordinate_callback,
            queue_size=10
        )
        self.rotation_pub = rospy.Publisher(
            '/control/kinematics_rotation_cmd',
            RotationCmd,
            queue_size=10
        )
        self.swing_pub = rospy.Publisher(
            '/control/kinematics_swing_cmd',
            SwingCmd,
            queue_size=10
        )
        self.telescopic_pub = rospy.Publisher(
            '/control/kinematics_telescopic_cmd',
            TelescopicCmd,
            queue_size=10
        )

        self.ENC_MID = 15000
        self.ENC_MIN = 580
        self.ENC_MAX = 29420
        self.DEG_PER_TICK = 0.01248

        self.MIN_LENGTH = 50.0
        self.MAX_LENGTH = 500.0

        rospy.loginfo("✅ 逆运动学节点已启动（中位15000，顺时针+）")

    def coordinate_callback(self, msg):
        if msg.device_id != 0:
            rospy.logwarn(" 非坐标指令，跳过")
            return

        if len(msg.position) < 3:
            rospy.logwarn("  需要 [x,y,z] 坐标")
            return

        x = msg.position[0]
        y = msg.position[1]
        z = msg.position[2]

        try:
            # ----------------------
            # 水平距离（防零值）
            # ----------------------
            horizontal = math.sqrt(x**2 + y**2)

            # ----------------------
            # 旋转轴（顺时针+ 已修复）
            # ----------------------
            if horizontal < 1e-6:
                theta1_deg = 0.0
            else:
                theta1 = math.atan2(y, x)
                theta1_deg = math.degrees(theta1)

            # ----------------------
            # 俯仰角（正确）
            # ----------------------
            if horizontal < 1e-6:
                theta2_deg = 0.0
            else:
                theta2 = math.atan2(z, horizontal)
                theta2_deg = math.degrees(theta2)

            # 总长度
            L = math.sqrt(x**2 + y**2 + z**2)

            # ======================
            # ✅ 关键修复：顺时针为正
            # ======================
            target_rot_enc = self.ENC_MID - int(theta1_deg / self.DEG_PER_TICK)
            target_swing_enc = self.ENC_MID + int(theta2_deg / self.DEG_PER_TICK)

            # 限位
            target_rot_enc = max(self.ENC_MIN, min(target_rot_enc, self.ENC_MAX))
            target_swing_enc = max(self.ENC_MIN, min(target_swing_enc, self.ENC_MAX))
            L = max(self.MIN_LENGTH, min(L, self.MAX_LENGTH))

            # 发布旋转轴
            rot_msg = RotationCmd()
            rot_msg.header = Header()
            rot_msg.header.stamp = rospy.Time.now()
            rot_msg.module_id = 17
            rot_msg.device_id = 33
            rot_msg.position = [target_rot_enc]
            self.rotation_pub.publish(rot_msg)
            rospy.sleep(8)

            # 发布摆动轴
            swing_msg = SwingCmd()
            swing_msg.header = Header()
            swing_msg.header.stamp = rospy.Time.now()
            swing_msg.module_id = 17
            swing_msg.device_id = 34
            swing_msg.position = [target_swing_enc]
            self.swing_pub.publish(swing_msg)
            rospy.sleep(8)  
            # 伸缩轴
            tel_msg = TelescopicCmd()
            tel_msg.header = Header()
            tel_msg.header.stamp = rospy.Time.now()
            tel_msg.module_id = 17
            tel_msg.device_id = 35
            tel_msg.position = [L]
            self.telescopic_pub.publish(tel_msg)

            rospy.loginfo(f"-------------------------------------------------")
            rospy.loginfo(f"旋转角度(顺时针+): {theta1_deg:+.2f}° → 编码: {target_rot_enc}")
            rospy.loginfo(f"摆动角度: {theta2_deg:+.2f}° → 编码: {target_swing_enc}")
            rospy.loginfo(f"伸长长度: {L:.2f}mm")
            rospy.loginfo(f"-------------------------------------------------")

        except Exception as e:
            rospy.logerr(f"解算错误：{str(e)}")

if __name__ == '__main__':
    try:
        ik_node = IKCalculationNode()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass