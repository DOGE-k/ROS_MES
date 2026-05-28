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
            FOREIGN KEY (Creator_ID) REFERENCES Users(User_ID)
        );
    """)

    # ----- 图纸版本表（图纸表依赖此表）-----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS DrawingsVersion (
            DrawingsVersion_ID INTEGER PRIMARY KEY,
            Drawing_ID INTEGER NOT NULL,
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
            NewVersion_ID INTEGER,
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
        CREATE TABLE IF NOT EXISTS Type (
            Type_ID INTEGER PRIMARY KEY,
            Typename TEXT NOT NULL,
            Typedescripte TEXT,
            creater_id INTEGER NOT NULL,
            Createtime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            del_flag BOOLEAN DEFAULT 0,
            Notes TEXT,
            FOREIGN KEY (creater_id) REFERENCES Users(User_ID)
        );
    """)

    # ----- 模块表 -----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS  Module (
            Module_ID INTEGER PRIMARY KEY,
            Type_ID INTEGER NOT NULL,
            Moduledescript TEXT,
            ModuleAddress TEXT NOT NULL,
            creater_id INTEGER NOT NULL,
            Createtime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            del_flag BOOLEAN DEFAULT 0,
            Notes TEXT,
            FOREIGN KEY (Type_ID) REFERENCES Type(Type_ID),
            FOREIGN KEY (creater_id) REFERENCES Users(User_ID)
        );
    """)

    # ----- 机械臂单元表 -----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Unit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            Unit_ID INTEGER NOT NULL,
            UnitDescript TEXT,
            Module_ID INTEGER NOT NULL,
            creater_id INTEGER NOT NULL,
            Createtime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            del_flag BOOLEAN DEFAULT 0,
            Notes TEXT,
            FOREIGN KEY (Module_ID) REFERENCES Module(Module_ID),
            FOREIGN KEY (creater_id) REFERENCES Users(User_ID),
            UNIQUE(Module_ID, Unit_ID)
        );
    """)

    # ----- 传感器表 -----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sensors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sensor_ID INTEGER NOT NULL,
            sensordescript TEXT,
            IsRead INTEGER NOT NULL,
            Module_ID INTEGER NOT NULL,
            Unit_ID INTEGER NOT NULL,
            Unit_address INTEGER NOT NULL,
            unit_row_id INTEGER NOT NULL,
            creater_id INTEGER NOT NULL,
            Createtime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            del_flag BOOLEAN DEFAULT 0,
            Notes TEXT,
            FOREIGN KEY (Module_ID) REFERENCES Module(Module_ID),
            FOREIGN KEY (unit_row_id) REFERENCES Unit(id),
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
            Module_ID INTEGER,
            unit_id INTEGER,
            sensor_id INTEGER,
            data TEXT,
            creater_id INTEGER NOT NULL,
            Createtime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            Modifytime DATETIME,
            del_flag BOOLEAN DEFAULT 0,
            Notes TEXT,
            FOREIGN KEY (Drawing_ID) REFERENCES Drawings(Drawing_ID),
            FOREIGN KEY (Module_ID) REFERENCES Module(Module_ID),
            FOREIGN KEY (unit_id) REFERENCES Unit(id),
            FOREIGN KEY (sensor_id) REFERENCES sensors(id),
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
            sensor_id INTEGER NOT NULL,
            isread INTEGER NOT NULL,
            data TEXT NOT NULL,
            del_flag BOOLEAN DEFAULT 0,
            Notes TEXT,
            PRIMARY KEY (Createtime, sensor_id),
            FOREIGN KEY (creater_id) REFERENCES Users(User_ID),
            FOREIGN KEY (Work_ID) REFERENCES works(Work_ID),
            FOREIGN KEY (sensor_id) REFERENCES sensors(id)
        );
    """)

    # ----- 计算解析数据日志表 -----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS calculation (
            Createtime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            creater_id INTEGER NOT NULL,
            Work_ID INTEGER NOT NULL,
            Module_ID INTEGER,
            Unit_ID INTEGER,
            Device_ID INTEGER,
            isread INTEGER NOT NULL,
            coord TEXT,
            position TEXT,
            del_flag BOOLEAN DEFAULT 0,
            Notes TEXT,
            PRIMARY KEY (Createtime),
            FOREIGN KEY (creater_id) REFERENCES Users(User_ID),
            FOREIGN KEY (Work_ID) REFERENCES works(Work_ID),
            FOREIGN KEY (Module_ID) REFERENCES Module(Module_ID)
        );
    """)

    # ----- 点云图解析数据表 -----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS point_data (
            Createtime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            creater_id INTEGER NOT NULL,
            Module_ID INTEGER,
            point TEXT NOT NULL,
            arms_address TEXT NOT NULL,
            del_flag BOOLEAN DEFAULT 0,
            Notes TEXT,
            PRIMARY KEY (Createtime),
            FOREIGN KEY (creater_id) REFERENCES Users(User_ID),
            FOREIGN KEY (Module_ID) REFERENCES Module(Module_ID)
        );
    """)


    # ----- 微调记录表-----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fine_tuning (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            Module_ID INTEGER NOT NULL,
            Unit_ID INTEGER NOT NULL,
            ModuleAddress INTEGER,
            Moduledescript TEXT,
            parameter_name VARCHAR(100) NOT NULL,
            old_value REAL,
            new_value REAL NOT NULL,
            creater_id INTEGER NOT NULL,
            Createtime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            Notes TEXT,
            del_flag BOOLEAN DEFAULT 0,
            FOREIGN KEY (Module_ID, Unit_ID) REFERENCES Unit(Module_ID, Unit_ID),
            FOREIGN KEY (creater id) REFERENCES Users(User_ID)
        );
    """)

    # ----- 微调配置表-----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fine_tuning_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            Module_ID INTEGER NOT NULL,
            Unit_ID INTEGER NOT NULL,
            sensor_ID INTEGER NOT NULL,
            config_json TEXT NOT NULL,
            creater_id INTEGER NOT NULL,
            Createtime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            Notes TEXT,
            del_flag BOOLEAN DEFAULT 0,
            FOREIGN KEY (creater_id) REFERENCES Users(User_ID),
            FOREIGN KEY (Module_ID) REFERENCES Module(Module_ID),
            FOREIGN KEY (Unit_ID) REFERENCES Unit(Unit_ID),
            FOREIGN KEY (sensor_ID) REFERENCES sensors(sensor_ID)
        );
    """)

    conn.commit()
    print("所有表创建成功！")

    # # 计算密码哈希（使用简单的方式避免bcrypt兼容性问题）
    try:
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        hashed_password = pwd_context.hash("123456")
    except Exception as e:
        print(f"bcrypt哈希失败，使用备用方案: {e}")
        # 使用预计算的哈希值
        hashed_password = "$2b$12$y0tc9zZgA8lEJzhvaJfKL.G0LQPGTZ.9r8e56FOuHg91rPBDlCYni"

    # 插入系统初始管理员
    try:
        cursor.execute("SELECT User_ID FROM Users WHERE User_ID = 1")
        if cursor.fetchone() is None:
            cursor.execute("""
                INSERT INTO Users (User_ID, Username, Password, Type_ID, Creator_ID, Createtime, Islock, del_flag)
                VALUES (1, 'admin', ?, 1, 1, CURRENT_TIMESTAMP, 0, 0)
            """, (hashed_password,))
            conn.commit()
            print("已插入默认管理员用户（admin）。")
    except Exception as e:
        print(f"插入初始管理员时出现异常：{e}")

    # 插入初始数据
    try:
        cursor.execute("SELECT Type_ID FROM Type WHERE Type_ID = 1")
        if cursor.fetchone() is None:
            cursor.execute("""
                INSERT INTO Type (Type_ID, Typename, Typedescripte, creater_id, Createtime, del_flag)
                VALUES (1, '自适应工装型号', '自适应工装型号描述', 1, CURRENT_TIMESTAMP, 0)
            """)
            print("已插入 Type_ID=1")
        conn.commit()

        cursor.execute("SELECT Module_ID FROM Module WHERE Module_ID = 17")
        if cursor.fetchone() is None:
            cursor.execute("""
                INSERT INTO Module (Module_ID, Type_ID, Moduledescript, ModuleAddress, creater_id, Createtime, del_flag)
                VALUES (17, 1, '一号模块', '17', 1, CURRENT_TIMESTAMP, 0)
            """)
            print("已插入 Module_ID=17")
        conn.commit()

        unit_sensor_data = [
            (32, '一号机械臂', [
                (33, '旋转电机', 1, 32, 1),
                (34, '摆动电机', 1, 32, 2),
                (35, '伸缩电机', 1, 32, 3),
                (41, '旋转编码器', 1, 32, 1),
                (42, '偏转编码器', 1, 32, 2),
                (43, '伸缩编码器', 1, 32, 3),
                (49, '压力传感器', 1, 32, 0),
                (50, '陀螺仪传感器', 1, 32, 4),
            ]),
            (64, '二号机械臂', [
                (65, '旋转电机', 1, 64, 1),
                (66, '摆动电机', 1, 64, 2),
                (67, '伸缩电机', 1, 64, 3),
                (73, '旋转编码器', 1, 64, 1),
                (74, '偏转编码器', 1, 64, 2),
                (75, '伸缩编码器', 1, 64, 3),
                (81, '压力传感器', 1, 64, 0),
                (82, '陀螺仪传感器', 1, 64, 4),
            ]),
            (96, '三号机械臂', [
                (97, '旋转电机', 1, 96, 1),
                (98, '摆动电机', 1, 96, 2),
                (99, '伸缩电机', 1, 96, 3),
                (105, '旋转编码器', 1, 96, 1),
                (106, '偏转编码器', 1, 96, 2),
                (107, '伸缩编码器', 1, 96, 3),
                (113, '压力传感器', 1, 96, 0),
                (114, '陀螺仪传感器', 1, 96, 4),
            ]),
        ]
        for unit_id, desc, sensor_list in unit_sensor_data:
            cursor.execute("SELECT id FROM Unit WHERE Module_ID = ? AND Unit_ID = ?", (17, unit_id))
            row = cursor.fetchone()
            if row is None:
                cursor.execute("""
                    INSERT INTO Unit (Unit_ID, UnitDescript, Module_ID, creater_id, Createtime, del_flag)
                    VALUES (?, ?, 17, 1, CURRENT_TIMESTAMP, 0)
                """, (unit_id, desc))
                unit_row_id = cursor.lastrowid
                print(f"已插入 Unit_ID={unit_id}")
            else:
                unit_row_id = row[0]
            conn.commit()

            for sensor_id, s_desc, isread, s_unit_id, unit_addr in sensor_list:
                cursor.execute(
                    "SELECT id FROM sensors WHERE unit_row_id = ? AND sensor_ID = ?",
                    (unit_row_id, sensor_id),
                )
                sensor_row = cursor.fetchone()
                if sensor_row is None:
                    cursor.execute("""
                        INSERT INTO sensors (sensor_ID, sensordescript, IsRead, Module_ID, Unit_ID, unit_row_id, Unit_address, creater_id, Createtime, del_flag)
                        VALUES (?, ?, ?, 17, ?, ?, ?, 1, CURRENT_TIMESTAMP, 0)
                    """, (sensor_id, s_desc, isread, s_unit_id, unit_row_id, unit_addr))
                    sensor_row_id = cursor.lastrowid
                    print(f"已插入 sensor_ID={sensor_id}")
                else:
                    sensor_row_id = sensor_row[0]
                    cursor.execute("""
                        UPDATE sensors
                        SET sensordescript = ?, IsRead = ?, Unit_ID = ?, Unit_address = ?, del_flag = 0
                        WHERE id = ?
                    """, (s_desc, isread, s_unit_id, unit_addr, sensor_row_id))
            conn.commit()

        cursor.execute("SELECT Work_ID FROM works WHERE Work_ID = 1")
        if cursor.fetchone() is None:
            cursor.execute("SELECT id FROM Unit WHERE Module_ID = ? AND Unit_ID = ?", (17, 32))
            initial_unit = cursor.fetchone()
            cursor.execute("""
                SELECT s.id
                FROM sensors AS s
                JOIN Unit AS u ON u.id = s.unit_row_id
                WHERE u.Module_ID = ? AND u.Unit_ID = ? AND s.sensor_ID = ?
            """, (17, 32, 33))
            initial_sensor = cursor.fetchone()
            if initial_unit is None or initial_sensor is None:
                raise RuntimeError("初始工作引用的机械臂或传感器不存在")
            cursor.execute("""
                INSERT INTO works (Work_ID, Workname, Module_ID, unit_id, sensor_id, creater_id, Createtime, del_flag)
                VALUES (1, '初始工作', 17, ?, ?, 1, CURRENT_TIMESTAMP, 0)
            """, (initial_unit[0], initial_sensor[0]))
            print("已插入 Work_ID=1")
        conn.commit()

        print("所有初始数据插入完成！")

        # 向后兼容：修复可能存在的 del_flag=NULL 数据
        tables_with_del_flag = ['Module', 'Type', 'Unit', 'sensors', 'works', 'workflows', 'work_flow_relations',
                                'sensor_log', 'calculation', 'point_data', 'Users', 'Drawings',
                                'DrawingsVersion', 'Tasks']
        for tbl in tables_with_del_flag:
            cursor.execute(f"UPDATE {tbl} SET del_flag = 0 WHERE del_flag IS NULL")
        conn.commit()
    except Exception as e:
        print(f"插入初始数据时出现异常：{e}")

    conn.close()

if __name__ == "__main__":
    create_database()
    print(f"数据库已生成在：{os.path.abspath(DB_PATH)}")
