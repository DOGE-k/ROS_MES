#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROS 环境下 SQLite 数据库初始化脚本
根据数据字典自动建表，并建立外键关系
"""

import sqlite3
import os
from passlib.context import CryptContext

DB_PATH = os.path.join(os.path.dirname(__file__), "ros_database.db")

def create_database(db_path=DB_PATH):
    """
    创建数据库并初始化所有表
    """
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("PRAGMA foreign_keys = ON;")

    # ----- 用户表 -----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Users (
            User_ID INTEGER PRIMARY KEY,
            Username TEXT NOT NULL,
            Password TEXT NOT NULL,
            Type_ID INTEGER NOT NULL,
            Creator_ID INTEGER NOT NULL,
            Createtime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            Islock BOOLEAN NOT NULL DEFAULT 0,
            Locktime DATETIME,
            Name VARCHAR(20),
            Headimage VARCHAR(255),
            Birthday DATETIME,
            Sex INTEGER,
            Modifytime DATETIME,
            del_flag BOOLEAN DEFAULT 0,
            Notes TEXT,
            FOREIGN KEY (Type_ID) REFERENCES Users(User_ID),
            FOREIGN KEY (Creator_ID) REFERENCES Users(User_ID)
        );
    """)

    # ----- 图纸版本表（图纸表依赖此表）-----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS DrawingsVersion (
            DrawingsVersion_ID INTEGER PRIMARY KEY,
            Drawing_ID INTEGER,
            Drawingfile TEXT NOT NULL,
            Creator_ID INTEGER NOT NULL,
            Createtime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            Modify_ID INTEGER NOT NULL,
            Modifytime DATETIME,
            del_flag BOOLEAN DEFAULT 0,
            Notes TEXT,
            FOREIGN KEY (Drawing_ID) REFERENCES Drawings(Drawing_ID),
            FOREIGN KEY (Creator_ID) REFERENCES Users(User_ID),
            FOREIGN KEY (Modify_ID) REFERENCES Users(User_ID)
        );
    """)

    # ----- 图纸表 -----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Drawings (
            Drawing_ID INTEGER PRIMARY KEY,
            Drawingname TEXT NOT NULL,
            Drawingdescripte TEXT NOT NULL,
            Drawingfile TEXT NOT NULL,
            Creator_ID INTEGER NOT NULL,
            Createtime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            Modifytime DATETIME,
            NewVersion_ID INTEGER NOT NULL,
            del_flag BOOLEAN DEFAULT 0,
            Notes TEXT,
            FOREIGN KEY (Creator_ID) REFERENCES Users(User_ID),
            FOREIGN KEY (NewVersion_ID) REFERENCES DrawingsVersion(DrawingsVersion_ID)
        );
    """)

    # ----- 工作流表 -----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workflows (
            Workflow_ID INTEGER PRIMARY KEY,
            Workflowname TEXT NOT NULL,
            WorkflowDescript TEXT,
            creater_id INTEGER NOT NULL,
            Createtime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            Modifytime DATETIME,
            del_flag BOOLEAN DEFAULT 0,
            Notes TEXT,
            FOREIGN KEY (creater_id) REFERENCES Users(User_ID)
        );
    """)

    # ----- 任务表 -----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Tasks (
            Task_ID INTEGER PRIMARY KEY,
            Taskname TEXT NOT NULL,
            Taskdescripte TEXT,
            Workflow_ID INTEGER,
            Drawing_ID INTEGER,
            creater_id INTEGER NOT NULL,
            Createtime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            TaskAssignment_id INTEGER,
            Status VARCHAR(20) NOT NULL,
            Modifytime DATETIME,
            del_flag BOOLEAN DEFAULT 0,
            Notes TEXT,
            FOREIGN KEY (Workflow_ID) REFERENCES workflows(Workflow_ID),
            FOREIGN KEY (Drawing_ID) REFERENCES Drawings(Drawing_ID),
            FOREIGN KEY (creater_id) REFERENCES Users(User_ID),
            FOREIGN KEY (TaskAssignment_id) REFERENCES Users(User_ID)
        );
    """)

    # ----- 任务跟踪表 -----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS TasksTracing (
            TasksTracing_ID INTEGER PRIMARY KEY,
            Task_ID INTEGER NOT NULL,
            operate_type INTEGER NOT NULL,
            Workflow_ID INTEGER NOT NULL,
            operater_ID INTEGER NOT NULL,
            operate_time DATETIME NOT NULL,
            Notes TEXT,
            FOREIGN KEY (Task_ID) REFERENCES Tasks(Task_ID),
            FOREIGN KEY (Workflow_ID) REFERENCES workflows(Workflow_ID),
            FOREIGN KEY (operater_ID) REFERENCES Users(User_ID)
        );
    """)

    # ----- 自适应工装型号表 -----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Model (
            Model_ID INTEGER PRIMARY KEY,
            Modelname TEXT NOT NULL,
            Modeldescripte TEXT,
            creater_id INTEGER NOT NULL,
            Createtime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            del_flag BOOLEAN DEFAULT 0,
            Notes TEXT,
            FOREIGN KEY (creater_id) REFERENCES Users(User_ID)
        );
    """)

    # ----- 设备表 -----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Device (
            Device_ID INTEGER PRIMARY KEY,
            Model_ID INTEGER NOT NULL,
            Devicedescript TEXT,
            DeviceAddress INTEGER NOT NULL,
            creater_id INTEGER NOT NULL,
            Createtime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            del_flag BOOLEAN DEFAULT 0,
            Notes TEXT,
            FOREIGN KEY (Model_ID) REFERENCES Model(Model_ID),
            FOREIGN KEY (creater_id) REFERENCES Users(User_ID)
        );
    """)

    # ----- 机械臂单元表 -----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Unit (
            Unit_ID INTEGER PRIMARY KEY,
            UnitDescript TEXT,
            Device_ID INTEGER NOT NULL,
            creater_id INTEGER NOT NULL,
            Createtime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            del_flag BOOLEAN DEFAULT 0,
            Notes TEXT,
            FOREIGN KEY (Device_ID) REFERENCES Device(Device_ID),
            FOREIGN KEY (creater_id) REFERENCES Users(User_ID)
        );
    """)

    # ----- 传感器表 -----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sensors (
            sensor_ID INTEGER PRIMARY KEY,
            sensordescript TEXT,
            IsRead INTEGER NOT NULL,
            Unit_ID INTEGER NOT NULL,
            Unit_address INTEGER NOT NULL,
            creater_id INTEGER NOT NULL,
            Createtime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            del_flag BOOLEAN DEFAULT 0,
            Notes TEXT,
            FOREIGN KEY (Unit_ID) REFERENCES Unit(Unit_ID),
            FOREIGN KEY (creater_id) REFERENCES Users(User_ID)
        );
    """)

    # ----- 工作表 -----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS works (
            Work_ID INTEGER PRIMARY KEY,
            Workname TEXT NOT NULL,
            WorkDescript TEXT,
            Drawing_ID INTEGER,
            Device_id INTEGER,
            unit_id INTEGER,
            sensor_id INTEGER,
            data TEXT,
            creater_id INTEGER NOT NULL,
            Createtime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            Modifytime DATETIME,
            del_flag BOOLEAN DEFAULT 0,
            Notes TEXT,
            FOREIGN KEY (Drawing_ID) REFERENCES Drawings(Drawing_ID),
            FOREIGN KEY (Device_id) REFERENCES Device(Device_ID),
            FOREIGN KEY (unit_id) REFERENCES Unit(Unit_ID),
            FOREIGN KEY (sensor_id) REFERENCES sensors(sensor_ID),
            FOREIGN KEY (creater_id) REFERENCES Users(User_ID)
        );
    """)

    # ----- 工作流关系表 -----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS work_flow_relations (
            work_flow_relation_ID INTEGER PRIMARY KEY,
            Workflow_ID INTEGER NOT NULL,
            Work_ID INTEGER NOT NULL,
            flow_seq INTEGER NOT NULL,
            creater_id INTEGER NOT NULL,
            Createtime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            Modifytime DATETIME,
            del_flag BOOLEAN DEFAULT 0,
            Notes TEXT,
            FOREIGN KEY (Workflow_ID) REFERENCES workflows(Workflow_ID),
            FOREIGN KEY (Work_ID) REFERENCES works(Work_ID),
            FOREIGN KEY (creater_id) REFERENCES Users(User_ID)
        );
    """)

    # ----- 传感器日志表 -----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sensor_log (
            Createtime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            creater_id INTEGER NOT NULL,
            Work_ID INTEGER NOT NULL,
            sensor_ID INTEGER NOT NULL,
            isread INTEGER NOT NULL,
            data TEXT NOT NULL,
            del_flag BOOLEAN DEFAULT 0,
            Notes TEXT,
            PRIMARY KEY (Createtime, sensor_ID),
            FOREIGN KEY (creater_id) REFERENCES Users(User_ID),
            FOREIGN KEY (Work_ID) REFERENCES works(Work_ID),
            FOREIGN KEY (sensor_ID) REFERENCES sensors(sensor_ID)
        );
    """)

    # ----- 图纸计算数据日志表 -----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS calculation (
            Createtime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            creater_id INTEGER NOT NULL,
            Work_ID INTEGER NOT NULL,
            model_id INTEGER,
            Unit_ID INTEGER,
            device_ID INTEGER,
            isread INTEGER,
            coord TEXT,
            position TEXT,
            del_flag BOOLEAN DEFAULT 0,
            Notes TEXT,
            PRIMARY KEY (Createtime),
            FOREIGN KEY (creater_id) REFERENCES Users(User_ID),
            FOREIGN KEY (Work_ID) REFERENCES works(Work_ID),
            FOREIGN KEY (model_id) REFERENCES Model(Model_ID),
            FOREIGN KEY (Unit_ID) REFERENCES Unit(Unit_ID),
            FOREIGN KEY (device_ID) REFERENCES Device(Device_ID)
        );
    """)

    # ----- 点云图解析数据表 -----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS point_data (
            Createtime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            creater_id INTEGER NOT NULL,
            model_id INTEGER,
            point TEXT NOT NULL,
            arms_address TEXT NOT NULL,
            del_flag BOOLEAN DEFAULT 0,
            Notes TEXT,
            PRIMARY KEY (Createtime),
            FOREIGN KEY (creater_id) REFERENCES Users(User_ID),
            FOREIGN KEY (model_id) REFERENCES Model(Model_ID)
        );
    """)

    # ----- 硬件表（Web后端补充）-----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hardware (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT,
            status TEXT,
            ip_address TEXT,
            description TEXT,
            updated_at DATETIME
        );
    """)

    # ----- 微调记录表（Web后端补充）-----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fine_tuning (
            id INTEGER PRIMARY KEY,
            hardware_id INTEGER,
            parameter_name TEXT NOT NULL,
            old_value REAL,
            new_value REAL NOT NULL,
            adjusted_by TEXT,
            adjusted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (hardware_id) REFERENCES hardware(id)
        );
    """)

    # ----- 微调配置表（Web后端补充）-----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fine_tuning_config (
            id INTEGER PRIMARY KEY,
            module_id INTEGER NOT NULL,
            device_id INTEGER NOT NULL,
            config_json TEXT NOT NULL,
            saved_by TEXT,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit()
    print("所有表创建成功！")

    # 计算bcrypt哈希密码
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    hashed_password = pwd_context.hash("123456")

    # 插入系统初始管理员
    try:
        cursor.execute("SELECT User_ID FROM Users WHERE User_ID = 1")
        if cursor.fetchone() is None:
            cursor.execute("""
                INSERT INTO Users (User_ID, Username, Password, Type_ID, Creator_ID, Createtime, Islock)
                VALUES (1, 'admin', ?, 1, 1, CURRENT_TIMESTAMP, 0)
            """, (hashed_password,))
            conn.commit()
            print("已插入默认管理员用户（admin）。")
    except Exception as e:
        print(f"插入初始管理员时出现异常：{e}")

    # 插入初始数据
    try:
        cursor.execute("SELECT Model_ID FROM Model WHERE Model_ID = 17")
        if cursor.fetchone() is None:
            cursor.execute("""
                INSERT INTO Model (Model_ID, Modelname, creater_id, Createtime)
                VALUES (17, '一号', 1, CURRENT_TIMESTAMP)
            """)
            print("已插入 Model_ID=17")
        conn.commit()

        cursor.execute("SELECT Device_ID FROM Device WHERE Device_ID = 1")
        if cursor.fetchone() is None:
            cursor.execute("""
                INSERT INTO Device (Device_ID, Model_ID, DeviceAddress, creater_id, Createtime)
                VALUES (1, 17, 00010001, 1, CURRENT_TIMESTAMP)
            """)
            print("已插入 Device_ID=1")
        conn.commit()

        unit_list = [
            (32, '一号机械臂'),
            (64, '二号机械臂'),
            (96, '三号机械臂'),
        ]
        for unit_id, desc in unit_list:
            cursor.execute("SELECT Unit_ID FROM Unit WHERE Unit_ID = ?", (unit_id,))
            if cursor.fetchone() is None:
                cursor.execute("""
                    INSERT INTO Unit (Unit_ID, UnitDescript, Device_ID, creater_id, Createtime)
                    VALUES (?, ?, 1, 1, CURRENT_TIMESTAMP)
                """, (unit_id, desc))
                print(f"已插入 Unit_ID={unit_id}")
        conn.commit()

        sensor_list = [
            # 一号机械臂传感器 (Unit_ID=32)
            (33, '一号机械臂的旋转电机', 1, 32, 1),
            (34, '一号机械臂的摆动电机', 1, 32, 2),
            (35, '一号机械臂的伸缩电机', 1, 32, 3),
            (41, '一号机械臂的旋转编码器', 1, 32, 1),
            (42, '一号机械臂的偏转编码器', 1, 32, 2),
            (43, '一号机械臂的伸缩编码器', 1, 32, 3),
            (49, '一号机械臂的压力传感器', 1, 32, 0),
            (50, '一号机械臂的陀螺仪传感器', 1, 32, 4),
            # 二号机械臂传感器 (Unit_ID=64)
            (65, '二号机械臂的旋转电机', 1, 64, 1),
            (66, '二号机械臂的摆动电机', 1, 64, 2),
            (67, '二号机械臂的伸缩电机', 1, 64, 3),
            (73, '二号机械臂的旋转编码器', 1, 64, 1),
            (74, '二号机械臂的偏转编码器', 1, 64, 2),
            (75, '二号机械臂的伸缩编码器', 1, 64, 3),
            (81, '二号机械臂的压力传感器', 1, 64, 0),
            (82, '二号机械臂的陀螺仪传感器', 1, 64, 4),
            # 三号机械臂传感器 (Unit_ID=96)
            (97, '三号机械臂的旋转电机', 1, 96, 1),
            (98, '三号机械臂的摆动电机', 1, 96, 2),
            (99, '三号机械臂的伸缩电机', 1, 96, 3),
            (105, '三号机械臂的旋转编码器', 1, 96, 1),
            (106, '三号机械臂的偏转编码器', 1, 96, 2),
            (107, '三号机械臂的伸缩编码器', 1, 96, 3),
            (113, '三号机械臂的压力传感器', 1, 96, 0),
            (114, '三号机械臂的陀螺仪传感器', 1, 96, 4),
        ]
        for sensor_id, desc, isread, unit_id, unit_addr in sensor_list:
            cursor.execute("SELECT sensor_ID FROM sensors WHERE sensor_ID = ?", (sensor_id,))
            if cursor.fetchone() is None:
                cursor.execute("""
                    INSERT INTO sensors (sensor_ID, sensordescript, IsRead, Unit_ID, Unit_address, creater_id, Createtime)
                    VALUES (?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
                """, (sensor_id, desc, isread, unit_id, unit_addr))
                print(f"已插入 sensor_ID={sensor_id}")
        conn.commit()

        cursor.execute("SELECT Work_ID FROM works WHERE Work_ID = 1")
        if cursor.fetchone() is None:
            cursor.execute("""
                INSERT INTO works (Work_ID, Workname, Device_id, unit_id, sensor_id, creater_id, Createtime)
                VALUES (1, '初始工作', 1, 32, 33, 1, CURRENT_TIMESTAMP)
            """)
            print("已插入 Work_ID=1")
        conn.commit()

        print("所有初始数据插入完成！")
    except Exception as e:
        print(f"插入初始数据时出现异常：{e}")

    conn.close()

if __name__ == "__main__":
    create_database()
    print(f"数据库已生成在：{os.path.abspath(DB_PATH)}")
