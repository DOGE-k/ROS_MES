# app/ros/normalizer.py
"""ROS 反馈消息归一化：把 rosbridge 收到的原始消息转成前端反馈形状。

纯业务规则，与 ROS1/ROS2 无关（时间戳字段的差异只存在于下发方向的
header 序列化，反馈方向的原始消息原样透传在 `raw` 字段里）。
"""
from __future__ import annotations

import json
import math
import time
from typing import Any, Dict, Optional

from app.core.config import settings
from app.ros.profile import TOPIC_DEFAULTS

# V2.1 三轴 device_id → 反馈标签
#   旋转=关节1：1,4,7,10,13；摆动=关节2：2,5,8,11,14；伸缩=关节3：3,6,9,12,15
#   压力/IMU 同为臂级 21~25，按话题区分（见 normalize_feedback_message）
def _build_feedback_labels() -> Dict[int, tuple]:
    labels: Dict[int, tuple] = {}
    type_by_joint = {
        0: ("rotation_axis_encoder", "旋转轴编码器"),
        1: ("swing_axis_encoder", "摆动轴编码器"),
        2: ("telescope_axis_encoder", "伸缩轴编码器"),
    }
    for arm in range(1, 6):                       # 臂 1~5
        for joint, (data_type, name) in type_by_joint.items():
            axis = (arm - 1) * 3 + joint + 1      # 三轴ID布局（臂1=1/2/3 … 臂5=13/14/15）
            labels[axis] = (data_type, f"臂{arm}{name}")
    for arm in range(1, 6):
        labels[20 + arm] = ("pressure_sensor", f"臂{arm}压力传感器")
    return labels


FEEDBACK_LABELS = _build_feedback_labels()
# 臂级 device_id 21~25 在 IMU 话题上覆盖为陀螺仪标签
IMU_FEEDBACK_LABEL = ("imu_pose", "陀螺仪姿态")


def _position_value(value: Any) -> Optional[float]:
    if isinstance(value, list):
        return _float_value(value[0]) if value else None
    return _float_value(value)


