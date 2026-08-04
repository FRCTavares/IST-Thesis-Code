"""Regression tests for the live TIM-MARS appearance launcher contract."""

import os
import re
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULTS = REPO_ROOT / 'tools/lib/live_defaults.sh'
CLI = REPO_ROOT / 'tools/lib/live_cli.sh'
USAGE = REPO_ROOT / 'tools/lib/live_usage.sh'
LAUNCHER = REPO_ROOT / 'tools/start_live_stack.sh'


def _read(path: Path) -> str:
    """Read a repository file as UTF-8 text."""
    return path.read_text(encoding='utf-8')


def _option_block(script: str, option: str) -> str:
    """Return the body of one live CLI option block."""
    match = re.search(
        rf'(?ms)^        {re.escape(option)}\)\n'
        rf'(.*?)'
        rf'^            ;;\n',
        script,
    )
    assert match is not None, f'missing parser block for {option}'
    return match.group(1)


def _tim_mars_launch_block(script: str) -> str:
    """Return the TIM-MARS launch section from the live launcher."""
    match = re.search(
        r'(?ms)^        start_ros_bg target_memory_mars '
        r'.*?'
        r'^        sleep 1$',
        script,
    )
    assert match is not None, 'missing TIM-MARS launcher block'
    return match.group(0)


def test_no_appearance_reaches_tim_mars_ros_parameter():
    """Verify that --no-appearance reaches the ROS appearance parameter."""
    cli = _read(CLI)
    launcher = _read(LAUNCHER)

    no_appearance = _option_block(cli, '--no-appearance')
    launch_block = _tim_mars_launch_block(launcher)

    assert 'TARGET_MEMORY_APPEARANCE_BOOL="false"' in no_appearance
    assert (
        '-p appearance_enabled:="$TARGET_MEMORY_APPEARANCE_BOOL"'
        in launch_block
    )
    assert 'appearance_enabled:=true' not in launch_block


def test_supported_live_appearance_options_reach_the_launcher():
    """Verify that supported appearance options reach the live launcher."""
    cli = _read(CLI)
    launcher = _read(LAUNCHER)
    launch_block = _tim_mars_launch_block(launcher)

    enable_block = _option_block(cli, '--target-memory-appearance')
    image_topic_block = _option_block(
        cli,
        '--target-memory-mars-image-topic',
    )
    model_path_block = _option_block(
        cli,
        '--target-memory-mars-model-path',
    )

    assert 'TARGET_MEMORY_APPEARANCE_BOOL="true"' in enable_block
    assert 'TARGET_MEMORY_MARS_IMAGE_TOPIC="$2"' in image_topic_block
    assert 'TARGET_MEMORY_MARS_MODEL_PATH="$2"' in model_path_block
    assert (
        '-p appearance_image_topic:="$TARGET_MEMORY_MARS_IMAGE_TOPIC"'
        in launch_block
    )
    assert (
        '-p mars_model_path:="$TARGET_MEMORY_MARS_MODEL_PATH"'
        in launch_block
    )


def test_obsolete_and_silent_noop_appearance_options_are_absent():
    """Verify that obsolete and silent no-op options remain absent."""
    combined = '\n'.join(
        (
            _read(DEFAULTS),
            _read(CLI),
            _read(USAGE),
            _read(LAUNCHER),
        )
    )

    obsolete_tokens = (
        '--target-memory-appearance-image-topic',
        '--target-memory-appearance-min-bbox-height',
        '--target-memory-appearance-max-image-age-ms',
        '--target-memory-mars-batch-size',
        '--target-memory-mars-appearance-weight',
        '--target-memory-mars-min-similarity',
        'TARGET_MEMORY_APPEARANCE_IMAGE_TOPIC',
        'TARGET_MEMORY_APPEARANCE_MIN_BBOX_HEIGHT',
        'TARGET_MEMORY_APPEARANCE_MAX_IMAGE_AGE_MS',
        'TARGET_MEMORY_MARS_BATCH_SIZE',
        'TARGET_MEMORY_MARS_APPEARANCE_WEIGHT',
        'TARGET_MEMORY_MARS_APPEARANCE_MIN_SIMILARITY',
        'RUN_TARGET_MEMORY_HSV',
    )

    for token in obsolete_tokens:
        assert token not in combined


