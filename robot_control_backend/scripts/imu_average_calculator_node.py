#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
压力传感器平均值计算节点
- 订阅压力传感器原始数据中转话题
- 订阅采集触发话题，收到触发后采集5秒数据计算平均值
- 发布平均值到传感器反馈话题（供前端使用）
"""
import rospy
import os
import numpy as np
from std_msgs.msg import Header
from robot_control_backend.msg import SensorCmd, IntCmd

def load_env_config():
    """从 .env 文件加载配置"""
    env_path = os.path.join(os.path.dirname(__file__), '../rob_arm.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    os.environ[key] = value
        rospy.loginfo("✅ 已从 rob_arm.env 加载配置")

class PressureAverageCalculator:
    def __init__(self):
        """初始化平均值计算器"""
        load_env_config()
        rospy.init_node('pressure_average_calculator')
        
        # 仅从 rob_arm.env 读取静态配置（配置文件一改无需改代码，配置缺失则 KeyError 立即暴露）
        # 采集参数
        self.SAMPLE_WINDOW = float(os.environ['PRESSURE_SAMPLE_WINDOW'])
        self.WINDOW_SIZE = int(os.environ['PRESSURE_WINDOW_SIZE'])
        # V2：压力为臂级传感器，device_id 即 AXIS = 21 + arm_idx（21~25）
        arm_base = int(os.environ['CAN_SENSOR_ARM_BASE'])
        pressure_arm = int(os.environ['PRESSURE_SENSOR_ARM']) - 1
        self.DEV_SENSOR = arm_base + pressure_arm

        # 从 rob_arm.env 读取话题名
        TOPIC_SENSOR_RAW = os.environ['ROS_TOPIC_SENSOR_RAW']
        TOPIC_SENSOR_AVG = os.environ['ROS_TOPIC_SENSOR_AVG']
        TOPIC_SAMPLE_TRIGGER = os.environ['ROS_TOPIC_PRESSURE_SAMPLE_TRIGGER']

        # 当前采集上下文：runtime 值，只来自 trigger 消息，不走 env / 不硬编码
        self.current_module_id = None
        self.current_device_id = None

        # 数据缓存
        self.data_buffer = []  # 存储原始数据
        self.is_collecting = False  # 是否正在采集数据
        self.collect_start_time = None  # 采集开始时间
        
        # 订阅压力传感器原始数据话题
        self.sensor_sub = rospy.Subscriber(
            TOPIC_SENSOR_RAW,
            SensorCmd,
            self.sensor_callback
        )
        
        # 订阅采集触发话题
        self.trigger_sub = rospy.Subscriber(
            TOPIC_SAMPLE_TRIGGER,
            IntCmd,
            self.trigger_callback
        )
        
        # 发布平均值结果到传感器反馈话题
        self.avg_pub = rospy.Publisher(
            TOPIC_SENSOR_AVG,
            SensorCmd,
            queue_size=10
        )
        
        rospy.loginfo("🧮 压力传感器平均值计算节点已启动")
        rospy.loginfo(f"📥 订阅原始数据话题: {TOPIC_SENSOR_RAW}")
        rospy.loginfo(f"📥 订阅触发话题: {TOPIC_SAMPLE_TRIGGER}")
        rospy.loginfo(f"📤 发布平均值话题: {TOPIC_SENSOR_AVG}")
        rospy.loginfo(f"⏱️  采集窗口: {self.SAMPLE_WINDOW}秒 ({self.WINDOW_SIZE}个数据点)")
    
    def trigger_callback(self, msg):
        """
        采集触发回调函数

        关键约束：
        1. module_id 只取前端下发（IntCmd.module_id），**绝不**从 env 读取，也不硬编码；
           前端改了 module_id，本节点跟着走——不需要重启、不需要改代码。
        2. device_id 必须取触发消息中携带的值；若缺失/为 0 视为非法触发。
        """
        mid = int(msg.module_id)
        did = int(msg.device_id)

        if mid == 0 or did == 0:
            rospy.logwarn(f"⚠️ 触发消息 module_id={mid} / device_id={did} 无效，已拒绝本次采集")
            return

        self.current_module_id = mid
        self.current_device_id = did
        rospy.loginfo(f"📡 收到采集触发信号，module_id={mid}，device_id={did}")

        # 清空缓存，开始新的采集窗口
        self.data_buffer = []
        self.is_collecting = True
        self.collect_start_time = rospy.Time.now().to_sec()

        rospy.loginfo(f"⏱️  开始采集 {self.SAMPLE_WINDOW} 秒的压力传感器数据")
    
    def sensor_callback(self, msg):
        """
        传感器数据回调函数
        接收原始数据并缓存
        """
        # 如果正在采集数据，将数据加入缓存
        if self.is_collecting:
            current_time = rospy.Time.now().to_sec()
            
            # 检查是否超过采集窗口时间
            if current_time - self.collect_start_time >= self.SAMPLE_WINDOW:
                # 采集窗口结束，计算平均值并发布
                self.calculate_and_publish_average()
                self.is_collecting = False
                return
            
            # 将数据加入缓存
            if len(msg.position) > 0:
                # 采集期间 device_id 应与触发一致，不一致则 warn（多臂场景下可用于诊断）
                if (self.current_device_id is not None
                        and int(msg.device_id) != self.current_device_id):
                    rospy.logwarn_throttle(2.0,
                        f"⚠️ 采集期间收到 device_id={msg.device_id} 的原始数据"
                        f"（触发为 {self.current_device_id}），可能多臂数据串扰")
                self.data_buffer.append(msg.position[0])
                
                # 如果缓存超过窗口大小，移除最旧的数据
                if len(self.data_buffer) > self.WINDOW_SIZE:
                    self.data_buffer.pop(0)
                
                rospy.loginfo(f"📊 采集数据 #{len(self.data_buffer)}: {msg.position[0]:.2f} N")
    
    def calculate_and_publish_average(self):
        """
        计算平均值并发布结果。
        module_id / device_id **必须**来自本次 trigger 上下文，缺失则拒绝发布（理论上不会走到）。
        """
        if not self.data_buffer:
            rospy.logwarn("⚠️  没有采集到数据，无法计算平均值")
            return

        # 理论上正常流程一定有 trigger 上下文；如果没有（异常路径：比如手动切了 is_collecting），拒绝发布
        module_id = self.current_module_id
        device_id = self.current_device_id
        if module_id is None or device_id is None:
            rospy.logerr("❌ 采集窗口结束但没有 trigger 上下文（module_id/device_id=None），已拒绝发布——检查触发链路")
            self.data_buffer = []
            return

        # 计算平均值
        average_value = np.mean(self.data_buffer)

        # 构建平均值消息
        avg_msg = SensorCmd()
        avg_msg.header = Header()
        avg_msg.header.stamp = rospy.Time.now()
        avg_msg.header.frame_id = "pressure_avg"
        avg_msg.id = 0
        avg_msg.module_id = module_id   # 只认触发消息中的 module_id（前端下发）
        avg_msg.device_id = device_id   # 只认触发消息中的 device_id
        avg_msg.position = [average_value]

        # 发布平均值结果
        self.avg_pub.publish(avg_msg)

        rospy.loginfo(f"✅ 已发布压力传感器平均值: {average_value:.2f} N "
                      f"(module_id={module_id}, device_id={device_id}, "
                      f"采集了 {len(self.data_buffer)} 个数据点)")

        # 清空缓存 + 清空本次采集的上下文
        self.data_buffer = []
        self.current_module_id = None
        self.current_device_id = None

if __name__ == '__main__':
    try:
        calculator = PressureAverageCalculator()
        rospy.spin()
    except rospy.ROSInterruptException:
        rospy.loginfo("👋 压力传感器平均值计算节点关闭")