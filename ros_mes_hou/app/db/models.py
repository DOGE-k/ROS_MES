from sqlalchemy import Boolean, Column, Integer, String, Float, DateTime, ForeignKey, Text, UniqueConstraint, Index
from sqlalchemy.sql import func

from app.db.database import Base


class User(Base):
    __tablename__ = "Users"

    User_ID = Column(Integer, primary_key=True, index=True, autoincrement=True)
    Username = Column(Text, nullable=False)
    Password = Column(Text, nullable=False)
    Type_ID = Column(Integer, ForeignKey("Users.User_ID"), nullable=False, default=2)
    Creator_ID = Column(Integer, ForeignKey("Users.User_ID"), nullable=False)
    Createtime = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    Islock = Column(Boolean, nullable=False, default=False)
    Locktime = Column(DateTime(timezone=True), nullable=True)
    Name = Column(String(20), nullable=True)
    Headimage = Column(String(255), nullable=True)
    Birthday = Column(DateTime(timezone=True), nullable=True)
    Sex = Column(Integer, nullable=True)
    Modifytime = Column(DateTime(timezone=True), nullable=True)
    del_flag = Column(Boolean, default=False)
    Notes = Column(Text, nullable=True)


class FineTuning(Base):
    __tablename__ = "fine_tuning"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    Device_ID = Column(Integer, ForeignKey("Device.Device_ID"), nullable=False)
    DeviceAddress = Column(Integer, nullable=True)
    Devicedescript = Column(Text, nullable=True)
    parameter_name = Column(String(100), nullable=False)
    old_value = Column(Float)
    new_value = Column(Float, nullable=False)
    adjusted_by = Column(String(50))
    adjusted_at = Column(DateTime(timezone=True), server_default=func.now())


class FineTuningConfig(Base):
    __tablename__ = "fine_tuning_config"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    module_id = Column(Integer, index=True, nullable=False)
    device_id = Column(Integer, index=True, nullable=False)
    config_json = Column(Text, nullable=False)
    saved_by = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Drawing(Base):
    __tablename__ = "Drawings"

    Drawing_ID = Column(Integer, primary_key=True, index=True, autoincrement=True)
    Drawingname = Column(Text, nullable=False)
    Drawingdescripte = Column(Text, nullable=False)
    Drawingfile = Column(Text, nullable=False)
    Creator_ID = Column(Integer, ForeignKey("Users.User_ID"), nullable=False)
    Createtime = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    Modifytime = Column(DateTime(timezone=True), nullable=True)
    NewVersion_ID = Column(Integer, ForeignKey("DrawingsVersion.DrawingsVersion_ID"), nullable=False)
    del_flag = Column(Boolean, default=False)
    Notes = Column(Text, nullable=True)


class DrawingVersion(Base):
    __tablename__ = "DrawingsVersion"

    DrawingsVersion_ID = Column(Integer, primary_key=True, index=True, autoincrement=True)
    Drawing_ID = Column(Integer, ForeignKey("Drawings.Drawing_ID"), nullable=False)
    Drawingfile = Column(Text, nullable=False)
    Creator_ID = Column(Integer, ForeignKey("Users.User_ID"), nullable=False)
    Createtime = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    Modify_ID = Column(Integer, ForeignKey("Users.User_ID"), nullable=False)
    Modifytime = Column(DateTime(timezone=True), nullable=True)
    del_flag = Column(Boolean, default=False)
    Notes = Column(Text, nullable=True)


