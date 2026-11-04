from sqlalchemy.orm import Session

from app.core.device_catalog import validate_sensor_fields
from app.db import models
from app.schemas import sensors as schemas


def get_sensors(db: Session):
    return db.query(models.Sensor).filter(models.Sensor.del_flag == False).all()


def get_sensors_by_unit(db: Session, unit_id: int):
    unit = db.query(models.Unit).filter(
        models.Unit.id == unit_id,
        models.Unit.del_flag == False,
    ).first()
    if unit:
        return db.query(models.Sensor).filter(
            models.Sensor.Module_ID == unit.Module_ID,
            models.Sensor.Unit_ID == unit.Unit_ID,
            models.Sensor.del_flag == False,
        ).all()
    return db.query(models.Sensor).filter(
        models.Sensor.Unit_ID == unit_id,
        models.Sensor.del_flag == False,
    ).all()


def get_sensor(db: Session, sensor_id: int):
    return db.query(models.Sensor).filter(
        models.Sensor.id == sensor_id,
        models.Sensor.del_flag == False,
    ).first()


def get_sensor_by_module_and_sensor_id(db: Session, module_id: int, sensor_id: int):
    return db.query(models.Sensor).filter(
        models.Sensor.Module_ID == module_id,
        models.Sensor.sensor_ID == sensor_id,
        models.Sensor.del_flag == False,
    ).first()


def _resolve_unit(db: Session, module_id, unit_id, unit_row_id=None):
    query = db.query(models.Unit).filter(models.Unit.del_flag == False)
    if unit_row_id is not None:
        query = query.filter(models.Unit.id == unit_row_id)
    if module_id is not None:
        query = query.filter(models.Unit.Module_ID == module_id)
    if unit_id is not None:
        query = query.filter(models.Unit.Unit_ID == unit_id)
    # 未指定模块时，不以业务 Unit_ID 猜测属于哪个模块。
    if module_id is None and unit_row_id is None:
        raise ValueError("必须指定所属模块或机械臂记录ID")
    unit = query.first()
    if unit is None:
        raise ValueError("所属机械臂不存在，或与模块/机械臂编号不匹配")
    return unit


def create_sensor(db: Session, data: schemas.SensorCreate):
    unit = _resolve_unit(db, data.Module_ID, data.Unit_ID, data.unit_row_id)
    fields = validate_sensor_fields(unit.Unit_ID, data.sensordescript, data.model_dump(exclude_unset=True))
    existing = db.query(models.Sensor).filter(
        models.Sensor.Module_ID == unit.Module_ID,
        models.Sensor.sensor_ID == fields["sensor_ID"],
    ).first()
    if existing and not existing.del_flag:
        return None
    create_data = data.model_dump(exclude={"Device_ID", "unit_row_id"})
    create_data.update(fields, Module_ID=unit.Module_ID)
    if existing:
        # 唯一约束包含软删除行，重新登记时复用记录，避免插入冲突。
        db_item = existing
        for field, value in create_data.items():
            setattr(db_item, field, value)
        db_item.del_flag = False
    else:
        db_item = models.Sensor(**create_data)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


def update_sensor(db: Session, sensor_id: int, data: schemas.SensorUpdate):
    db_item = get_sensor(db, sensor_id)
    if not db_item:
        return None
    update_data = data.model_dump(exclude_unset=True)
    for field in ("Unit_ID", "Module_ID"):
        if field in update_data and update_data[field] is None:
            raise ValueError(f"{field} 不能为空")
    unit_row_id = update_data.get("unit_row_id")
    unit = _resolve_unit(
        db,
        update_data.get("Module_ID", None if unit_row_id is not None else db_item.Module_ID),
        update_data.get("Unit_ID", None if unit_row_id is not None else db_item.Unit_ID),
        unit_row_id,
    )
    # 仅修改备注/启用状态时，保留历史数据的编号；改变类型或归属时统一重新校验及生成。
    identity_fields = {"sensor_ID", "sensordescript", "Unit_ID", "Module_ID", "unit_row_id", "Unit_address"}
    if identity_fields.intersection(update_data):
        fields = validate_sensor_fields(
            unit.Unit_ID, update_data.get("sensordescript", db_item.sensordescript), update_data,
        )
        update_data.update(fields)
    update_data.update(Module_ID=unit.Module_ID, Unit_ID=unit.Unit_ID)
    update_data.pop("Device_ID", None)
    update_data.pop("unit_row_id", None)
    target_module_id = update_data.get("Module_ID", db_item.Module_ID)
    target_sensor_id = update_data.get("sensor_ID", db_item.sensor_ID)
    existing = db.query(models.Sensor).filter(
        models.Sensor.Module_ID == target_module_id,
        models.Sensor.sensor_ID == target_sensor_id,
    ).first()
    if existing and existing.id != sensor_id:
        return False
    for field, value in update_data.items():
        setattr(db_item, field, value)
    db.commit()
    db.refresh(db_item)
    return db_item


def delete_sensor(db: Session, sensor_id: int):
    db_item = get_sensor(db, sensor_id)
    if not db_item:
        return False
    db_item.del_flag = True
    db.commit()
    return True
