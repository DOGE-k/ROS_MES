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

        # ==========================
        # ✅ 修复话题不匹配问题
        # ==========================
        self.coord_sub = rospy.Subscriber(
            '/control/kinematics_pose',
            Kinematics,
            self.coordinate_callback,
            queue_size=10
        )

        # 发布者
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

        # ==========================
        # ✅ 你的硬件真实参数
        # ==========================
        self.ENC_MID = 15000        # 中间位（绝对中位）
        self.ENC_MIN = 580          # 0x0244
        self.ENC_MAX = 29420        # 0x72EC
        self.DEG_PER_TICK = 0.01248  # 1编码 = 0.01248°

        # 伸缩轴限位
        self.MIN_LENGTH = 50.0
        self.MAX_LENGTH = 500.0

        rospy.loginfo("✅ 逆运动学节点已启动（中位15000，右加左减）")

    def coordinate_callback(self, msg):
        if msg.device_id != 0:
            rospy.logwarn("⚠️  非坐标指令，跳过")
            return

        if len(msg.position) < 3:
            rospy.logwarn("⚠️  需要 [x,y,z] 坐标")
            return

        x = msg.position[0]
        y = msg.position[1]
        z = msg.position[2]

        try:
            # ----------------------
            # 逆运动学计算角度
            # ----------------------
            theta1 = math.atan2(y, x)
            theta1_deg = math.degrees(theta1)

            L = math.sqrt(x**2 + y**2 + z**2)
            if L < 1e-6:
                theta2_deg = 0.0
            else:
                sin_theta2 = z / L
                sin_theta2 = max(min(sin_theta2, 1.0), -1.0)
                theta2_deg = math.degrees(math.asin(sin_theta2))

            # ----------------------
            # ✅ 角度 → 编码器值（中位15000基准）
            # ----------------------
            # 增加 = 向右（+）
            # 减少 = 向左（-）
            target_rot_enc = self.ENC_MID + int(theta1_deg / self.DEG_PER_TICK)
            target_swing_enc = self.ENC_MID + int(theta2_deg / self.DEG_PER_TICK)

            # ----------------------
            # ✅ 硬件硬限位（绝对不能超）
            # ----------------------
            target_rot_enc = max(self.ENC_MIN, min(target_rot_enc, self.ENC_MAX))
            target_swing_enc = max(self.ENC_MIN, min(target_swing_enc, self.ENC_MAX))
            L = max(self.MIN_LENGTH, min(L, self.MAX_LENGTH))

            # ----------------------
            # 下发给下位机（编码值）
            # ----------------------
            # 旋转轴
            rot_msg = RotationCmd()
            rot_msg.header = Header()
            rot_msg.header.stamp = rospy.Time.now()
            rot_msg.module_id = 17
            rot_msg.device_id = 33
            rot_msg.position = [target_rot_enc]  # ✅ 直接发编码值
            self.rotation_pub.publish(rot_msg)

            # 摆动轴
            swing_msg = SwingCmd()
            swing_msg.header = Header()
            rot_msg.header.stamp = rospy.Time.now()
            swing_msg.module_id = 17
            swing_msg.device_id = 34
            swing_msg.position = [target_swing_enc]  # ✅ 直接发编码值
            self.swing_pub.publish(swing_msg)

            # 伸缩轴
            tel_msg = TelescopicCmd()
            tel_msg.header = Header()
            tel_msg.header.stamp = rospy.Time.now()
            tel_msg.module_id = 17
            tel_msg.device_id = 35
            tel_msg.position = [L]
            self.telescopic_pub.publish(tel_msg)

            rospy.loginfo(f"-------------------------------------------------")
            rospy.loginfo(f"旋转角度: {theta1_deg:+.2f}° → 编码: {target_rot_enc}")
            rospy.loginfo(f"摆动角度: {theta2_deg:+.2f}° → 编码: {target_swing_enc}")
            rospy.loginfo(f"伸长长度: {L:.2f}mm")
            rospy.loginfo(f"-------------------------------------------------")

        except Exception as e:
            rospy.logerr(f"❌ 解算错误：{str(e)}")

if __name__ == '__main__':
    try:
        ik_node = IKCalculationNode()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass