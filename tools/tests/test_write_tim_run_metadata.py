import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER = REPO_ROOT / "tools" / "experiments" / "write_tim_run_metadata.py"
CONFIG = (
    REPO_ROOT
    / "ros2_ws"
    / "src"
    / "thesis_bringup"
    / "config"
    / "tim_mars_canonical.yaml"
)
RUNNER = (
    REPO_ROOT
    / "tools"
    / "experiments"
    / "run_one_memory_tim_replay.sh"
)


def test_metadata_records_effective_command_and_value_sources(tmp_path):
    output_dir = tmp_path / "metadata"

    subprocess.run(
        [
            "python3",
            str(HELPER),
            "--repo-root",
            str(REPO_ROOT),
            "--output-dir",
            str(output_dir),
            "--config",
            str(CONFIG),
            "--runner",
            str(RUNNER),
            "--command",
            "run_one_memory_tim_replay.sh bag 1 run annotations.csv 1.0",
            "--effective-command",
            (
                "RAW_TARGET_MODE=source "
                "TIM_MIRROR_RAW_TARGET_SELECTION=false "
                "run_one_memory_tim_replay.sh bag 1 run annotations.csv 1.0"
            ),
            "--runtime",
            "selected_track_id=1",
            "--runtime",
            "mirror_raw_target_selection=false",
            "--field",
            "raw_target_mode=source",
            "--field",
            "run_name=run",
            "--source",
            "raw_target_mode=environment",
            "--source",
            "mirror_raw_target_selection=runner_default",
            "--source",
            "appearance_image_topic=bag_auto_detect_dashboard",
        ],
        check=True,
        cwd=REPO_ROOT,
    )

    metadata = json.loads(
        (output_dir / "run_metadata.json").read_text(encoding="utf-8")
    )
    resolved = json.loads(
        (output_dir / "tim_mars_resolved_runtime.json").read_text(
            encoding="utf-8"
        )
    )

    expected_sources = {
        "appearance_image_topic": "bag_auto_detect_dashboard",
        "mirror_raw_target_selection": "runner_default",
        "raw_target_mode": "environment",
    }

    assert metadata["schema_version"] == 3
    assert metadata["effective_command"].startswith(
        "RAW_TARGET_MODE=source "
    )
    assert metadata["value_sources"] == expected_sources
    assert metadata["experiment_fields"] == {
        "raw_target_mode": "source",
        "run_name": "run",
    }

    assert resolved["schema_version"] == 2
    assert resolved["value_sources"] == expected_sources
    assert resolved["experiment_fields"]["raw_target_mode"] == "source"
    assert (
        resolved["runtime_overrides"]["mirror_raw_target_selection"]
        is False
    )


def test_metadata_rejects_duplicate_value_source_keys(tmp_path):
    result = subprocess.run(
        [
            "python3",
            str(HELPER),
            "--repo-root",
            str(REPO_ROOT),
            "--output-dir",
            str(tmp_path / "metadata"),
            "--config",
            str(CONFIG),
            "--runner",
            str(RUNNER),
            "--command",
            "runner",
            "--effective-command",
            "runner",
            "--source",
            "raw_target_mode=environment",
            "--source",
            "raw_target_mode=runner_default",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "duplicate assignment key: raw_target_mode" in result.stderr

def test_metadata_defaults_effective_command_to_original_command(tmp_path):
    output_dir = tmp_path / "metadata"

    subprocess.run(
        [
            "python3",
            str(HELPER),
            "--repo-root",
            str(REPO_ROOT),
            "--output-dir",
            str(output_dir),
            "--config",
            str(CONFIG),
            "--runner",
            str(RUNNER),
            "--command",
            "legacy-runner bag 1 run annotations.csv",
        ],
        check=True,
        cwd=REPO_ROOT,
    )

    metadata = json.loads(
        (output_dir / "run_metadata.json").read_text(encoding="utf-8")
    )

    assert metadata["command"] == (
        "legacy-runner bag 1 run annotations.csv"
    )
    assert metadata["effective_command"] == metadata["command"]
    assert metadata["value_sources"] == {}