class Work(Base):
    __tablename__ = "works"

    Work_ID = Column(Integer, primary_key=True, index=True, autoincrement=True)
    Workname = Column(Text, nullable=False)
    WorkDescript = Column(Text, nullable=True)
    Drawing_ID = Column(Integer, ForeignKey("Drawings.Drawing_ID"), nullable=True)
    Device_id = Column(Integer, nullable=True)
    unit_id = Column(Integer, ForeignKey("Unit.id"), nullable=True)
    sensor_id = Column(Integer, ForeignKey("sensors.id"), nullable=True)
    data = Column(Text, nullable=True)
    creater_id = Column(Integer, ForeignKey("Users.User_ID"), nullable=False)
    Createtime = Column(DateTime(timezone=True), server_default=func.now())
    Modifytime = Column(DateTime(timezone=True), nullable=True)
    del_flag = Column(Boolean, default=False)
    Notes = Column(Text, nullable=True)


class Workflow(Base):
    __tablename__ = "workflows"

    Workflow_ID = Column(Integer, primary_key=True, index=True, autoincrement=True)
    Workflowname = Column(Text, nullable=False)
    WorkflowDescript = Column(Text, nullable=True)
    creater_id = Column(Integer, ForeignKey("Users.User_ID"), nullable=False)
    Createtime = Column(DateTime(timezone=True), server_default=func.now())
    Modifytime = Column(DateTime(timezone=True), nullable=True)
    del_flag = Column(Boolean, default=False)
    Notes = Column(Text, nullable=True)


class WorkFlowRelation(Base):
    __tablename__ = "work_flow_relations"

    work_flow_relation_ID = Column(Integer, primary_key=True, index=True, autoincrement=True)
    Workflow_ID = Column(Integer, ForeignKey("workflows.Workflow_ID"), nullable=False)
    Work_ID = Column(Integer, ForeignKey("works.Work_ID"), nullable=False)
    flow_seq = Column(Integer, nullable=False)
    creater_id = Column(Integer, ForeignKey("Users.User_ID"), nullable=False)
    Createtime = Column(DateTime(timezone=True), server_default=func.now())
    Modifytime = Column(DateTime(timezone=True), nullable=True)
    del_flag = Column(Boolean, default=False)
    Notes = Column(Text, nullable=True)


class ModelTooling(Base):
    __tablename__ = "Model"

    Model_ID = Column(Integer, primary_key=True, index=True, autoincrement=True)
    Modelname = Column(Text, nullable=False)
    Modeldescripte = Column(Text, nullable=True)
    creater_id = Column(Integer, ForeignKey("Users.User_ID"), nullable=False)
    Createtime = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    del_flag = Column(Boolean, default=False)
    Notes = Column(Text, nullable=True)


class Device(Base):
    __tablename__ = "Device"

    Device_ID = Column(Integer, primary_key=True, index=True, autoincrement=True)
    Model_ID = Column(Integer, ForeignKey("Model.Model_ID"), nullable=False)
    Devicedescript = Column(Text, nullable=True)
    DeviceAddress = Column(Integer, nullable=False)
    creater_id = Column(Integer, ForeignKey("Users.User_ID"), nullable=False)
    Createtime = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    del_flag = Column(Boolean, default=False)
    Notes = Column(Text, nullable=True)


class Unit(Base):
    __tablename__ = "Unit"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    Unit_ID = Column(Integer, nullable=False, autoincrement=False)
    UnitDescript = Column(Text, nullable=True)
    Device_ID = Column(Integer, ForeignKey("Device.Device_ID"), nullable=False)
    creater_id = Column(Integer, ForeignKey("Users.User_ID"), nullable=False)
    Createtime = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    del_flag = Column(Boolean, default=False)
    Notes = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint('Device_ID', 'Unit_ID', name='uq_unit_device'),
    )


class Sensor(Base):
    __tablename__ = "sensors"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    sensor_ID = Column(Integer, nullable=False, autoincrement=False)
    sensordescript = Column(Text, nullable=True)
    IsRead = Column(Integer, nullable=False)
    Device_ID = Column(Integer, ForeignKey("Device.Device_ID"), nullable=False)
    Unit_ID = Column(Integer, nullable=False)
    unit_row_id = Column(Integer, ForeignKey("Unit.id"), nullable=False)
    Unit_address = Column(Integer, nullable=False)
    creater_id = Column(Integer, ForeignKey("Users.User_ID"), nullable=False)
    Createtime = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    del_flag = Column(Boolean, default=False)
    Notes = Column(Text, nullable=True)

    __table_args__ = (
        Index(
            'uq_sensor_device_active',
            'Device_ID',
            'sensor_ID',
            unique=True,
            sqlite_where=(del_flag == False),
        ),
    )


