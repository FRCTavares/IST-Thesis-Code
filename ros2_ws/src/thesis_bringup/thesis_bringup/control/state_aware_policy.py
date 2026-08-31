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
    recovery_history_consumed: bool = False
    target_source_stamp_ns: int = 0
    status_source_stamp_ns: int = 0


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


@dataclass(frozen=True)
class RecoveryYawCommandDecision:
    yaw_z: float
    budget_exhausted: bool


def resolve_bounded_recovery_yaw(
    *,
    desired_yaw_z: float,
    previous_yaw_z: float,
    invert_yaw: bool,
    max_yaw_z: float,
    max_delta_yaw_z: float,
    dt_s: float,
    remaining_integrated_yaw_rad: float,
) -> RecoveryYawCommandDecision:
    """Apply direction, saturation, slew and hard integrated-yaw budget."""
    desired = float(desired_yaw_z)
    if invert_yaw:
        desired = -desired

    max_yaw = max(0.0, abs(float(max_yaw_z)))
    desired = max(-max_yaw, min(max_yaw, desired))

    previous = float(previous_yaw_z)
    max_delta = max(0.0, abs(float(max_delta_yaw_z)))
    delta = max(
        -max_delta,
        min(max_delta, desired - previous),
    )
    candidate = previous + delta

    if desired != 0.0 and candidate * desired < 0.0:
        candidate = 0.0

    remaining = max(
        0.0,
        float(remaining_integrated_yaw_rad),
    )
    dt = max(0.0, float(dt_s))

    if remaining <= 0.0:
        return RecoveryYawCommandDecision(
            yaw_z=0.0,
            budget_exhausted=True,
        )

    if dt > 0.0 and abs(candidate) * dt > remaining + 1e-12:
        return RecoveryYawCommandDecision(
            yaw_z=0.0,
            budget_exhausted=True,
        )

    return RecoveryYawCommandDecision(
        yaw_z=candidate,
        budget_exhausted=False,
    )


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
        and policy_input.target_source_stamp_ns > 0
        and policy_input.status_source_stamp_ns > 0
        and policy_input.target_source_stamp_ns
        == policy_input.status_source_stamp_ns
    )

    if not policy_input.status_fresh:
        return StateAwarePolicyDecision(
            mode="HOVER",
            reason="status_not_fresh",
            allow_normal_follow=False,
            update_last_trusted=False,
        )

    if (
        policy_input.state == "LOCKED"
        and policy_input.control_mode == "NORMAL"
    ):
        if not causal_pair:
            return StateAwarePolicyDecision(
                mode="HOVER",
                reason="authority_frame_mismatch",
                allow_normal_follow=False,
                update_last_trusted=False,
            )

        if not policy_input.target_valid:
            return StateAwarePolicyDecision(
                mode="HOVER",
                reason="trusted_target_not_valid",
                allow_normal_follow=False,
                update_last_trusted=False,
            )

        return StateAwarePolicyDecision(
            mode="NORMAL_FOLLOW",
            reason="trusted_locked_normal",
            allow_normal_follow=True,
            update_last_trusted=True,
        )

    if policy_input.state != "LOST":
        return StateAwarePolicyDecision(
            mode="HOVER",
            reason=(
                "state_not_trusted:"
                f"{policy_input.state}/{policy_input.control_mode}"
            ),
            allow_normal_follow=False,
            update_last_trusted=False,
        )

    if not config.recovery_enabled:
        return StateAwarePolicyDecision(
            mode="HOVER",
            reason="recovery_disabled",
            allow_normal_follow=False,
            update_last_trusted=False,
        )

    if policy_input.recovery_history_consumed:
        return StateAwarePolicyDecision(
            mode="HOVER",
            reason="trusted_history_already_consumed",
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
