"""Tests for the live recorder free-space refusal gate."""

import os
from pathlib import Path
import subprocess


REPO_ROOT = Path(__file__).resolve().parents[2]
LIBRARY = REPO_ROOT / "tools/lib/live_storage.sh"
LAUNCHER = REPO_ROOT / "tools/start_live_stack.sh"
DEFAULTS = REPO_ROOT / "tools/lib/live_defaults.sh"


def _run_guard(tmp_path: Path, available_kib: int, minimum_gib: str):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_df = fake_bin / "df"
    fake_df.write_text(
        "#!/usr/bin/env bash\n"
        "echo 'Filesystem 1024-blocks Used Available Capacity Mounted on'\n"
        f"echo '/dev/test 999999999 1 {available_kib} 1% /'\n",
        encoding="utf-8",
    )
    fake_df.chmod(0o755)
    environment = dict(os.environ)
    environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
    return subprocess.run(
        [
            "bash",
            "-c",
            'source "$1"; ensure_recording_storage_available "$2" "$3"',
            "bash",
            str(LIBRARY),
            str(tmp_path / "bags"),
            minimum_gib,
        ],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )


def test_guard_accepts_storage_above_threshold(tmp_path):
    result = _run_guard(tmp_path, 25 * 1024 * 1024, "20")

    assert result.returncode == 0
    assert result.stderr == ""


def test_guard_refuses_storage_below_threshold_without_deleting(tmp_path):
    result = _run_guard(tmp_path, 5 * 1024 * 1024, "20")

    assert result.returncode == 1
    assert "recording refused" in result.stdout
    assert "explicitly disposable runs" in result.stdout


def test_guard_rejects_invalid_threshold(tmp_path):
    result = _run_guard(tmp_path, 25 * 1024 * 1024, "0")

    assert result.returncode == 2
    assert "positive integer" in result.stdout


def test_live_launcher_wires_the_guard_before_camera_preflight():
    launcher = LAUNCHER.read_text(encoding="utf-8")
    defaults = DEFAULTS.read_text(encoding="utf-8")

    guard_position = launcher.index("ensure_recording_storage_available")
    camera_position = launcher.index("check_stuck_camera_processes", guard_position)

    assert 'source "$THESIS_ROOT/tools/lib/live_storage.sh"' in launcher
    assert guard_position < camera_position
    assert 'RECORDING_MIN_FREE_GIB="${RECORDING_MIN_FREE_GIB:-20}"' in defaults
