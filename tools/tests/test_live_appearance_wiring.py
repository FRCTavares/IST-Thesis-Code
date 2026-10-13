# Thesis-Code
# Purpose: Regression tests for the live TIM-MARS appearance launcher
# contract.
# Author: Francisco Tavares
# Copyright (c) 2026 Francisco Carreira Tavares
# SPDX-License-Identifier: MIT
#
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.

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
        r'(?ms)^    start_ros_bg target_memory_mars '
        r'.*?'
        r'^    sleep 1$',
        script,
    )
    assert match is not None, 'missing TIM-MARS launcher block'
    return match.group(0)


def test_tim_mars_startup_is_independent_of_dashboard_bridge():
    """Disabling the dashboard must not silently suppress enabled TIM-MARS."""
    cli = _read(CLI)
    launcher = _read(LAUNCHER)

    no_dashboard = _option_block(cli, '--no-dashboard')
    assert 'ENABLE_DASHBOARD_BRIDGE=0' in no_dashboard
    assert 'ENABLE_WEB_VIDEO=0' in no_dashboard
    assert 'RUN_TARGET_MEMORY_MARS' not in no_dashboard
    assert 'TARGET_MEMORY_MODE' not in no_dashboard

    startup_start = launcher.index(
        'if [[ "$ENABLE_DASHBOARD_BRIDGE" -eq 1 ]]; then',
        launcher.index('TRACKER_RESOLVED_PARAMS'),
    )
    startup_end = launcher.index(
        '# Start MAVROS telemetry when --record-mavros is enabled.',
        startup_start,
    )
    startup = launcher[startup_start:startup_end]

    assert (
        '\nif [[ "${RUN_TARGET_MEMORY_MARS:-0}" -eq 1 ]]; then\n'
        in startup
    )
    assert (
        '\n    if [[ "${RUN_TARGET_MEMORY_MARS:-0}" -eq 1 ]]; then\n'
        not in startup
    )


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


