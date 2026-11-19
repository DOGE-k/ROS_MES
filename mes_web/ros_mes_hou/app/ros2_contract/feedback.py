"""Parse the proposed ROS2 contract without transport, storage or ROS imports.

The caller supplies the message name and, optionally, its confirmed topic map.
Payload fields keep their message shape. Units that the design has not settled
remain unknown; this module never infers motion completion or request identity.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from .addressing import Address, AxisKind, EntityKind, axis_kind, validate_device
from .models import BindingState, ParsedMessage
from .validation import (
    ContractError,
    require_header,
    require_int,
    require_number,
    require_object,
)


_FLOAT32_MAX = 3.4028234663852886e38
_INT32_MIN = -(2**31)
_INT32_MAX = 2**31 - 1

_AXIS_INTEGER_FIELDS = {
    "AxisStatus": {
        "status_bits": (0, 0x1FF),
        "axis_state": (0, 3),
        "base_valid": (0, 1),
    },
    "ArriveNotification": {
        "angle": (_INT32_MIN, _INT32_MAX),
        "pos_error": (-(2**15), 2**15 - 1),
        "status_bits": (0, 0xFF),
        "flags": (0, 0xFF),
    },
    "StopNotification": {
        "stop_reason": (1, 6),
        "output_level": (0, 0xFF),
    },
    "CmdAck": {
        "ack_msg": (0, 15),
        "result": (0, 5),
        "detail": (0, 0xFF),
    },
    "AxisFault": {
        "fault_bits": (0, 0xFFFF),
        "local_action": (1, 1),
        "detail": (0, 0xFF),
        "duration_ms": (0, 0xFFFF),
    },
    "LimitEvent": {
        "limit_type": (1, 2),
        "output_level": (0, 0xFF),
    },
}

_MODULE_INTEGER_FIELDS = {
    "seg": (0, 14),
    "status": (0, 1),
    "arm_slot": (1, 5),
    "axis_base": (1, 13),
    "exist_mask": (0, 7),
    "ready_mask": (0, 7),
    "module_state": (0, 0xFF),
    "token": (0, 0xFFFF),
}

_KNOWN_NAMES = frozenset(_AXIS_INTEGER_FIELDS) | {
    "Feedback",
    "SensorCmd",
    "VacuumLoss",
    "TuoLuoYi",
    "GyroFeedback",
    "ModuleStatus",
}


def _field(message: dict[str, Any], name: str) -> Any:
    if name not in message:
        raise ContractError(f"missing required field: {name}")
    return message[name]


def _integer_fields(
    message: dict[str, Any], fields: dict[str, tuple[int, int]]
) -> dict[str, int]:
    return {
        name: require_int(_field(message, name), name, minimum, maximum)
        for name, (minimum, maximum) in fields.items()
    }


def _position(message: dict[str, Any]) -> list[float]:
    position = _field(message, "position")
    if not isinstance(position, list) or len(position) != 1:
        raise ContractError("position must be a single-element array")
    return [require_number(position[0], "position[0]")]


def _check_topic(
    message_name: str,
    topic: str | None,
    topic_message_types: Mapping[str, str] | None,
) -> None:
    if topic is not None and (not isinstance(topic, str) or not topic):
        raise ContractError("topic must be a non-empty string when supplied")
    if topic_message_types is None:
        return
    if not isinstance(topic_message_types, Mapping):
        raise ContractError("topic_message_types must be a mapping")
    if topic is None or topic_message_types.get(topic) != message_name:
        raise ContractError("topic is unconfirmed or does not match the message name")


def parse_feedback(
    message_name: str,
    message: object,
    *,
    topic: str | None = None,
    topic_message_types: Mapping[str, str] | None = None,
) -> ParsedMessage:
    """Validate one feedback payload using its explicitly supplied message name.

    Known payloads require every documented field and a ROS2 Header. Unknown
    names retain their payload for diagnosis but have no interpreted values.
    A supplied topic map is authoritative; this module has no default topics.
    The caller must supply feedback-direction inputs/maps: SensorCmd also names
    a different, unresolved outbound command, so a type name cannot prove flow
    direction. Without a map, a supplied topic is not verified by this parser.
    """
    if not isinstance(message_name, str) or not message_name:
        raise ContractError("message_name must be a non-empty string")
    _check_topic(message_name, topic, topic_message_types)
    payload = require_object(message, "message")
    raw = deepcopy(payload)
    if message_name not in _KNOWN_NAMES:
        return ParsedMessage(
            message_name=message_name,
            header=None,
            address=None,
            values={},
            units={},
            pending=("unknown_message",),
            raw=raw,
            is_known=False,
        )

    header = require_header(_field(payload, "header"))
    address = Address(
        module_id=_field(payload, "module_id"),
        device_id=_field(payload, "device_id"),
    )
    values: dict[str, Any]
    units: dict[str, str | None] = {}
    pending: tuple[str, ...] = ()
    binding = None

    if message_name in _AXIS_INTEGER_FIELDS or message_name == "Feedback":
        validate_device(address.device_id, EntityKind.AXIS)
        if message_name == "Feedback":
            values = {"position": _position(payload)}
            if axis_kind(address.device_id) == AxisKind.TELESCOPIC:
                units["position"] = None
                pending = ("telescopic_feedback_unit_unconfirmed",)
            else:
                units["position"] = "degree"
        else:
            values = _integer_fields(payload, _AXIS_INTEGER_FIELDS[message_name])
            if message_name == "ArriveNotification":
                if axis_kind(address.device_id) == AxisKind.TELESCOPIC:
                    units.update(angle=None, pos_error=None)
                    pending = ("telescopic_arrive_units_unconfirmed",)
                else:
                    units.update(angle="0.01degree", pos_error="0.01degree")
            elif message_name == "CmdAck":
                pending = ("uncorrelated_ack",)
            elif message_name == "AxisFault":
                units["duration_ms"] = "ms"
    elif message_name == "SensorCmd":
        validate_device(address.device_id, EntityKind.PRESSURE)
        values = {
            "id": require_int(_field(payload, "id"), "id", 0, 0xFF),
            "position": _position(payload),
        }
        units["position"] = "N"
    elif message_name == "VacuumLoss":
        validate_device(address.device_id, EntityKind.PRESSURE)
        values = _integer_fields(
            payload,
            {
                "pressure_raw": (_INT32_MIN, _INT32_MAX),
                "loss_threshold": (0, 0xFFFF),
            },
        )
        units.update(pressure_raw=None, loss_threshold=None)
        pending = ("vacuum_loss_units_unconfirmed",)
    elif message_name == "TuoLuoYi":
        validate_device(address.device_id, EntityKind.IMU)
        fields = ("swing_angle", "rotation_angle", "x", "y", "z")
        values = {
            name: require_number(_field(payload, name), name) for name in fields
        }
        units = {
            "swing_angle": "degree",
            "rotation_angle": "degree",
            "x": "cm",
            "y": "cm",
            "z": "cm",
        }
    elif message_name == "GyroFeedback":
        validate_device(address.device_id, EntityKind.IMU)
        values = {}
        for prefix, unit in (("accel", "m/s²"), ("gyro", "degree/s")):
            for axis in ("x", "y", "z"):
                name = f"{prefix}_{axis}"
                value = require_number(_field(payload, name), name)
                if abs(value) > _FLOAT32_MAX:
                    raise ContractError(f"{name} is outside float32 range")
                values[name] = value
                units[name] = unit
    else:  # ModuleStatus
        validate_device(address.device_id, EntityKind.SYSTEM)
        values = _integer_fields(payload, _MODULE_INTEGER_FIELDS)
        binding = BindingState(
            route_seg=address.module_id,
            bound_seg=values["seg"],
            status=values["status"],
            arm_slot=values["arm_slot"],
            axis_base=values["axis_base"],
        )
        pending = (
            "binding_freshness_unverified",
            "binding_query_correlation_unverified",
        )
        if values["status"] == 1 and address.module_id != values["seg"]:
            pending += ("binding_route_mismatch",)

    return ParsedMessage(
        message_name=message_name,
        header=header,
        address=address,
        values=values,
        units=units,
        pending=pending,
        raw=raw,
        binding=binding,
    )
