"""Issue #74: /control_ref/diagnostics is recorded and summarisable.

Non-ROS contracts: the launcher records the topic (and therefore its run
provenance inventory), the message carries the required fields, the summary
helper enforces the recovery/translation safety invariant, and the live
launcher still forces yaw recovery OFF with no activation path.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = REPO_ROOT / "tools/start_live_stack.sh"
MSG = REPO_ROOT / "ros2_ws/src/thesis_msgs/msg/ControlDiagnostics.msg"
MSG_CMAKE = REPO_ROOT / "ros2_ws/src/thesis_msgs/CMakeLists.txt"
HELPER = REPO_ROOT / "tools/analysis/summarize_control_diagnostics.py"

REQUIRED_MSG_FIELDS = (
    "mode",
    "reason",
    "tim_state",
    "tim_control_mode",
    "selection_generation",
    "status_fresh",
    "target_fresh",
    "recovery_enabled",
    "recovery_active",
    "recovery_direction",
    "recovery_elapsed_s",
    "recovery_yaw_rate",
    "recovery_integrated_yaw_rad",
    "recovery_max_integrated_yaw_rad",
    "recovery_max_duration_s",
    "last_trusted_age_s",
    "last_trusted_valid",
    "command_vx",
    "command_vy",
    "command_yaw_z",
)


def _load(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


summarize_mod = _load(HELPER)


# --------------------------------------------------------------------------- #
# G / H: recorded in the retained video bag (and its provenance inventory)
# --------------------------------------------------------------------------- #
def test_diagnostics_topic_is_recorded_next_to_cmd_vel_in_the_video_bag():
    source = LAUNCHER.read_text(encoding="utf-8")
    assert re.search(
        r"/control_ref/cmd_vel\s*\n\s*/control_ref/diagnostics",
        source,
    ), "diagnostics topic must sit beside /control_ref/cmd_vel in VIDEO_BAG_TOPICS"


def test_diagnostics_topic_in_video_bag_not_dataset_bag():
    # The video bag (and its run-metadata inventory, built from the same list)
    # gains the topic; the perception-only dataset bag does not. The topic name
    # also appears in the stop-time bag/evidence verification contract.
    source = LAUNCHER.read_text(encoding="utf-8")
    video = source[source.index("VIDEO_BAG_TOPICS=("):source.index("DATASET_BAG_TOPICS=(")]
    dataset = source[source.index("DATASET_BAG_TOPICS=("):
                     source.index("DATASET_BAG_TOPICS=(") + 600]
    assert video.count("/control_ref/diagnostics") == 1
    assert "/control_ref/diagnostics" not in dataset


# --------------------------------------------------------------------------- #
# message contract
# --------------------------------------------------------------------------- #
def test_control_diagnostics_message_exists_and_has_required_fields():
    assert MSG.is_file()
    assert '"msg/ControlDiagnostics.msg"' in MSG_CMAKE.read_text(
        encoding="utf-8"
    )
    text = MSG.read_text(encoding="utf-8")
    assert text.splitlines()[0].startswith("#")
    declared = {
        line.split()[1]
        for line in text.splitlines()
        if line.strip()
        and not line.lstrip().startswith("#")
        and len(line.split()) >= 2
    }
    missing = [f for f in REQUIRED_MSG_FIELDS if f not in declared]
    assert missing == [], f"missing message fields: {missing}"
    assert "std_msgs/Header header" in text


# --------------------------------------------------------------------------- #
# I: live launcher defaults recovery OFF; the candidate is deliberately gated
# --------------------------------------------------------------------------- #
def test_launcher_yaw_recovery_defaults_off_and_is_deliberately_gated():
    source = LAUNCHER.read_text(encoding="utf-8")
    defaults = (REPO_ROOT / "tools/lib/live_defaults.sh").read_text(
        encoding="utf-8"
    )
    cli = (REPO_ROOT / "tools/lib/live_cli.sh").read_text(encoding="utf-8")

    # default OFF
    assert 'CONTROL_YAW_RECOVERY_BOOL="false"' in defaults
    assert (
        'CONTROL_ENABLE_YAW_RECOVERY="${CONTROL_YAW_RECOVERY_BOOL:-false}"'
        in source
    )
    assert (
        "-p enable_yaw_recovery:=$CONTROL_ENABLE_YAW_RECOVERY" in source
    )

    # provenance asserts the trial condition dynamically
    assert (
        'control_ref_node:enable_yaw_recovery=$control_recovery_expect'
        in source
    )
    assert 'control_ref_node:enable_diagnostics=true' in source

    # candidate opt-in requires the acknowledgement + field control-trial path
    assert "--control-yaw-recovery)" in cli
    assert "--acknowledge-yaw-recovery-candidate)" in cli
    assert "add --acknowledge-yaw-recovery-candidate to proceed" in cli
    assert "--control-yaw-recovery requires the controller" in cli
    assert "--control-yaw-recovery is a closed-loop control-trial candidate" in cli
    assert "--control-yaw-recovery requires retained field recording" in cli

    # bounds are never exposed as trial-time CLI knobs
    for knob in ("--recovery-yaw-rate", "--recovery-timeout", "--recovery-budget",
                 "--recovery-max-duration", "--recovery-max-integrated",
                 "--last-trusted-max-age"):
        assert knob not in source
        assert knob not in cli


# --------------------------------------------------------------------------- #
# summary helper: safety invariant + recovery bookkeeping
# --------------------------------------------------------------------------- #
def _sample(**overrides):
    base = dict(
        stamp_ns=0,
        mode="HOVER",
        reason="recovery_disabled",
        tim_state="LOST",
        tim_control_mode="NO_CONTROL",
        selection_generation=3,
        status_fresh=True,
        target_fresh=True,
        target_valid=False,
        recovery_enabled=False,
        recovery_active=False,
        recovery_direction="unknown",
        recovery_elapsed_s=0.0,
        recovery_integrated_yaw_rad=0.0,
        recovery_budget_remaining_rad=0.1,
        recovery_max_integrated_yaw_rad=0.1,
        recovery_max_duration_s=1.0,
        last_trusted_valid=False,
        last_trusted_age_s=float("nan"),
        last_trusted_generation=-1,
        recovery_history_consumed=False,
        command_vx=0.0,
        command_vy=0.0,
        command_yaw_z=0.0,
        command_saturated_yaw=False,
    )
    base.update(overrides)
    return base


def test_summary_flags_translation_while_recovery_active():
    samples = [
        _sample(stamp_ns=0),
        _sample(
            stamp_ns=33_000_000,
            mode="RECOVERY_YAW_ONLY",
            recovery_enabled=True,
            recovery_active=True,
            command_vx=0.02,  # <-- forbidden
            command_yaw_z=0.03,
        ),
    ]
    result = summarize_mod.summarize(samples)
    assert result["ok"] is True
    assert result["safety_ok"] is False
    assert len(result["translation_during_recovery_violations"]) == 1
    assert result["translation_during_recovery_violations"][0]["command_vx"] == 0.02


def test_summary_counts_recovery_attempts_and_passes_when_clean():
    samples = [
        _sample(stamp_ns=0, mode="NORMAL_FOLLOW", reason="trusted_locked_normal"),
        _sample(stamp_ns=33_000_000, mode="RECOVERY_YAW_ONLY",
                recovery_enabled=True, recovery_active=True,
                command_yaw_z=0.03, recovery_integrated_yaw_rad=0.01),
        _sample(stamp_ns=66_000_000, mode="RECOVERY_YAW_ONLY",
                recovery_enabled=True, recovery_active=True,
                command_yaw_z=0.03, recovery_integrated_yaw_rad=0.05),
        _sample(stamp_ns=99_000_000, mode="HOVER",
                reason="recovery_yaw_budget_exhausted"),
        _sample(stamp_ns=132_000_000, mode="RECOVERY_YAW_ONLY",
                recovery_enabled=True, recovery_active=True,
                command_yaw_z=0.03),
    ]
    result = summarize_mod.summarize(samples)
    assert result["safety_ok"] is True
    assert result["recovery_attempt_count"] == 2
    assert result["max_recovery_integrated_yaw_rad"] == 0.05
    assert result["mode_message_counts"]["RECOVERY_YAW_ONLY"] == 3


def test_summary_reports_no_samples():
    result = summarize_mod.summarize([])
    assert result["ok"] is False