def _float_value(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _int_value(value: Any) -> Optional[int]:
    number = _float_value(value)
    return int(number) if number is not None and number.is_integer() else None


def _raw_json_value(value: Any) -> Any:
    """保留诊断信息；JSON 不支持的 NaN/Infinity 以文本保留，不再冒充数值。"""
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {key: _raw_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_raw_json_value(item) for item in value]
    return value


def resolve_ack_module(module_id: Any, module_seg_map: Optional[str] = None) -> Dict[str, Any]:
    """列出 ACK 模块号的可能业务归属，不猜发布者或关联某次请求。

    ROS 软件拒绝使用业务号，CAN ACK 使用 SEG；二者消息结构相同。
    正业务号始终是候选，SEG 无映射时不能排除未知来源。
    """
    raw_module = _int_value(module_id)
    candidates = {raw_module} if raw_module is not None and raw_module > 0 else set()
    unresolved = raw_module is None or raw_module < 0
    mapping_valid = True
    mapping = {}
    try:
        parsed = json.loads(settings.ROS_MODULE_SEG_MAP if module_seg_map is None else module_seg_map)
        if not isinstance(parsed, dict):
            raise ValueError("mapping must be an object")
        for business, seg in parsed.items():
            business_id, seg_id = _int_value(business), _int_value(seg)
            if business_id is None or business_id <= 0 or seg_id is None or not 0 <= seg_id <= 14:
                raise ValueError("invalid module/SEG entry")
            mapping[business_id] = seg_id
    except (TypeError, ValueError, OverflowError):
        mapping_valid = False
        unresolved = True

    if mapping_valid and raw_module is not None and 0 <= raw_module <= 14:
        matches = {business for business, seg in mapping.items() if seg == raw_module}
        candidates.update(matches)
        unresolved = not matches

    if not mapping_valid or unresolved or not candidates:
        resolution = "unknown"
    else:
        resolution = "resolved" if len(candidates) == 1 else "ambiguous"
    return {
        "module_candidates": sorted(candidates),
        "module_resolution": resolution,
        "business_module_id": next(iter(candidates)) if resolution == "resolved" else None,
    }


def normalize_feedback_message(
    topic: str,
    msg: Dict[str, Any],
    topics: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """归一化一条反馈消息；topics 缺省用默认话题表（与 profile.topics 同构）。"""
    topics = topics or TOPIC_DEFAULTS
    raw = msg
    msg = msg if isinstance(msg, dict) else {}
    device_id = _int_value(msg.get("device_id"))
    module_id = _int_value(msg.get("module_id"))
    data_type, feedback_type = "unknown", "unknown feedback"
    module_id_space = "unknown"
    arm = device_id - 20 if device_id is not None and 21 <= device_id <= 25 else None
    # 指令回执（CmdAck：超位拒绝等）先于默认表查找，避免轴号被套上编码器标签
    event_fields = {
        "feedback_axis_status": ("axis_status", ("status_bits", "axis_state", "base_valid")),
        "feedback_arrive": ("arrive_notification", ("angle", "pos_error", "status_bits", "flags")),
        "feedback_stop": ("stop_notification", ("stop_reason", "output_level")),
        "feedback_fault": ("axis_fault", ("fault_bits", "local_action", "detail", "duration_ms")),
        "feedback_limit": ("limit_event", ("limit_type", "output_level")),
    }
    event = next((value for key, value in event_fields.items() if topic == topics.get(key)), None)
    if event is not None and device_id is not None and 1 <= device_id <= 15:
        data_type, feedback_type = event[0], event[0]
        module_id_space = "seg"
    elif topic == topics["feedback_cmd_ack"]:
        data_type, feedback_type = "cmd_ack", "指令回执"
        module_id_space = "mixed"
    # 新话题分支先于默认表查找，保证标签稳定（即使 FEEDBACK_LABELS 未覆盖）
    elif topic == topics["feedback_pressure_avg"] and arm is not None:
        data_type = "pressure_average"
        feedback_type = f"臂{arm}压力平均值(5s窗口)"
        module_id_space = "business"
    elif topic == topics["feedback_vacuum_loss"] and arm is not None:
        data_type = "vacuum_loss_event"
        feedback_type = f"臂{arm}吸盘失压告警"
    # 臂级 21~25：IMU 话题识别为陀螺仪，其余按压力传感器
    elif topic == topics["feedback_imu"] and arm is not None:
        data_type, feedback_type = IMU_FEEDBACK_LABEL[0], f"臂{arm}陀螺仪姿态"
        module_id_space = "seg"
    elif topic == topics["feedback_sensor"] and arm is not None:
        data_type, feedback_type = FEEDBACK_LABELS[device_id]
        module_id_space = "seg"
    elif device_id is not None and 1 <= device_id <= 15:
        expected_topics = (topics["feedback_rotation"], topics["feedback_swing"], topics["feedback_telescope"])
        if topic == expected_topics[(device_id - 1) % 3]:
            data_type, feedback_type = FEEDBACK_LABELS[device_id]
            module_id_space = "seg"
    header = msg.get("header") or {}
    stamp = header.get("stamp") if isinstance(header, dict) else None

    position = _position_value(msg.get("position"))
    position_valid = position is not None and data_type not in ("unknown", "cmd_ack", "imu_pose")
    normalized = {
        "time_id": time.time(),
        "topic": topic,
        "header": _raw_json_value(stamp or header),
        "module_id": module_id,
        "module_id_space": module_id_space,
        "device_id": device_id,
        "position": position if position_valid else None,
        "position_valid": position_valid,
        "valid_fields": ["position"] if position_valid else [],
        "data_type": data_type,
        "feedback_type": feedback_type,
        "raw": _raw_json_value(raw),
    }
    if "id" in msg:
        normalized["id"] = _raw_json_value(msg["id"])

    if event is not None and data_type == event[0]:
        normalized["position"] = None
        normalized["position_valid"] = False
        normalized["valid_fields"] = []
        for field in event[1]:
            normalized[field] = _int_value(msg.get(field))
            if normalized[field] is not None:
                normalized["valid_fields"].append(field)
    if data_type == "vacuum_loss_event":
        normalized["module_id_space"] = "seg"
        normalized.update({field: _int_value(msg.get(field)) for field in ("pressure_raw", "loss_threshold")})

    if data_type == "imu_pose":
        for field in ("swing_angle", "rotation_angle", "x", "y", "z"):
            normalized[field] = _float_value(msg.get(field))
            if normalized[field] is not None:
                normalized["valid_fields"].append(field)

    if data_type == "cmd_ack":
        # CmdAck 专有字段：ack_msg=回执类型 / result=结果码（3=超位拒绝）/ detail=明细（1上限 2下限）
        normalized.update(
            {
                "ack_msg": _int_value(msg.get("ack_msg")),
                "result": _int_value(msg.get("result")),
                "detail": _int_value(msg.get("detail")),
                **resolve_ack_module(msg.get("module_id")),
            }
        )

    return normalized
