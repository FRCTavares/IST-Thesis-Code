"""Fail-closed contracts for the one-command field preflight."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools/flight/field_preflight_check.sh"
SOURCE = SCRIPT.read_text(encoding="utf-8")


def _function(name: str, next_name: str) -> str:
    return SOURCE.split(f"{name}() {{", 1)[1].split(f"{next_name}() {{", 1)[0]


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _evidence(tmp_path: Path, *, transport="observed_zero", loss=0, visual=True):
    bag = tmp_path / "bag"
    bag.mkdir()
    _write(bag / "bag_integrity.json", {
        "passed": True,
        "storage_identifier": "mcap",
        "duration_ns": 10_000_000_000,
        "total_bytes": 1000,
        "topic_message_counts": {"/detections": 300, "/tracks": 300},
    })
    _write(bag / "recorder_transport_status.json", {
        "quality_status": transport,
        "recorders": {"main": {
            "reported_transport_loss_count": loss,
            "parse_ok": transport != "unavailable",
        }},
    })
    _write(bag / "visual_evidence_status.json", {
        "passed": visual,
        "recorder_alive_at_stop": visual,
        "finalization": "graceful" if visual else "failed",
        "codec": "mjpeg",
        "width": 640,
        "height": 480,
        "measured_fps": 10.0,
        "decoded_frames": 100,
    })
    _write(bag / "evidence_package_status.json", {
        "runtime_status": "complete_runtime_evidence" if visual else "incomplete_runtime_evidence",
        "pending": ["pending_pixhawk_dataflash"],
        "problems": [] if visual else ["visual evidence failed"],
    })
    return bag


def _source_and_run(command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-c", f'source "$1"; {command}', "bash", str(SCRIPT)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_script_syntax_and_non_actuating_command_contract():
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True)
    forbidden = (
        "ros2 topic pub",
        "/mavros/cmd/arming",
        "/mavros/set_mode",
        "nmcli connection up",
        "nmcli connection down",
        "nmcli connection modify",
        "systemctl enable",
        "systemctl disable",
    )
    for token in forbidden:
        assert token not in SOURCE
    assert "READY FOR FLIGHT" not in SOURCE


def test_default_static_path_is_observational_and_checks_required_contracts():
    static = _function("run_static_checks", "passive_cleanup")
    assert "run_passive_live_gate" not in static
    assert "kill " not in static
    assert "pkill" not in static
    assert "rm " not in static
    assert "check_repository" in static
    assert "check_storage" in static
    assert "check_field_network" in static
    assert "check_hardware" in static
    assert "check_no_stale_processes" in static

    assert "validate_tim_evaluation_split.py" in SOURCE
    assert "final_ready=3/3" in SOURCE
    assert "RECORDING_MIN_FREE_GIB" in SOURCE
    assert 'ip route show default dev "$ETHERNET_INTERFACE"' in SOURCE
    assert "systemctl is-active tailscaled.service" in SOURCE
    assert "THESIS_HOST_MODE" in SOURCE
    assert 'media-ctl -d "$candidate" -p' in SOURCE
    assert "rp1-cfe" in SOURCE and "tevs" in SOURCE
    assert "command -v ros2" not in SOURCE
    assert "-x /opt/ros/jazzy/bin/ros2" in SOURCE
    assert "ancestor chain" in SOURCE


def test_repository_gate_accepts_completed_frozen_split_and_rejects_old_state():
    completed = _source_and_run(
        "python3() { printf '[ok] split=frozen final_ready=3/3\\n'; }; "
        "FAILURES=0; check_repository; echo \"FAILURES=$FAILURES\""
    )
    assert "PASS  Stage-7 freeze: final_ready=3/3" in completed.stdout
    incomplete = _source_and_run(
        "python3() { printf '[ok] split=frozen final_ready=0/3\\n'; }; "
        "FAILURES=0; check_repository; echo \"FAILURES=$FAILURES\""
    )
    assert "FAIL  Stage-7 freeze validation" in incomplete.stdout


def test_passive_gate_uses_only_field_record_no_control():
    live = _function("run_passive_live_gate", "print_human_gates")
    assert '--res vga --field-record --no-control --tag' in live
    assert "--control-mavros" not in live
    assert "--record-raw" not in live
    assert "printf 'stop\\n'" in live
    assert "PASSIVE_GATE_SECONDS < 30" in live
    assert "PASSIVE_GATE_SECONDS > 45" in live


def test_passive_mavros_gate_checks_disarmed_body_frame_and_zero_publishers():
    observe = _function("observe_live_mavros", "check_passive_evidence")
    assert "/mavros/state" in observe
    assert "connected: true" in observe
    assert "armed: false" in observe
    assert "/mavros/imu/data_raw" in observe
    assert "String value is: BODY_NED" in observe
    assert "/mavros/setpoint_velocity/cmd_vel" in observe
    assert "Publisher count: 0" in observe
    assert "ros2 topic pub" not in observe


def test_zero_loss_valid_visual_evidence_passes(tmp_path: Path):
    bag = _evidence(tmp_path)
    result = _source_and_run(
        f'FAILURES=0; check_passive_evidence "{bag}"; rc=$?; '
        'echo "FAILURES=$FAILURES"; exit "$rc"'
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "structured recorder: observed_zero transport loss" in result.stdout
    assert "visual evidence and evidence-package finalization" in result.stdout
    assert "FAILURES=0" in result.stdout


def test_nonzero_transport_loss_fails(tmp_path: Path):
    bag = _evidence(tmp_path, transport="observed_nonzero", loss=1)
    result = _source_and_run(
        f'FAILURES=0; check_passive_evidence "{bag}"; '
        'echo "FAILURES=$FAILURES"'
    )
    assert "runtime_evidence_acceptable: False" in result.stdout
    assert "FAILURES=1" in result.stdout


def test_unavailable_transport_loss_fails(tmp_path: Path):
    bag = _evidence(tmp_path, transport="unavailable", loss=None)
    result = _source_and_run(
        f'FAILURES=0; check_passive_evidence "{bag}"; '
        'echo "FAILURES=$FAILURES"'
    )
    assert "transport: unavailable" in result.stdout
    assert "FAILURES=1" in result.stdout


def test_failed_visual_verification_fails(tmp_path: Path):
    bag = _evidence(tmp_path, visual=False)
    result = _source_and_run(
        f'FAILURES=0; check_passive_evidence "{bag}"; '
        'echo "FAILURES=$FAILURES"'
    )
    assert "visual: passed=False" in result.stdout
    assert "FAILURES=1" in result.stdout


def test_final_status_only_claims_software_passive_readiness():
    ready = _source_and_run("FAILURES=0; print_final_status")
    blocked = _source_and_run("FAILURES=2; print_final_status")
    assert ready.returncode == 0
    assert ready.stdout.rstrip().endswith(
        "SOFTWARE/PASSIVE PREFLIGHT: READY FOR HUMAN PHYSICAL SAFETY GATES"
    )
    assert "READY FOR FLIGHT" not in ready.stdout
    assert blocked.returncode == 1
    assert "SOFTWARE/PASSIVE PREFLIGHT: NOT READY" in blocked.stdout
    for gate in ("RC takeover", "PreArm/arming", "direction/sign", "pilot judgement"):
        assert gate in ready.stdout
