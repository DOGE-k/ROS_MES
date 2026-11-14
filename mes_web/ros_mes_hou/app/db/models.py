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
    # 初始值：本次发令前的实测位置；下发前检查关闭或缺少起点反馈时为空
    old_value = Column(Float)
    # 应到值 = old_value + requested_delta；缺少初始值时为为空
    new_value = Column(Float)
    # 微调量：本次请求的增量（页面输入值），与批次 progress_json 的 position 同义
    requested_delta = Column(Float)
    # 到位实测：绝对位置与相对初始值的增量，来自到位事件 angle/100
    observed_position = Column(Float)
    observed_delta = Column(Float)
    # 偏差 = observed_delta - requested_delta
    deviation = Column(Float)
    # 固件自报误差：到位事件 pos_error/100，设备自述，不参与 MES 判定
    position_error = Column(Float)
    # 运动结论：moved 已动（默认）/ no_motion 人工标记未动 / unknown 无法判定
    outcome = Column(String(20), nullable=True)
    outcome_by = Column(Integer, ForeignKey("Users.User_ID"), nullable=True)
    outcome_at = Column(DateTime(timezone=True), nullable=True)
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


class FineTuningBatch(Base):
    __tablename__ = "fine_tuning_batches"

    id = Column(String(36), primary_key=True)
    request_id = Column(String(80), nullable=False, unique=True)
    # 未完成/待核实批次保留唯一目标锁；终结后置空，SQLite 允许多个 NULL。
    target_key = Column(String(80), nullable=True, unique=True)
    module_id = Column(Integer, nullable=False)
    unit_id = Column(Integer, nullable=False)
    seg = Column(Integer, nullable=False)
    creator_id = Column(Integer, nullable=False)
    request_json = Column(Text, nullable=False)
    progress_json = Column(Text, nullable=False)
    status = Column(String(30), nullable=False)
    message = Column(Text, nullable=False)
    cancel_requested = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ControlSafety(Base):
    __tablename__ = "control_safety"

    id = Column(Integer, primary_key=True)
    state = Column(String(30), nullable=False, default="clear")
    generation = Column(Integer, nullable=False, default=0)


class ControlStopHold(Base):
    """局部停记录：只锁住本次的模块/轴，不清除全局联锁。

    与 control_safety（全局急停）分开存放，避免局部停把所有模块一起锁死。
    清除表示操作员确认过现场、恢复 MES 下发能力；不代表设备侧锁存已解除。
    """

    __tablename__ = "control_stop_holds"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    mode = Column(String(10), nullable=False, default="real")
    scope = Column(String(10), nullable=False)
    module_id = Column(Integer, nullable=False, index=True)
    device_id = Column(Integer, nullable=True)
    state = Column(String(30), nullable=False, default="requested")
    message = Column(Text, nullable=True)
    creator_id = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    cleared_at = Column(DateTime(timezone=True), nullable=True)
    cleared_reason = Column(String(40), nullable=True)


class RosDebugSettings(Base):
    __tablename__ = "ros_debug_settings"

    id = Column(Integer, primary_key=True)
    revision = Column(Integer, nullable=False, default=0)
    config_json = Column(Text, nullable=False)


class ControlSession(Base):
    """一次成功的模块握手登记为可续接会话。

    只记录 MES 侧的会话事实（模块、组号、机械臂、连接版本），不代表设备仍保持绑定；
    续接读取本表，不发送任何模块确认指令，也不自动重发运动。
    """

    __tablename__ = "control_sessions"

    id = Column(String(36), primary_key=True)
    module_id = Column(Integer, nullable=False, index=True)
    device_id = Column(Integer, nullable=True)
    x = Column(Integer, nullable=True)
    y = Column(Integer, nullable=True)
    seg = Column(Integer, nullable=False)
    unit_ids_json = Column(Text, nullable=False)
    connection_revision = Column(Integer, nullable=True)
    creator_id = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_active_at = Column(DateTime(timezone=True), server_default=func.now())
    invalidated_at = Column(DateTime(timezone=True), nullable=True)
    invalid_reason = Column(String(60), nullable=True)


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
