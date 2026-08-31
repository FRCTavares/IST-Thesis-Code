from __future__ import annotations

import pytest

from thesis_bringup.control.state_aware_policy import (
    StateAwarePolicyConfig,
    StateAwarePolicyInput,
    resolve_state_aware_policy,
)


def policy_input(**overrides):
    values = {
        "state": "LOCKED",
        "control_mode": "NORMAL",
        "target_valid": True,
        "target_frame_id": 100,
        "status_frame_id": 100,
        "status_fresh": True,
        "selection_generation": 3,
        "last_trusted_generation": 3,
        "last_trusted_horizontal_error": 0.25,
        "last_trusted_age_s": 0.20,
        "recovery_elapsed_s": 0.20,
        "recovery_integrated_yaw_rad": 0.01,
        "dt_s": 0.10,
    }
    values.update(overrides)
    return StateAwarePolicyInput(**values)


def enabled_config(**overrides):
    values = {
        "recovery_enabled": True,
        "recovery_yaw_rate": 0.05,
        "recovery_max_duration_s": 1.0,
        "recovery_max_integrated_yaw_rad": 0.05,
        "last_trusted_max_age_s": 1.0,
    }
    values.update(overrides)
    return StateAwarePolicyConfig(**values)


def test_locked_normal_causal_target_allows_normal_follow():
    decision = resolve_state_aware_policy(
        policy_input(),
        enabled_config(),
    )

    assert decision.mode == "NORMAL_FOLLOW"
    assert decision.allow_normal_follow
    assert decision.translation_allowed
    assert decision.update_last_trusted
    assert decision.recovery_yaw_z == 0.0


def test_target_status_frame_mismatch_fails_safe():
    decision = resolve_state_aware_policy(
        policy_input(status_frame_id=99),
        enabled_config(),
    )

    assert decision.mode == "HOVER"
    assert not decision.translation_allowed


@pytest.mark.parametrize(
    ("state", "control_mode"),
    [
        ("UNCERTAIN", "YAW_ONLY"),
        ("REACQUIRED", "CONFIRM"),
        ("NO_TARGET", "NO_CONTROL"),
    ],
)
def test_untrusted_tim_states_do_not_obtain_motion_authority(
    state,
    control_mode,
):
    decision = resolve_state_aware_policy(
        policy_input(
            state=state,
            control_mode=control_mode,
            target_valid=False,
        ),
        enabled_config(),
    )

    assert decision.mode == "HOVER"
    assert not decision.translation_allowed
    assert decision.recovery_yaw_z == 0.0


def test_recovery_disabled_preserves_hover_on_loss():
    decision = resolve_state_aware_policy(
        policy_input(
            state="LOST",
            control_mode="HOVER",
            target_valid=False,
        ),
        StateAwarePolicyConfig(recovery_enabled=False),
    )

    assert decision.mode == "HOVER"
    assert decision.reason == "recovery_disabled"
    assert decision.recovery_yaw_z == 0.0


@pytest.mark.parametrize(
    ("horizontal_error", "expected_sign"),
    [
        (0.25, 1.0),
        (-0.25, -1.0),
    ],
)
def test_recent_loss_uses_only_last_trusted_yaw_direction(
    horizontal_error,
    expected_sign,
):
    decision = resolve_state_aware_policy(
        policy_input(
            state="LOST",
            control_mode="HOVER",
            target_valid=False,
            last_trusted_horizontal_error=horizontal_error,
        ),
        enabled_config(),
    )

    assert decision.mode == "RECOVERY_YAW_ONLY"
    assert not decision.translation_allowed
    assert decision.recovery_yaw_z * expected_sign > 0.0


def test_recovery_timeout_returns_zero():
    decision = resolve_state_aware_policy(
        policy_input(
            state="LOST",
            control_mode="HOVER",
            target_valid=False,
            recovery_elapsed_s=1.0,
        ),
        enabled_config(),
    )

    assert decision.mode == "HOVER"
    assert decision.reason == "recovery_timeout"
    assert decision.recovery_yaw_z == 0.0


def test_old_trusted_observation_returns_zero():
    decision = resolve_state_aware_policy(
        policy_input(
            state="LOST",
            control_mode="HOVER",
            target_valid=False,
            last_trusted_age_s=1.01,
        ),
        enabled_config(),
    )

    assert decision.mode == "HOVER"
    assert decision.reason == "trusted_history_too_old"


def test_selection_generation_change_cancels_old_history():
    decision = resolve_state_aware_policy(
        policy_input(
            state="LOST",
            control_mode="HOVER",
            target_valid=False,
            selection_generation=4,
            last_trusted_generation=3,
        ),
        enabled_config(),
    )

    assert decision.mode == "HOVER"
    assert decision.reason == "trusted_history_generation_mismatch"


def test_stale_status_fails_safe():
    decision = resolve_state_aware_policy(
        policy_input(
            state="LOST",
            control_mode="HOVER",
            target_valid=False,
            status_fresh=False,
        ),
        enabled_config(),
    )

    assert decision.mode == "HOVER"
    assert decision.reason == "status_not_fresh"


def test_recovery_yaw_is_limited_by_remaining_integrated_budget():
    decision = resolve_state_aware_policy(
        policy_input(
            state="LOST",
            control_mode="HOVER",
            target_valid=False,
            recovery_integrated_yaw_rad=0.049,
            dt_s=0.10,
        ),
        enabled_config(
            recovery_yaw_rate=0.05,
            recovery_max_integrated_yaw_rad=0.05,
        ),
    )

    assert decision.mode == "RECOVERY_YAW_ONLY"
    assert decision.recovery_yaw_z == pytest.approx(0.01)


def test_exhausted_recovery_budget_returns_zero():
    decision = resolve_state_aware_policy(
        policy_input(
            state="LOST",
            control_mode="HOVER",
            target_valid=False,
            recovery_integrated_yaw_rad=0.05,
        ),
        enabled_config(),
    )

    assert decision.mode == "HOVER"
    assert decision.reason == "recovery_yaw_budget_exhausted"
    assert decision.recovery_yaw_z == 0.0
