"""Construct established ROS2 message bodies without sending anything.

No business-ID lookup, clock, topic defaults, ROS package import or device
connection belongs here. Unresolved operations have no builder in this stage.
"""
from __future__ import annotations

from .addressing import (
    Address, AxisKind, EntityKind, arm_of, axis_kind, device_id_for, validate_arm,
)
from .models import BindingState, MessageDraft
from .validation import ContractError, PendingContractError, require_header, require_number


_MESSAGE_NAMES = {
    AxisKind.ROTATION: "RotationCmd",
    AxisKind.SWING: "SwingCmd",
    AxisKind.TELESCOPIC: "TelescopicCmd",
}
_INTEGRATION_PENDING = ("topic_and_package_not_bound", "runtime_checks_not_performed")


def _require_binding(binding: BindingState | None, module_id: int, arm: int) -> None:
    if binding is None:
        raise PendingContractError("explicit binding evidence is required; no default SEG is used")
    if not isinstance(binding, BindingState):
        raise ContractError("binding must be a BindingState")
    binding.require_target(module_id, arm)


def build_fine_tuning_message(
    parameter_name: str | AxisKind,
    position: float,
    module_id: int,
    device_id: int,
    *,
    header: dict,
    binding: BindingState | None = None,
) -> MessageDraft:
    """Build one relative increment using a physical SEG and axis entity ID.

    position is in degrees for rotation/swing and mm for telescopic. Absolute
    limits, start position, binding freshness and safety interlocks cannot be
    checked by this message-only function and remain pending.
    """
    if not isinstance(parameter_name, str):
        raise ContractError("parameter_name must be rotation, swing or telescopic")
    try:
        parameter = AxisKind(parameter_name)
    except ValueError as exc:
        raise ContractError("parameter_name must be rotation, swing or telescopic") from exc
    address = Address(module_id, device_id)
    if axis_kind(address.device_id) is not parameter:
        raise ContractError("parameter_name does not match the axis entity ID")
    arm = arm_of(address.device_id)
    _require_binding(binding, address.module_id, arm)
    increment = require_number(position, "position")
    validated_header = require_header(header)
    pending = _INTEGRATION_PENDING + ("absolute_limits_not_checked",)
    if parameter is AxisKind.ROTATION:
        if validated_header["frame_id"] != f"module_{address.module_id}":
            raise ContractError("RotationCmd frame_id must be module_{SEG}")
    else:
        pending += ("frame_id_rule_pending",)
    return MessageDraft(
        message_name=_MESSAGE_NAMES[parameter],
        message={
            "header": validated_header,
            "module_id": address.module_id,
            "device_id": address.device_id,
            "position": [increment],
        },
        pending=pending,
    )


def build_axis_zero_message(
    module_id: int,
    arm: int,
    *,
    header: dict,
    binding: BindingState | None = None,
) -> MessageDraft:
    """Build the defined software-baseline reset, not hardware motion/home."""
    arm = validate_arm(arm)
    address = Address(module_id, device_id_for(arm, EntityKind.ARM))
    _require_binding(binding, address.module_id, arm)
    return MessageDraft(
        message_name="IntCmd",
        message={
            "header": require_header(header),
            "module_id": address.module_id,
            "device_id": address.device_id,
            "position": [address.device_id],
        },
        pending=_INTEGRATION_PENDING + ("frame_id_rule_pending", "reset_confirmation_not_defined"),
    )
