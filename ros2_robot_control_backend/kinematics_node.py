import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from std_msgs.msg import Float64MultiArray
import numpy as np

class KinematicsNode(Node):
    def __init__(self):
        super().__init__("kinematics_node")
        self.cb_group = ReentrantCallbackGroup()

        self.sub_ab = self.create_subscription(
            Float64MultiArray,
            "/alpha_beta",
            self.ab_callback,
            10,
            callback_group=self.cb_group
        )
        # 输出关节增量：[旋转角(deg),摆动角(deg),伸缩量(mm)]
        self.pub_joint_inc = self.create_publisher(Float64MultiArray, "/joint_increment", 10)

        # ===== 修正为任务要求阈值 =====
        self.limit_rot = 180.0     # 旋转 ±180°
        self.limit_swing = 15.0    # 摆动 ±15°
        self.limit_extend = 3.0    # 伸缩 ±3 mm

        self.get_logger().info("kinematics_node 启动，等待αβ输入")

    def solve_3dof(self, alpha, beta):
        # 3DOF逆解模型，输入α、beta(rad)，输出三个关节增量
        rot_deg = np.rad2deg(alpha)
        swing_deg = np.rad2deg(beta)
        extend_mm = 120.0 * np.cos(beta)
        return rot_deg, swing_deg, extend_mm

    def ab_callback(self, msg):
        try:
            alpha = msg.data[0]
            beta = msg.data[1]
            rot, swing, extend = self.solve_3dof(alpha, beta)

            # 增量钳位
            rot_clamp = np.clip(rot, -self.limit_rot, self.limit_rot)
            swing_clamp = np.clip(swing, -self.limit_swing, self.limit_swing)
            extend_clamp = np.clip(extend, -self.limit_extend, self.limit_extend)

            out_msg = Float64MultiArray()
            out_msg.data = [rot_clamp, swing_clamp, extend_clamp]
            self.pub_joint_inc.publish(out_msg)
            self.get_logger().info(
                f"逆解输出：旋转={rot_clamp:.2f}°,摆动={swing_clamp:.2f}°,伸缩={extend_clamp:.2f}mm"
            )
        except Exception as e:
            self.get_logger().error(f"逆解计算异常：{str(e)}")

def main(args=None):
    rclpy.init(args=args)
    node = KinematicsNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == "__main__":
    main()

