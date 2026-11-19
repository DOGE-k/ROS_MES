"""Offline preparation for the proposed ROS2 message contract.

Only standard-library modules are imported. No legacy adapter, environment
configuration, database, ROS package or transport is loaded. The running MES
does not import this package, even when ROS_VERSION=2.

See mes_web/docs/后端与ROS接口对接状态清单.md section 7 for the contract
source, implemented subset and unresolved protocol/integration questions.
"""
from .addressing import (
    Address,
    AxisKind,
    EntityKind,
    arm_of,
    axis_kind,
    device_id_for,
    entity_kind,
    validate_arm,
    validate_device,
    validate_seg,
)
from .commands import build_axis_zero_message, build_fine_tuning_message
from .feedback import parse_feedback
from .models import BindingState, MessageDraft, ParsedMessage
from .validation import ContractError, PendingContractError

__all__ = [
    "Address", "AxisKind", "EntityKind", "BindingState", "MessageDraft",
    "ParsedMessage", "ContractError", "PendingContractError", "arm_of",
    "axis_kind", "device_id_for", "entity_kind", "validate_arm",
    "validate_device", "validate_seg", "build_axis_zero_message",
    "build_fine_tuning_message", "parse_feedback",
]
