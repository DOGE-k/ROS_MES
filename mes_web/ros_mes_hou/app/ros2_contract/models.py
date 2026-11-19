"""Offline message data only; these types do not express device readiness."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from .addressing import Address, validate_arm, validate_seg
from .validation import ContractError, require_int


@dataclass(frozen=True)
class BindingState:
    """Identity fields from ModuleStatus, without freshness or query matching.

    route_seg and bound_seg stay separate even when their values differ. A
    caller must verify the query token, freshness and device state in a future
    runtime integration; status=1 by itself is not permission to move.
    """

    route_seg: int
    bound_seg: int
    status: int
    arm_slot: int
    axis_base: int

    def __post_init__(self) -> None:
        validate_seg(self.route_seg)
        validate_seg(self.bound_seg)
        require_int(self.status, "status", 0, 1)
        validate_arm(self.arm_slot)
        require_int(self.axis_base, "axis_base", 1, 13)
        if self.axis_base != (self.arm_slot - 1) * 3 + 1:
            raise ContractError("axis_base must match arm_slot's first axis")
        if self.status == 0 and self.bound_seg != 0:
            raise ContractError("unbound ModuleStatus must have seg=0")

    def require_target(self, module_id: int, arm: int) -> None:
        """Reject an unbound or differently addressed command target."""
        validate_seg(module_id)
        validate_arm(arm)
        if self.status != 1:
            raise ContractError("an unbound target cannot produce a control message")
        if self.route_seg != module_id or self.bound_seg != module_id:
            raise ContractError("routing SEG and bound SEG must match the target SEG")
        if self.arm_slot != arm:
            raise ContractError("binding arm_slot does not match the command target")


@dataclass(frozen=True)
class MessageDraft:
    """A message body for inspection, without a topic, package or transport.

    This is deliberately not a rosbridge publish payload. pending identifies
    integration checks that this offline layer cannot perform. Nested dicts
    remain editable; a future sender must validate the final body again.
    """

    message_name: str
    message: dict[str, Any]
    pending: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_name": self.message_name,
            "message": deepcopy(self.message),
            "pending": list(self.pending),
        }


@dataclass(frozen=True)
class ParsedMessage:
    """Validated message fields, with raw evidence and unresolved semantics.

    values keeps the message's payload shape, not today's HTTP/WS schema.
    A parsed ACK, binding or arrival never implies a completed MES request.
    """

    message_name: str
    header: dict | None
    address: Address | None
    values: dict[str, Any]
    units: dict[str, str | None]
    pending: tuple[str, ...]
    raw: dict
    is_known: bool = True
    binding: BindingState | None = None

    @property
    def valid_fields(self) -> tuple[str, ...]:
        """Typed payload fields; consumers must also inspect units/pending."""
        return tuple(self.values)

    def to_dict(self) -> dict[str, Any]:
        binding = None
        if self.binding is not None:
            binding = {
                "route_seg": self.binding.route_seg,
                "bound_seg": self.binding.bound_seg,
                "status": self.binding.status,
                "arm_slot": self.binding.arm_slot,
                "axis_base": self.binding.axis_base,
            }
        return {
            "message_name": self.message_name,
            "is_known": self.is_known,
            "header": deepcopy(self.header),
            "address": (
                {"module_id": self.address.module_id, "device_id": self.address.device_id}
                if self.address is not None else None
            ),
            "values": deepcopy(self.values),
            "valid_fields": list(self.valid_fields),
            "units": dict(self.units),
            "pending": list(self.pending),
            "raw": deepcopy(self.raw),
            "binding": binding,
        }