def test_memory_replay_forwards_issue_44_request_controls():
    """The live replay must resolve, record, and forward both controls."""
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    wrapper = (
        repo_root
        / "tools"
        / "experiments"
        / "run_one_memory_tim_replay.sh"
    ).read_text(encoding="utf-8")

    required_tokens = (
        "TIM_APPEARANCE_REQUEST_POLICY_EFFECTIVE",
        "TIM_APPEARANCE_REQUEST_POLICY_SOURCE",
        "TIM_APPEARANCE_COMPUTE_MIN_INTERVAL_MS_EFFECTIVE",
        "TIM_APPEARANCE_COMPUTE_MIN_INTERVAL_MS_SOURCE",
        'appearance_request_policy:="$TIM_APPEARANCE_REQUEST_POLICY_EFFECTIVE"',
        'appearance_compute_min_interval_ms:="$TIM_APPEARANCE_COMPUTE_MIN_INTERVAL_MS_EFFECTIVE"',
        '--runtime "appearance_request_policy=',
        '--runtime "appearance_compute_min_interval_ms=',
        '--field "appearance_request_policy=',
        '--field "appearance_compute_min_interval_ms=',
        '--source "appearance_request_policy=',
        '--source "appearance_compute_min_interval_ms=',
        "all_candidates|geometry_winner|ambiguity_guarded",
        "canonical_config",
    )

    for token in required_tokens:
        assert token in wrapper, token


def test_memory_replay_normalizes_zero_interval_to_double(tmp_path):
    """An integer-looking zero override must reach ROS as a double literal."""
    wrapper = (
        REPO_ROOT
        / 'tools'
        / 'experiments'
        / 'run_one_memory_tim_replay.sh'
    )
    config = (
        REPO_ROOT
        / 'ros2_ws'
        / 'src'
        / 'thesis_bringup'
        / 'config'
        / 'tim_mars_canonical.yaml'
    )

    environment = os.environ.copy()
    environment.update(
        {
            'TIM_MARS_CONFIG': str(config),
            'TIM_APPEARANCE_REQUEST_POLICY': 'all_candidates',
            'TIM_APPEARANCE_COMPUTE_MIN_INTERVAL_MS': '0',
        }
    )

    result = subprocess.run(
        [
            'bash',
            str(wrapper),
            str(tmp_path / 'absent_bag'),
            '1',
            'p044_zero_interval_probe',
            str(tmp_path / 'absent_annotations.csv'),
            '1.0',
        ],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert (
        'TIM_APPEARANCE_COMPUTE_MIN_INTERVAL_MS=0.0'
        in result.stdout
    )
    assert 'bag not found' in result.stderr
    assert 'InvalidParameterTypeException' not in (
        result.stdout + result.stderr
    )


def test_memory_replay_accepts_ambiguity_guarded_override(tmp_path):
    """Forward the guarded policy without changing canonical YAML."""
    repo_root = Path(__file__).resolve().parents[2]
    wrapper = (
        repo_root
        / "tools"
        / "experiments"
        / "run_one_memory_tim_replay.sh"
    )
    config = (
        repo_root
        / "ros2_ws"
        / "src"
        / "thesis_bringup"
        / "config"
        / "tim_mars_canonical.yaml"
    )

    environment = os.environ.copy()
    environment.update(
        {
            "TIM_MARS_CONFIG": str(config),
            "TIM_APPEARANCE_REQUEST_POLICY": (
                "ambiguity_guarded"
            ),
            "TIM_APPEARANCE_COMPUTE_MIN_INTERVAL_MS": (
                "250"
            ),
        }
    )

    result = subprocess.run(
        [
            "bash",
            str(wrapper),
            str(tmp_path / "absent_bag"),
            "1",
            "p044_guarded_policy_probe",
            str(tmp_path / "absent_annotations.csv"),
            "1.0",
        ],
        cwd=repo_root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    combined = result.stdout + result.stderr

    assert result.returncode == 2
    assert (
        "TIM_APPEARANCE_REQUEST_POLICY="
        "ambiguity_guarded"
        in combined
    )
    assert (
        "TIM_APPEARANCE_COMPUTE_MIN_INTERVAL_MS="
        "250.0"
        in combined
    )
    assert "bag not found" in combined
    assert (
        "invalid TIM_APPEARANCE_REQUEST_POLICY"
        not in combined
    )
