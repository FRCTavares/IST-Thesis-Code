"""Pure state-aware selected-person control policy for Issue #74.

This module owns no ROS subscriptions and receives no raw tracker or detector
candidates. It resolves whether trusted normal following, bounded yaw-only
recovery, or fail-safe hover is permitted from TIM-MARS authority state.
"""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class StateAwarePolicyConfig:
    recovery_enabled: bool = False
    recovery_yaw_rate: float = 0.05
    recovery_max_duration_s: float = 1.0
    recovery_max_integrated_yaw_rad: float = 0.05
    last_trusted_max_age_s: float = 1.0


@dataclass(frozen=True)
class StateAwarePolicyInput:
    state: str
    control_mode: str
    target_valid: bool
    target_frame_id: int
    status_frame_id: int
    status_fresh: bool
    selection_generation: int

    last_trusted_generation: int | None = None
    last_trusted_horizontal_error: float | None = None
    last_trusted_age_s: float | None = None

    recovery_elapsed_s: float = 0.0
    recovery_integrated_yaw_rad: float = 0.0
    dt_s: float = 0.0


@dataclass(frozen=True)
class StateAwarePolicyDecision:
    mode: str
    reason: str
    allow_normal_follow: bool
    update_last_trusted: bool
    recovery_yaw_z: float = 0.0

    @property
    def translation_allowed(self) -> bool:
        return self.allow_normal_follow


def _finite_nonnegative(value: float | None) -> bool:
    return (
        value is not None
        and math.isfinite(value)
        and value >= 0.0
    )


def resolve_state_aware_policy(
    policy_input: StateAwarePolicyInput,
    config: StateAwarePolicyConfig,
) -> StateAwarePolicyDecision:
    """Resolve the controller-authority mode without using candidate geometry."""

    causal_pair = (
        policy_input.target_frame_id > 0
        and policy_input.status_frame_id > 0
        and policy_input.target_frame_id == policy_input.status_frame_id
    )

    trusted_normal = (
        policy_input.status_fresh
        and causal_pair
        and policy_input.target_valid
        and policy_input.state == "LOCKED"
        and policy_input.control_mode == "NORMAL"
    )

    if trusted_normal:
        return StateAwarePolicyDecision(
            mode="NORMAL_FOLLOW",
            reason="trusted_locked_normal",
            allow_normal_follow=True,
            update_last_trusted=True,
        )

    if not config.recovery_enabled:
        return StateAwarePolicyDecision(
            mode="HOVER",
            reason="recovery_disabled",
            allow_normal_follow=False,
            update_last_trusted=False,
        )

    if not policy_input.status_fresh:
        return StateAwarePolicyDecision(
            mode="HOVER",
            reason="status_not_fresh",
            allow_normal_follow=False,
            update_last_trusted=False,
        )

    if policy_input.state != "LOST":
        return StateAwarePolicyDecision(
            mode="HOVER",
            reason=f"state_not_recoverable:{policy_input.state}",
            allow_normal_follow=False,
            update_last_trusted=False,
        )

    if (
        policy_input.last_trusted_generation is None
        or policy_input.last_trusted_generation
        != policy_input.selection_generation
    ):
        return StateAwarePolicyDecision(
            mode="HOVER",
            reason="trusted_history_generation_mismatch",
            allow_normal_follow=False,
            update_last_trusted=False,
        )

    if (
        not _finite_nonnegative(policy_input.last_trusted_age_s)
        or policy_input.last_trusted_age_s
        > config.last_trusted_max_age_s
    ):
        return StateAwarePolicyDecision(
            mode="HOVER",
            reason="trusted_history_too_old",
            allow_normal_follow=False,
            update_last_trusted=False,
        )

    if (
        policy_input.last_trusted_horizontal_error is None
        or not math.isfinite(policy_input.last_trusted_horizontal_error)
        or policy_input.last_trusted_horizontal_error == 0.0
    ):
        return StateAwarePolicyDecision(
            mode="HOVER",
            reason="no_trusted_search_direction",
            allow_normal_follow=False,
            update_last_trusted=False,
        )

    if (
        not _finite_nonnegative(policy_input.recovery_elapsed_s)
        or policy_input.recovery_elapsed_s
        >= config.recovery_max_duration_s
    ):
        return StateAwarePolicyDecision(
            mode="HOVER",
            reason="recovery_timeout",
            allow_normal_follow=False,
            update_last_trusted=False,
        )

    if (
        not _finite_nonnegative(policy_input.recovery_integrated_yaw_rad)
        or policy_input.recovery_integrated_yaw_rad
        >= config.recovery_max_integrated_yaw_rad
    ):
        return StateAwarePolicyDecision(
            mode="HOVER",
            reason="recovery_yaw_budget_exhausted",
            allow_normal_follow=False,
            update_last_trusted=False,
        )

    yaw_magnitude = abs(float(config.recovery_yaw_rate))
    remaining_budget = max(
        0.0,
        config.recovery_max_integrated_yaw_rad
        - policy_input.recovery_integrated_yaw_rad,
    )

    if policy_input.dt_s > 0.0 and math.isfinite(policy_input.dt_s):
        yaw_magnitude = min(
            yaw_magnitude,
            remaining_budget / policy_input.dt_s,
        )

    if yaw_magnitude <= 0.0:
        return StateAwarePolicyDecision(
            mode="HOVER",
            reason="recovery_yaw_budget_exhausted",
            allow_normal_follow=False,
            update_last_trusted=False,
        )

    direction = (
        1.0
        if policy_input.last_trusted_horizontal_error > 0.0
        else -1.0
    )

    return StateAwarePolicyDecision(
        mode="RECOVERY_YAW_ONLY",
        reason="recent_lost_trusted_direction",
        allow_normal_follow=False,
        update_last_trusted=False,
        recovery_yaw_z=direction * yaw_magnitude,
    )
