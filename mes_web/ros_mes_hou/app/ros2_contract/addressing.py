"""Module-local entity addressing from the proposed message contract.

    module_id: CAN SEG 0..14, never a database/business module identifier.
    device_id: system=0; axes=1..15; arms=21..25;
               pressure sensors=31..35; IMUs=36..40.

No CAN frame conversion or business-to-SEG mapping belongs in this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from .validation import ContractError, require_int


class EntityKind(str, Enum):
    SYSTEM = "system"
    AXIS = "axis"
    ARM = "arm"
    PRESSURE = "pressure"
    IMU = "imu"


class AxisKind(str, Enum):
    ROTATION = "rotation"
    SWING = "swing"
    TELESCOPIC = "telescopic"


def validate_seg(seg: Any) -> int:
    """Require an explicitly supplied physical CAN SEG, including legal zero."""
    return require_int(seg, "module_id (CAN SEG)", 0, 14)


def validate_arm(arm: Any) -> int:
    """Require a slot within one physical module, without legacy ID decoding."""
    return require_int(arm, "arm", 1, 5)


def entity_kind(device_id: Any) -> EntityKind:
    """Classify a legal entity ID, rejecting reserved ranges and legacy IDs."""
    device_id = require_int(device_id, "device_id", 0, 40)
    if device_id == 0:
        return EntityKind.SYSTEM
    if 1 <= device_id <= 15:
        return EntityKind.AXIS
    if 21 <= device_id <= 25:
        return EntityKind.ARM
    if 31 <= device_id <= 35:
        return EntityKind.PRESSURE
    if 36 <= device_id <= 40:
        return EntityKind.IMU
    raise ContractError(f"device_id {device_id} is reserved")


def arm_of(device_id: Any) -> int | None:
    """Return the module-local arm slot; system ID zero has no arm."""
    kind = entity_kind(device_id)
    if kind is EntityKind.SYSTEM:
        return None
    if kind is EntityKind.AXIS:
        return (device_id - 1) // 3 + 1
    offset = {EntityKind.ARM: 20, EntityKind.PRESSURE: 30, EntityKind.IMU: 35}[kind]
    return device_id - offset


def validate_device(device_id: Any, kind: EntityKind) -> int:
    """Require the device segment specified by the message's entity category."""
    if not isinstance(kind, EntityKind):
        raise ContractError("kind must be an EntityKind")
    actual = entity_kind(device_id)
    if actual is not kind:
        raise ContractError(f"device_id {device_id} is {actual.value}, expected {kind.value}")
    return device_id


def axis_kind(device_id: Any) -> AxisKind:
    """Return J1/J2/J3 only for axis entities."""
    device_id = validate_device(device_id, EntityKind.AXIS)
    return (AxisKind.ROTATION, AxisKind.SWING, AxisKind.TELESCOPIC)[(device_id - 1) % 3]


def device_id_for(arm: Any, kind: EntityKind, axis: AxisKind | None = None) -> int:
    """Build an entity ID from an explicit arm slot and message category."""
    arm = validate_arm(arm)
    if not isinstance(kind, EntityKind):
        raise ContractError("kind must be an EntityKind")
    if kind is EntityKind.SYSTEM:
        raise ContractError("a system entity is not addressed by an arm")
    if kind is EntityKind.AXIS:
        if not isinstance(axis, AxisKind):
            raise ContractError("axis entities require an AxisKind")
        joint = {AxisKind.ROTATION: 1, AxisKind.SWING: 2, AxisKind.TELESCOPIC: 3}[axis]
        return (arm - 1) * 3 + joint
    if axis is not None:
        raise ContractError("axis is only valid for axis entities")
    return {EntityKind.ARM: 20, EntityKind.PRESSURE: 30, EntityKind.IMU: 35}[kind] + arm


@dataclass(frozen=True)
class Address:
    """A validated physical entity identity, scoped by SEG and device ID."""

    module_id: int
    device_id: int

    def __post_init__(self) -> None:
        validate_seg(self.module_id)
        entity_kind(self.device_id)
