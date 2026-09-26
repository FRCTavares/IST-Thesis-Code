"""Synthetic capture identity tests: no ROS, devices or real evidence."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = (ROOT / "tools/start_live_stack.sh").read_text()
# Execute the real launcher's initialization, stopping before any log creation.
PREFIX = LAUNCHER[:LAUNCHER.index("declare -A PROC_PIDS")]
SOURCE_PATHS = LAUNCHER[
    LAUNCHER.index('    SOURCE_ROOT="${SOURCE_RECORD_ROOT'):
    LAUNCHER.index('    if [[ "${SOURCE_RAW_IMAGE_RECORD:-0}" -eq 1 ]]; then',
                   LAUNCHER.index('    SOURCE_ROOT="${SOURCE_RECORD_ROOT'))
]


def shell(script, env):
    return subprocess.run(["bash", "-c", script], env=env,
                          capture_output=True, text=True, check=False)


def environment(root):
    env = dict(os.environ)
    env.pop("RUN_ID", None)
    env.update(THESIS_ROOT=str(root), ROS_WS=str(root / "ros2_ws"),
               SOURCE_RECORD_ROOT=str(root / "ram"))
    return env


@pytest.mark.parametrize("supplied", ["known_test_id", "2026-09-09__12-34-56", "run.v1"])
def test_launcher_preserves_supplied_id(supplied):
    env = environment(ROOT)
    env["RUN_ID"] = supplied
    result = shell(PREFIX + '\nprintf "%s" "$RUN_ID"', env)
    assert result.returncode == 0, result.stderr
    assert result.stdout == supplied


def test_launcher_generates_id_when_unset():
    result = shell(PREFIX + '\nprintf "%s" "$RUN_ID"', environment(ROOT))
    assert result.returncode == 0
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}__\d{2}-\d{2}-\d{2}", result.stdout)


@pytest.mark.parametrize("unsafe", ["", " ", "../escape", "a/b", "..", ".", "a..b", "a\\b"])
def test_launcher_rejects_unsafe_id(unsafe):
    env = environment(ROOT)
    env["RUN_ID"] = unsafe
    result = shell(PREFIX, env)
    assert result.returncode == 2
    assert "RUN_ID" in result.stderr


def fixture_tree(tmp_path, behavior="success"):
    (tmp_path / "tools/lib").mkdir(parents=True)
    shutil.copy(ROOT / "tools/lib/live_run_id.sh", tmp_path / "tools/lib")
    # Synthetic pending metadata only; never load a real held-out reference/bag.
    split = tmp_path / "docs/data/splits/tim_mars_split_v4.json"
    split.parent.mkdir(parents=True)
    split.write_text(json.dumps({"sets": {"final_held_out": [
        {"id": "heldout_h01_exit_reentry", "status": "reserved_pending_capture"}
    ]}}))
    validator = tmp_path / "tools/analysis/validate_tim_evaluation_split.py"
    validator.parent.mkdir()
    validator.write_text("raise SystemExit(0)\n")
    fake = tmp_path / "tools/start_live_stack.sh"
    # Delay across a full second, then execute actual launcher identity/path
    # derivation. The old unconditional date assignment fails these tests.
    fake.write_text("#!/usr/bin/env bash\nsleep 1.1\n" + PREFIX +
                    '\nBAG_TAG="${@: -1}"\nSOURCE_DETECTIONS_RECORD=1\n' +
                    SOURCE_PATHS + '''
if [[ "$TEST_BEHAVIOR" == missing ]]; then
    SOURCE_RAW_BAG_OUT_DIR="$SOURCE_ROOT/unexpected_capture"
fi
mkdir -p "$SOURCE_RAW_BAG_OUT_DIR"
printf 'synthetic metadata' > "$SOURCE_RAW_BAG_OUT_DIR/metadata.yaml"
printf 'synthetic payload' > "$SOURCE_RAW_BAG_OUT_DIR/fixture.mcap"
if [[ "$TEST_BEHAVIOR" == failure ]]; then exit 7; fi
''')
    fake.chmod(0o755)
    env = environment(tmp_path)
    env.update(RUN_ID="known_test_id", TEST_BEHAVIOR=behavior)
    return env


def capture_paths(root):
    tag = "p027_h01_exit_reentry"
    base = root / "bags/source/held_out/2026-09/h01_exit_reentry"
    source = base / f"known_test_id__source__{tag}__image_raw_detections"
    final = root / "bags/source_video" / source.name
    return source, final


def run_helper(env):
    return subprocess.run(
        [
            "bash",
            str(ROOT / "tools/experiments/record_p027_heldout_sequence.sh"),
            "h01",
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_delayed_capture_uses_exact_id(tmp_path):
    result = run_helper(fixture_tree(tmp_path))
    assert result.returncode == 0, result.stdout + result.stderr
    source, _ = capture_paths(tmp_path)
    assert (source / "fixture.mcap").read_text() == "synthetic payload"
    assert str(source) in result.stdout


@pytest.mark.parametrize("behavior", ["missing", "failure"])
def test_failure_preserves_evidence(tmp_path, behavior):
    env = fixture_tree(tmp_path, behavior)
    source, final = capture_paths(tmp_path)
    neighbor = source.parent / "previous_capture"
    neighbor.mkdir(parents=True)
    sentinel = neighbor / "evidence"
    sentinel.write_bytes(b"never change")

    result = run_helper(env)

    assert result.returncode != 0
    assert sentinel.read_bytes() == b"never change"

    produced = (
        source.parent / "unexpected_capture"
        if behavior == "missing"
        else source
    )
    assert (produced / "fixture.mcap").read_text() == "synthetic payload"
    assert not final.exists()

    if behavior == "missing":
        assert str(source) in result.stdout