class SensorLog(Base):
    __tablename__ = "sensor_log"

    Createtime = Column(DateTime(timezone=True), server_default=func.now(), primary_key=True, nullable=False)
    creater_id = Column(Integer, ForeignKey("Users.User_ID"), nullable=False)
    Work_ID = Column(Integer, ForeignKey("works.Work_ID"), nullable=False)
    sensor_id = Column(Integer, ForeignKey("sensors.id"), primary_key=True, nullable=False)
    isread = Column(Integer, nullable=False)
    data = Column(Text, nullable=False)
    del_flag = Column(Boolean, default=False)
    Notes = Column(Text, nullable=True)


class Task(Base):
    __tablename__ = "Tasks"

    Task_ID = Column(Integer, primary_key=True, index=True, autoincrement=True)
    Taskname = Column(Text, nullable=False)
    Taskdescripte = Column(Text, nullable=True)
    Workflow_ID = Column(Integer, ForeignKey("workflows.Workflow_ID"), nullable=True)
    Drawing_ID = Column(Integer, ForeignKey("Drawings.Drawing_ID"), nullable=True)
    creater_id = Column(Integer, ForeignKey("Users.User_ID"), nullable=False)
    Createtime = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    TaskAssignment_id = Column(Integer, ForeignKey("Users.User_ID"), nullable=True)
    Status = Column(String(20), nullable=False, default="0")
    Modifytime = Column(DateTime(timezone=True), nullable=True)
    del_flag = Column(Boolean, default=False)
    Notes = Column(Text, nullable=True)


class TasksTracing(Base):
    __tablename__ = "TasksTracing"

    TasksTracing_ID = Column(Integer, primary_key=True, index=True, autoincrement=True)
    Task_ID = Column(Integer, ForeignKey("Tasks.Task_ID"), nullable=False)
    operate_type = Column(Integer, nullable=False)
    Workflow_ID = Column(Integer, ForeignKey("workflows.Workflow_ID"), nullable=False)
    operater_ID = Column(Integer, ForeignKey("Users.User_ID"), nullable=False)
    operate_time = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    Notes = Column(Text, nullable=True)


class Calculation(Base):
    __tablename__ = "calculation"

    Createtime = Column(DateTime(timezone=True), server_default=func.now(), primary_key=True, nullable=False)
    creater_id = Column(Integer, ForeignKey("Users.User_ID"), nullable=False)
    Work_ID = Column(Integer, ForeignKey("works.Work_ID"), nullable=False)
    model_id = Column(Integer, ForeignKey("Model.Model_ID"), nullable=True)
    Unit_ID = Column(Integer, nullable=True)
    device_ID = Column(Integer, ForeignKey("Device.Device_ID"), nullable=True)
    isread = Column(Integer, nullable=True)
    coord = Column(Text, nullable=True)
    position = Column(Text, nullable=True)
    del_flag = Column(Boolean, default=False)
    Notes = Column(Text, nullable=True)


class PointData(Base):
    __tablename__ = "point_data"

    Createtime = Column(DateTime(timezone=True), server_default=func.now(), primary_key=True, nullable=False)
    creater_id = Column(Integer, ForeignKey("Users.User_ID"), nullable=False)
    model_id = Column(Integer, ForeignKey("Model.Model_ID"), nullable=True)
    point = Column(Text, nullable=False)
    arms_address = Column(Text, nullable=False)
    del_flag = Column(Boolean, default=False)
    Notes = Column(Text, nullable=True)
