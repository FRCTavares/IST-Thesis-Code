from __future__ import annotations

import ast
from pathlib import Path

import pytest

from thesis_bringup.control.tim_authority_status import (
    evaluate_authority_epoch,
    parse_tim_authority_status,
)


CONTROL_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "thesis_bringup"
    / "control"
    / "control_ref_node.py"
)


def test_full_status_parses_controller_authority_fields():
    status = parse_tim_authority_status(
        """
        {
          "state": "LOCKED",
          "control_mode": "NORMAL",
          "selection_generation": 4,
          "selection_session_id": "session-current",
          "frame_id": 91,
          "track_timestamp_ns": 5000000000,
          "target_track_id": 7,
          "freshness_is_fresh": true,
          "reason": "accepted_candidate"
        }
        """
    )

    assert status.state == "LOCKED"
    assert status.control_mode == "NORMAL"
    assert status.selection_generation == 4
    assert status.selection_session_id == "session-current"
    assert status.frame_id == 91
    assert status.source_stamp_ns == 5_000_000_000
    assert status.target_track_id == 7
    assert status.freshness_is_fresh


def test_status_only_authority_transaction_has_no_frame():
    status = parse_tim_authority_status(
        """
        {
          "state": "NO_TARGET",
          "control_mode": "NO_CONTROL",
          "selection_generation": 8,
          "selection_session_id": "session-current",
          "target_track_id": null,
          "reason": "operator_clear"
        }
        """
    )

    assert status.selection_generation == 8
    assert status.frame_id is None
    assert not status.freshness_is_fresh


@pytest.mark.parametrize(
    "payload",
    [
        '{"state":"LOCKED","control_mode":"NORMAL"}',
        (
            '{"state":"LOCKED","control_mode":"NORMAL",'
            '"selection_generation":-1,"selection_session_id":"s"}'
        ),
        (
            '{"state":"LOCKED","control_mode":"NORMAL",'
            '"selection_generation":true,"selection_session_id":"s"}'
        ),
        '{"state":"LOCKED","control_mode":"NORMAL","selection_generation":1}',
        (
            '{"state":"LOCKED","control_mode":"NORMAL",'
            '"selection_generation":1,"selection_session_id":""}'
        ),
        'not-json',
    ],
)
def test_missing_or_invalid_generation_fails_closed(payload):
    with pytest.raises(ValueError):
        parse_tim_authority_status(payload)


def test_controller_has_no_raw_target_default_or_tracks_subscription():
    source = CONTROL_SOURCE.read_text(encoding="utf-8")

    assert "'/target_memory_mars'" in source
    assert "'/target_memory_mars/status'" in source
    assert "create_subscription(" in source
    assert "'/tracks'" not in source

    tree = ast.parse(source)
    cls = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "ControlRefNode"
    )
    methods = {
        node.name: node
        for node in cls.body
        if isinstance(node, ast.FunctionDef)
    }

    assert "on_status" in methods
    assert "on_timer" in methods

    timer_calls = [
        node.func.id
        for node in ast.walk(methods["on_timer"])
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
    ]
    assert "resolve_state_aware_policy" in timer_calls


def test_generation_change_path_clears_trusted_history_and_zeroes():
    tree = ast.parse(CONTROL_SOURCE.read_text(encoding="utf-8"))
    cls = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "ControlRefNode"
    )
    method = next(
        node
        for node in cls.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "on_status"
    )

    attributes = [
        node.func.attr
        for node in ast.walk(method)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
    ]

    assert "clear_trusted_history" in attributes
    assert "publish_zero" in attributes


def test_same_session_generation_advance_is_accepted_and_resets():
    decision = evaluate_authority_epoch(
        current_session_id="session-a",
        current_generation=3,
        retired_session_ids=set(),
        incoming_session_id="session-a",
        incoming_generation=4,
    )

    assert decision.accepted
    assert decision.reset_authority
    assert decision.reason == "generation_advance"


def test_same_session_generation_rollback_is_rejected():
    decision = evaluate_authority_epoch(
        current_session_id="session-a",
        current_generation=4,
        retired_session_ids=set(),
        incoming_session_id="session-a",
        incoming_generation=3,
    )

    assert not decision.accepted
    assert decision.reset_authority
    assert decision.reason == "generation_rollback"


def test_new_tim_session_is_accepted_as_hard_reset():
    decision = evaluate_authority_epoch(
        current_session_id="session-a",
        current_generation=4,
        retired_session_ids=set(),
        incoming_session_id="session-b",
        incoming_generation=0,
    )

    assert decision.accepted
    assert decision.reset_authority
    assert decision.reason == "new_authority_session"


def test_delayed_retired_tim_session_is_rejected():
    decision = evaluate_authority_epoch(
        current_session_id="session-b",
        current_generation=1,
        retired_session_ids={"session-a"},
        incoming_session_id="session-a",
        incoming_generation=99,
    )

    assert not decision.accepted
    assert decision.reset_authority
    assert decision.reason == "retired_session"


def test_recovery_feature_defaults_off():
    source = CONTROL_SOURCE.read_text(encoding="utf-8")

    assert "declare_parameter('enable_yaw_recovery', False)" in source
    assert "recovery_enabled=self.enable_yaw_recovery" in source


def test_recovery_path_hard_zeros_translation():
    source = CONTROL_SOURCE.read_text(encoding="utf-8")

    assert "def handle_recovery_yaw(" in source
    assert "self.prev_vx = 0.0" in source
    assert "self.prev_vy = 0.0" in source
    assert (
        "self.publish_pair(\n"
        "            now.to_msg(),\n"
        "            0.0,\n"
        "            0.0,\n"
        "            self.prev_yaw_z,"
    ) in source


def test_recovery_starts_from_hard_zero():
    source = CONTROL_SOURCE.read_text(encoding="utf-8")

    assert "def begin_recovery(" in source
    assert "self.prev_vx = 0.0" in source
    assert "self.prev_vy = 0.0" in source
    assert "self.prev_yaw_z = 0.0" in source


def test_new_trusted_observation_rearms_recovery():
    source = CONTROL_SOURCE.read_text(encoding="utf-8")

    assert "self.recovery_consumed_trusted_stamp_ns = None" in source
    assert "self.recovery_history_consumed()" in source
    assert "self.consume_current_trusted_history()" in source


def test_recovery_diagnostics_cover_required_fields():
    source = CONTROL_SOURCE.read_text(encoding="utf-8")

    required_tokens = {
        "mode=",
        "reason=",
        "tim_state=",
        "tim_control_mode=",
        "selection_generation=",
        "selection_session=",
        "status_fresh=",
        "recovery_enabled=",
        "recovery_active=",
        "trusted_history_age_s=",
        "recovery_direction=",
        "recovery_elapsed_s=",
        "recovery_integrated_yaw_rad=",
        "recovery_budget_remaining_rad=",
        "saturation=",
        "final_command=",
    }

    for token in required_tokens:
        assert token in source

    assert "def maybe_log_recovery_diagnostics(" in source
