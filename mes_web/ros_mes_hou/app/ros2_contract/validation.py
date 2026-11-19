"""Strict, dependency-free validation for the proposed ROS2 message contract.

These helpers validate JSON-shaped values. They neither coerce legacy business
identifiers nor load application settings, connect to ROS, or access storage.
"""
from __future__ import annotations

import math
from typing import Any


class ContractError(ValueError):
    """A supplied value does not satisfy an established message rule."""


class PendingContractError(ContractError):
    """The requested operation depends on an unresolved contract definition."""


def require_int(value: Any, field: str, minimum: int, maximum: int) -> int:
    """Require a JSON integer without treating bool, strings, or floats as IDs."""
    if type(value) is not int or not minimum <= value <= maximum:
        raise ContractError(f"{field} must be an integer in {minimum}..{maximum}")
    return value


def require_number(value: Any, field: str) -> float:
    """Require a finite JSON number, rejecting booleans and numeric strings."""
    if type(value) not in (int, float):
        raise ContractError(f"{field} must be a finite number")
    try:
        number = float(value)
    except (OverflowError, ValueError) as exc:
        raise ContractError(f"{field} must be a finite number") from exc
    if not math.isfinite(number):
        raise ContractError(f"{field} must be a finite number")
    return number


def require_object(value: Any, field: str) -> dict:
    """Require a dictionary while leaving caller-owned data unchanged."""
    if not isinstance(value, dict):
        raise ContractError(f"{field} must be an object")
    return value


def require_header(value: Any) -> dict:
    """Validate a ROS2 Header and return only its standard, detached fields.

    A timestamp is supplied explicitly; no wall-clock time or default frame is
    invented. ROS1 secs/nsecs are intentionally not accepted here.
    """
    header = require_object(value, "header")
    stamp = require_object(header.get("stamp"), "header.stamp")
    sec = require_int(stamp.get("sec"), "header.stamp.sec", -(2**31), 2**31 - 1)
    nanosec = require_int(stamp.get("nanosec"), "header.stamp.nanosec", 0, 999_999_999)
    frame_id = header.get("frame_id")
    if not isinstance(frame_id, str):
        raise ContractError("header.frame_id must be a string")
    return {"stamp": {"sec": sec, "nanosec": nanosec}, "frame_id": frame_id}
