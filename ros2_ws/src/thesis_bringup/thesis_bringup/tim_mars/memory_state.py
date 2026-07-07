"""Private selected-target memory state helpers for TIM-MARS.

This module contains the internal _Memory dataclass used by TargetIdentityMemory
and the mapping from memory state to controller-facing control mode.

It is intentionally private support code. Public TIM-MARS data structures live
in types.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from thesis_bringup.tim_mars.types import BBox, ControlMode, TargetState


@dataclass
class _Memory:
    selected: bool = False
    state: TargetState = TargetState.NO_TARGET
    track_id: Optional[int] = None
    bbox: Optional[BBox] = None
    quality: float = 0.0
    frames_since_seen: int = 0
    confirmed_after_reacquire: int = 0
    appearance: Optional[Any] = None


def _control_mode_for_state(state: TargetState) -> ControlMode:
    if state == TargetState.NO_TARGET:
        return ControlMode.NO_CONTROL
    if state == TargetState.LOCKED:
        return ControlMode.NORMAL
    if state == TargetState.UNCERTAIN:
        return ControlMode.YAW_ONLY
    if state == TargetState.REACQUIRED:
        return ControlMode.CONFIRM
    return ControlMode.HOVER


