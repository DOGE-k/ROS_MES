import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from sensor_msgs.msg import PointCloud2
from std_msgs.msg import Float64MultiArray
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import struct

class CalculationNode(Node):
    def __init__(self):
        super().__init__("calculation_node")
        self.cb_group = ReentrantCallbackGroup()
        # 4线程池，需求指定
        self.executor_pool = ThreadPoolExecutor(max_workers=4)

        self.sub_cloud = self.create_subscription(
            PointCloud2,
            "/zero_point_cloud",
            self.cloud_callback,
            10,
            callback_group=self.cb_group
        )
        # 发布 alpha, beta 两个角度 [alpha, beta]
        self.pub_alpha_beta = self.create_publisher(Float64MultiArray, "/alpha_beta", 10)

        self.get_logger().info("calculation_node 启动，等待点云输入")

    def parse_pointcloud2(self, msg: PointCloud2):
        """PointCloud2转numpy数组 x,y,z"""
        point_step = msg.point_step
        data = np.frombuffer(msg.data, dtype=np.uint8)
        points = []
        for i in range(msg.width):
            offset = i * point_step
            x = struct.unpack_from("f", data, offset + 0)[0]
            y = struct.unpack_from("f", data, offset + 4)[0]
            z = struct.unpack_from("f", data, offset + 8)[0]
            points.append([x, y, z])
        return np.array(points)

    def calc_alpha_beta(self, points):
        # ========== 策略链：垂直区域 → 水平平面 → 曲面自适应 → 默认 ==========
        # 1. 垂直区域判定
        z_mean = np.mean(points[:,2])
        z_std = np.std(points[:,2])
        if z_std > 0.08:
            self.get_logger().info("策略：垂直区域")
            alpha = np.arctan2(np.mean(points[:,1]), np.mean(points[:,0]))
            beta = np.pi / 2.0
            return alpha, beta

        # 2. 水平平面判定
        if z_std < 0.005:
            self.get_logger().info("策略：水平平面")
            alpha = np.arctan2(np.mean(points[:,1]), np.mean(points[:,0]))
            beta = 0.0
            return alpha, beta

        # 3. 曲面自适应策略
        self.get_logger().info("策略：曲面自适应")
        center = np.mean(points, axis=0)
        dist = np.linalg.norm(center)
        lift_angle = np.arctan2(center[2], np.sqrt(center[0]**2 + center[1]**2))
        score = dist * 0.6 + lift_angle * 0.4
        self.get_logger().info(f"曲面得分={score:.3f}，距离={dist:.3f},抬升角={lift_angle:.3f}")
        alpha = np.arctan2(center[1], center[0])
        beta = lift_angle
        return alpha, beta

    def cloud_callback(self, msg):
        # 丢进线程池，避免阻塞ROS回调
        self.executor_pool.submit(self.work_task, msg)

    def work_task(self, msg):
        try:
            pts = self.parse_pointcloud2(msg)
            alpha, beta = self.calc_alpha_beta(pts)
            msg_out = Float64MultiArray()
            msg_out.data = [float(alpha), float(beta)]
            self.pub_alpha_beta.publish(msg_out)
            self.get_logger().info(f"输出 α={alpha:.3f} rad , β={beta:.3f} rad")
        except Exception as e:
            self.get_logger().error(f"计算异常：{str(e)}")

def main(args=None):
    rclpy.init(args=args)
    node = CalculationNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == "__main__":
    main()
