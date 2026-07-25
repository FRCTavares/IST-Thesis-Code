"""Contract tests for the final TIM-MARS replay runner."""

from __future__ import annotations

import ast
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNER = (
    REPO_ROOT
    / "tools"
    / "experiments"
    / "run_one_memory_tim_replay.sh"
)
TIM_PARAMS = (
    REPO_ROOT
    / "ros2_ws"
    / "src"
    / "thesis_bringup"
    / "thesis_bringup"
    / "tim_mars"
    / "ros_params.py"
)
ANNOTATION_PUBLISHER = (
    REPO_ROOT
    / "tools"
    / "experiments"
    / "publish_annotated_track_target.py"
)


def declared_parameters(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        function = node.func
        if not (
            isinstance(function, ast.Attribute)
            and function.attr == "declare_parameter"
            and node.args
        ):
            continue

        first = node.args[0]
        if (
            isinstance(first, ast.Constant)
            and isinstance(first.value, str)
        ):
            names.add(first.value)

    return names


def shell_block(
    text: str,
    start_marker: str,
    end_marker: str,
) -> str:
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


def passed_ros_parameters(block: str) -> set[str]:
    return set(
        re.findall(
            r"(?:^|\s)-p\s+"
            r"([A-Za-z_][A-Za-z0-9_]*):=",
            block,
        )
    )


def test_tim_mars_runner_only_passes_declared_parameters():
    runner = RUNNER.read_text(encoding="utf-8")
    block = shell_block(
        runner,
        "ros2 run thesis_bringup target_memory_mars_node",
        "TIM_PID=$!",
    )

    assert (
        passed_ros_parameters(block)
        - declared_parameters(TIM_PARAMS)
        == set()
    )


def test_annotation_publisher_only_receives_declared_parameters():
    runner = RUNNER.read_text(encoding="utf-8")
    block = shell_block(
        runner,
        (
            'python3 "$THESIS_ROOT/tools/experiments/'
            'publish_annotated_track_target.py"'
        ),
        "RAW_SELECTOR_PID=$!",
    )

    passed = passed_ros_parameters(block)
    unsupported = passed - declared_parameters(ANNOTATION_PUBLISHER)

    assert unsupported == set(), (
        "Annotation publisher received undeclared parameters: "
        f"{sorted(unsupported)}"
    )


def test_removed_unsupported_experiment_parameters_do_not_return():
    runner = RUNNER.read_text(encoding="utf-8").lower()

    forbidden = {
        "anchor_drift",
        "anchor-drift",
        "group_split",
        "group-split",
    }

    assert forbidden.isdisjoint(runner)
