import rclpy
from rclpy.node import Node
from sensor_msgs.msg import PointCloud2, PointField
import json
import struct
import os

class DataProcessNode(Node):
    def __init__(self):
        super().__init__("data_process_node")
        self.pub_cloud = self.create_publisher(PointCloud2, "zero_point_cloud", 10)
        self.timer = self.create_timer(0.5, self.timer_cb)

        self.json_path = "/home/suren/零件坐标绑定结果.json"
        self.points = []
        self.load_json()

    def load_json(self):
        if not os.path.exists(self.json_path):
            self.get_logger().error(f"文件不存在：{self.json_path}")
            return
        try:
            with open(self.json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 解析JSON结构：根对象 → "虚拟部件列表"
            part_list = data.get("虚拟部件列表", [])
            total = 0
            for part in part_list:
                coord_list = part.get("坐标列表", [])
                for pt in coord_list:
                    # 读取mm单位坐标
                    x_mm = float(pt["全局X(mm)"])
                    y_mm = float(pt["全局Y(mm)"])
                    z_mm = float(pt["全局Z(mm)"])
                    # mm → m，ROS标准单位米
                    x = x_mm / 1000.0
                    y = y_mm / 1000.0
                    z = z_mm / 1000.0
                    self.points.append([x, y, z])
                    total += 1

            self.get_logger().info(f"✅成功加载 {total} 个零点坐标(已毫米转米)")

        except Exception as e:
            self.get_logger().error(f"读取json失败：{str(e)}")

    def timer_cb(self):
        if len(self.points) == 0:
            return
        msg = PointCloud2()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "base_link"

        fields = [
            PointField(name="x", offset=0, datatype=PointField.FLOAT32, count=1),
            PointField(name="y", offset=4, datatype=PointField.FLOAT32, count=1),
            PointField(name="z", offset=8, datatype=PointField.FLOAT32, count=1),
        ]
        msg.fields = fields
        msg.height = 1
        msg.width = len(self.points)
        msg.is_bigendian = False
        msg.point_step = 12
        msg.row_step = msg.point_step * msg.width
        buf = b""
        for p in self.points:
            buf += struct.pack("fff", p[0], p[1], p[2])
        msg.data = buf
        msg.is_dense = True
        self.pub_cloud.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    node = DataProcessNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == "__main__":
    main()

