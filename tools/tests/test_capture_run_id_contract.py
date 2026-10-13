# Thesis-Code
# Purpose: Synthetic capture identity tests: no ROS, devices or real evidence.
# Author: Francisco Tavares
# Copyright (c) 2026 Francisco Carreira Tavares
# SPDX-License-Identifier: MIT
#
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.

"""Synthetic capture identity tests: no ROS, devices or real evidence."""
import os
from pathlib import Path
import re
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = (ROOT / "tools/start_live_stack.sh").read_text()
# Execute the real launcher's initialization, stopping before any log creation.
PREFIX = LAUNCHER[:LAUNCHER.index("declare -A PROC_PIDS")]


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
