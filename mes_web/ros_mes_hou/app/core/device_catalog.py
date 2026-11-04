"""设备管理的业务编号配置；不定义或修改 ROS device_id。

这里维护可登记的机械臂和传感器类型，既供页面读取，也供写接口校验。
现有业务编号与 sqlite_create.py 保持一致，不会因读取配置而补写数据库。
"""

ARM_OPTIONS = (
    (32, "一号机械臂"),
    (64, "二号机械臂"),
    (96, "三号机械臂"),
    (128, "四号机械臂"),
    (160, "五号机械臂"),
)

# 名称、业务号偏移、臂内地址。
SENSOR_TYPES = (
    ("旋转电机", 1, 1),
    ("摆动电机", 2, 2),
    ("伸缩电机", 3, 3),
    ("旋转编码器", 9, 1),
    ("偏转编码器", 10, 2),
    ("伸缩编码器", 11, 3),
    ("压力传感器", 17, 0),
    ("陀螺仪传感器", 18, 4),
)


def validate_unit_id(unit_id: int) -> int:
    if unit_id not in {value for value, _ in ARM_OPTIONS}:
        raise ValueError("机械臂编号不在设备配置中，请重新加载设备配置")
    return unit_id


def sensor_fields(unit_id: int, label: str | None) -> dict:
    validate_unit_id(unit_id)
    for name, offset, address in SENSOR_TYPES:
        if name == label:
            return {"sensor_ID": unit_id + offset, "Unit_address": address}
    raise ValueError("传感器类型不在设备配置中，请重新选择")


def validate_sensor_fields(unit_id: int, label: str | None, supplied: dict) -> dict:
    expected = sensor_fields(unit_id, label)
    for field, value in expected.items():
        if field in supplied and supplied[field] is not None and supplied[field] != value:
            raise ValueError(f"{field} 与设备配置不一致，期望值为 {value}")
    return expected


def get_device_config() -> dict:
    return {
        "arms": [{"label": label, "value": value} for value, label in ARM_OPTIONS],
        "sensor_types": [
            {
                "label": label,
                "Unit_address": address,
                "sensor_ids": {str(unit_id): unit_id + offset for unit_id, _ in ARM_OPTIONS},
            }
            for label, offset, address in SENSOR_TYPES
        ],
    }
