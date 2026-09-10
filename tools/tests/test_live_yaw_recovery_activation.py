"""Issue #74 bounded yaw-only recovery: deliberate, default-OFF launcher opt-in.

The candidate policy itself is frozen and already tested; this file only
covers the launcher activation plumbing -- default baseline, the gated
candidate path, fail-before-launch on every missing prerequisite, provenance
condition, and that no recovery bound leaked out as a CLI knob.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB = REPO_ROOT / "tools" / "lib"
LAUNCHER = (REPO_ROOT / "tools/start_live_stack.sh").read_text(encoding="utf-8")
CLI = (LIB / "live_cli.sh").read_text(encoding="utf-8")
USAGE = (LIB / "live_usage.sh").read_text(encoding="utf-8")
DEFAULTS = (LIB / "live_defaults.sh").read_text(encoding="utf-8")

_HARNESS = (
    "set +u; "
    f"source '{LIB}/live_usage.sh'; "
    f"source '{LIB}/live_defaults.sh'; "
    f"source '{LIB}/live_storage.sh'; "
    f"source '{LIB}/live_cli.sh'; "
    'parse_and_validate_live_stack_args "$@"; '
    'rc=$?; '
    'echo "RESOLVE recovery=$CONTROL_YAW_RECOVERY_BOOL '
    'ack=$CONTROL_YAW_RECOVERY_ACKNOWLEDGED control=$ENABLE_CONTROL '
    'mavros=$CONTROL_MAVROS_BOOL field=$FIELD_MAVROS_RECORD rosbag=$ENABLE_ROSBAG"; '
    "exit $rc"
)


@pytest.fixture(scope="module")
def fake_root():
    with tempfile.TemporaryDirectory(prefix="yaw_recovery_") as tmp:
        root = Path(tmp)
        (root / "models/hef").mkdir(parents=True)
        (root / "models/reid").mkdir(parents=True)
        cfg = root / (
            "ros2_ws/install/thesis_bringup/share/thesis_bringup/config"
        )
        cfg.mkdir(parents=True)
        (root / "models/hef/yolov8s.hef").write_text("stub")
        (root / "models/reid/mars-small128.pb").write_text("stub")
        (cfg / "tim_mars_canonical.yaml").write_text("stub: true\n")
        yield root


def run_parser(fake_root: Path, *args: str):
    result = subprocess.run(
        ["bash", "-c", _HARNESS, "bash", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={
            "PATH": "/usr/bin:/bin",
            "HOME": str(fake_root),
            "THESIS_ROOT": str(fake_root),
        },
    )
    return result


def _resolved(result) -> dict[str, str]:
    line = next(
        ln for ln in result.stdout.splitlines() if ln.startswith("RESOLVE ")
    )
    out = {}
    for pair in line[len("RESOLVE "):].split():
        key, _, value = pair.partition("=")
        out[key] = value
    return out


# --------------------------------------------------------------------------- #
# A. default baseline
# --------------------------------------------------------------------------- #
def test_no_new_flags_resolves_to_recovery_off(fake_root):
    for args in ([], ["--record", "--tag", "t"], ["--field-record", "--tag", "t"]):
        result = run_parser(fake_root, *args)
        assert result.returncode == 0, result.stderr + result.stdout
        assert _resolved(result)["recovery"] == "false"


# --------------------------------------------------------------------------- #
# B. explicit candidate with the full field control-trial path
# --------------------------------------------------------------------------- #
def test_full_candidate_invocation_resolves_to_recovery_on(fake_root):
    result = run_parser(
        fake_root,
        "--field-record",
        "--control-mavros",
        "--control-yaw-recovery",
        "--acknowledge-yaw-recovery-candidate",
        "--tag",
        "cand",
    )
    assert result.returncode == 0, result.stderr + result.stdout
    resolved = _resolved(result)
    assert resolved["recovery"] == "true"
    assert resolved["ack"] == "1"
    assert resolved["control"] == "1"
    assert resolved["mavros"] == "true"
    assert resolved["field"] == "1"


# --------------------------------------------------------------------------- #
# C. missing acknowledgement -> fail before launch
# --------------------------------------------------------------------------- #
def test_candidate_without_acknowledgement_fails(fake_root):
    result = run_parser(
        fake_root,
        "--field-record",
        "--control-mavros",
        "--control-yaw-recovery",
        "--tag",
        "cand",
    )
    assert result.returncode != 0
    assert "EXPERIMENTAL Issue #74" in result.stdout
    assert "--acknowledge-yaw-recovery-candidate" in result.stdout


# --------------------------------------------------------------------------- #
# D. missing retained recording / MAVROS control -> fail before launch
# --------------------------------------------------------------------------- #
def test_candidate_without_retained_field_recording_fails(fake_root):
    # --control-mavros without --field-record is already rejected upstream.
    result = run_parser(
        fake_root,
        "--control-mavros",
        "--control-yaw-recovery",
        "--acknowledge-yaw-recovery-candidate",
    )
    assert result.returncode != 0
    assert "retained field" in result.stdout


def test_candidate_recording_only_without_mavros_control_fails(fake_root):
    result = run_parser(
        fake_root,
        "--record",
        "--control-yaw-recovery",
        "--acknowledge-yaw-recovery-candidate",
        "--tag",
        "x",
    )
    assert result.returncode != 0
    assert "closed-loop control-trial candidate" in result.stdout


# --------------------------------------------------------------------------- #
# E. missing controller -> fail before launch
# --------------------------------------------------------------------------- #
def test_candidate_without_controller_fails(fake_root):
    result = run_parser(
        fake_root,
        "--field-record",
        "--control-mavros",
        "--no-control",
        "--control-yaw-recovery",
        "--acknowledge-yaw-recovery-candidate",
    )
    assert result.returncode != 0
    assert "requires the controller" in result.stdout


def test_bare_candidate_flag_fails(fake_root):
    result = run_parser(fake_root, "--control-yaw-recovery")
    assert result.returncode != 0


# --------------------------------------------------------------------------- #
# F / G. provenance freezes the trial condition dynamically
# --------------------------------------------------------------------------- #
def test_provenance_expectation_is_condition_dependent():
    assert 'control_recovery_expect="false"' in LAUNCHER
    assert 'control_recovery_expect="true"' in LAUNCHER
    assert (
        '--expect-param "control_ref_node:enable_yaw_recovery=$control_recovery_expect"'
        in LAUNCHER
    )
    # the metadata sidecar records the human-readable condition too
    assert "control_yaw_recovery_enabled=${CONTROL_YAW_RECOVERY_BOOL:-false}" in LAUNCHER
    assert "trial_condition=" in LAUNCHER


# --------------------------------------------------------------------------- #
# H. diagnostics / operator-event alignment
# --------------------------------------------------------------------------- #
def test_startup_prints_condition_and_ready_operator_event_command():
    assert "[candidate] #74 bounded yaw-only recovery ENABLED" in LAUNCHER
    assert "[baseline] yaw recovery disabled" in LAUNCHER
    assert (
        "operator_event.py trial_start --run-id $RUN_ID --condition candidate"
        in LAUNCHER
    )
    assert "--recovery-enabled" in LAUNCHER
    assert (
        "operator_event.py trial_start --run-id $RUN_ID --condition baseline"
        in LAUNCHER
    )


# --------------------------------------------------------------------------- #
# J. no recovery bound is exposed as a CLI knob
# --------------------------------------------------------------------------- #
def test_recovery_bounds_are_not_cli_tuning_knobs():
    for knob in (
        "--recovery-yaw-rate",
        "--recovery-timeout",
        "--recovery-budget",
        "--recovery-max-duration",
        "--recovery-max-integrated-yaw",
        "--recovery-last-trusted-max-age",
        "--last-trusted-max-age",
    ):
        assert knob not in CLI
        assert knob not in USAGE
        assert knob not in LAUNCHER
    # the frozen node defaults are untouched
    node = (
        REPO_ROOT
        / "ros2_ws/src/thesis_bringup/thesis_bringup/control/control_ref_node.py"
    ).read_text(encoding="utf-8")
    assert "self.declare_parameter('recovery_yaw_rate', 0.10)" in node
    assert "self.declare_parameter('recovery_max_duration_s', 1.0)" in node
    assert "declare_parameter('enable_yaw_recovery', False)" in node


def test_help_text_documents_the_gated_candidate():
    assert "--control-yaw-recovery" in USAGE
    assert "--acknowledge-yaw-recovery-candidate" in USAGE
    assert "default OFF" in USAGE
