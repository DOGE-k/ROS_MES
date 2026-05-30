from sqlalchemy import Boolean, Column, Integer, String, Float, DateTime, ForeignKey, Text, UniqueConstraint, Index, ForeignKeyConstraint
from sqlalchemy.sql import func

from app.db.database import Base


class User(Base):
    __tablename__ = "Users"

    User_ID = Column(Integer, primary_key=True, index=True, autoincrement=True)
    Username = Column(Text, nullable=False)
    Password = Column(Text, nullable=False)
    Type_ID = Column(Integer, nullable=False, default=2)
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
    module_id = Column(Integer, nullable=False)
    unit_id = Column(Integer, nullable=False)
    module_address = Column(Integer, nullable=True)
    module_descript = Column(Text, nullable=True)
    parameter_name = Column(String(100), nullable=False)
    old_value = Column(Float)
    new_value = Column(Float, nullable=False)
    creater_id = Column(Integer, ForeignKey("Users.User_ID"), nullable=False)
    create_time = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    notes = Column(Text, nullable=True)
    del_flag = Column(Boolean, default=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["module_id", "unit_id"],
            ["Unit.Module_ID", "Unit.Unit_ID"],
            name="fk_fine_tuning_unit",
        ),
    )


class FineTuningConfig(Base):
    __tablename__ = "fine_tuning_config"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    module_id = Column(Integer, index=True, nullable=False)
    unit_id = Column(Integer, index=True, nullable=False)
    sensor_id = Column(Integer, index=True, nullable=False)
    config_json = Column(Text, nullable=False)
    creater_id = Column(Integer, ForeignKey("Users.User_ID"), nullable=False)
    create_time = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    notes = Column(Text, nullable=True)
    del_flag = Column(Boolean, default=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["module_id", "unit_id"],
            ["Unit.Module_ID", "Unit.Unit_ID"],
            name="fk_fine_tuning_config_unit",
        ),
        ForeignKeyConstraint(
            ["module_id", "sensor_id"],
            ["sensors.Module_ID", "sensors.sensor_ID"],
            name="fk_fine_tuning_config_sensor",
        ),
    )


class Drawing(Base):
    __tablename__ = "Drawings"

    Drawing_ID = Column(Integer, primary_key=True, index=True, autoincrement=True)
    Drawingname = Column(Text, nullable=False)
    Drawingdescripte = Column(Text, nullable=False)
    Drawingfile = Column(Text, nullable=False)
    Creator_ID = Column(Integer, ForeignKey("Users.User_ID"), nullable=False)
    Createtime = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    Modifytime = Column(DateTime(timezone=True), nullable=True)
    NewVersion_ID = Column(Integer, ForeignKey("DrawingsVersion.DrawingsVersion_ID"), nullable=True)
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
    Module_ID = Column(Integer, ForeignKey("Module.Module_ID"), nullable=True)
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


class Type(Base):
    __tablename__ = "Type"

    Type_ID = Column(Integer, primary_key=True, index=True, autoincrement=True)
    Typename = Column(Text, nullable=False)
    Typedescripte = Column(Text, nullable=True)
    creater_id = Column(Integer, ForeignKey("Users.User_ID"), nullable=False)
    Createtime = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    del_flag = Column(Boolean, default=False)
    Notes = Column(Text, nullable=True)


class Module(Base):
    __tablename__ = "Module"

    Module_ID = Column(Integer, primary_key=True, index=True, autoincrement=True)
    Type_ID = Column(Integer, ForeignKey("Type.Type_ID"), nullable=False)
    Moduledescript = Column(Text, nullable=True)
    ModuleAddress = Column(Text, nullable=False)
    creater_id = Column(Integer, ForeignKey("Users.User_ID"), nullable=False)
    Createtime = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    del_flag = Column(Boolean, default=False)
    Notes = Column(Text, nullable=True)


class Unit(Base):
    __tablename__ = "Unit"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    Unit_ID = Column(Integer, nullable=False, autoincrement=False)
    UnitDescript = Column(Text, nullable=True)
    Module_ID = Column(Integer, ForeignKey("Module.Module_ID"), nullable=False)
    creater_id = Column(Integer, ForeignKey("Users.User_ID"), nullable=False)
    Createtime = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    del_flag = Column(Boolean, default=False)
    Notes = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint('Module_ID', 'Unit_ID', name='uq_unit_module'),
    )


class Sensor(Base):
    __tablename__ = "sensors"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    sensor_ID = Column(Integer, nullable=False, autoincrement=False)
    sensordescript = Column(Text, nullable=True)
    IsRead = Column(Integer, nullable=False)
    Module_ID = Column(Integer, nullable=False)
    Unit_ID = Column(Integer, nullable=False)
    Unit_address = Column(Integer, nullable=False)
    creater_id = Column(Integer, ForeignKey("Users.User_ID"), nullable=False)
    Createtime = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    del_flag = Column(Boolean, default=False)
    Notes = Column(Text, nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["Module_ID", "Unit_ID"],
            ["Unit.Module_ID", "Unit.Unit_ID"],
            name="fk_sensor_unit",
        ),
        UniqueConstraint('Module_ID', 'sensor_ID', name='uq_sensor_module'),
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
    Module_ID = Column(Integer, ForeignKey("Module.Module_ID"), nullable=True)
    Unit_ID = Column(Integer, nullable=True)
    device_ID = Column(Integer, nullable=True)
    isread = Column(Integer, nullable=True)
    coord = Column(Text, nullable=True)
    position = Column(Text, nullable=True)
    del_flag = Column(Boolean, default=False)
    Notes = Column(Text, nullable=True)


class PointData(Base):
    __tablename__ = "point_data"

    Createtime = Column(DateTime(timezone=True), server_default=func.now(), primary_key=True, nullable=False)
    creater_id = Column(Integer, ForeignKey("Users.User_ID"), nullable=False)
    Module_ID = Column(Integer, ForeignKey("Module.Module_ID"), nullable=True)
    point = Column(Text, nullable=False)
    arms_address = Column(Text, nullable=False)
    del_flag = Column(Boolean, default=False)
    Notes = Column(Text, nullable=True)
