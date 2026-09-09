"""Structural contracts for ros2_ws/ documentation.

Small guardrail: every architectural README under ros2_ws/ exists, identifies
itself, and carries a review date; the workspace README does not carry stale
Timing-schema or perception-path wording; and the package READMEs name the
public executables / backends they are the contract for.

Does not check prose, length, table formatting, section order, or the review
date's value. See docs/design/README_STANDARD.md.
"""

from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WS = REPO_ROOT / "ros2_ws"

WORKSPACE_README = WS / "README.md"

ARCHITECTURAL_READMES = {
    WS / "README.md": "# ros2_ws",
    WS / "src/thesis_msgs/README.md": "# thesis_msgs",
    WS / "src/thesis_tracker/README.md": "# thesis_tracker",
    WS / "src/thesis_bringup/README.md": "# thesis_bringup",
    WS / "src/thesis_tracker/thesis_tracker/README.md": "# thesis_tracker — Python layout",
    WS / "src/thesis_bringup/thesis_bringup/README.md": "# thesis_bringup — Python layout",
    WS / "src/thesis_bringup/thesis_bringup/tim_mars/README.md": "# TIM-MARS selected-target memory",
}

_LAST_REVIEWED = re.compile(r"^Last reviewed: \d{4}-\d{2}-\d{2}$", re.MULTILINE)


def _first_heading(text: str) -> str:
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return ""


def _console_scripts() -> set[str]:
    text = (WS / "src/thesis_bringup/setup.py").read_text(encoding="utf-8")
    return set(re.findall(r"(\w+)\s*=\s*thesis_bringup\.", text))


def test_every_ros2_ws_architectural_readme_exists():
    for path in ARCHITECTURAL_READMES:
        assert path.is_file(), str(path.relative_to(REPO_ROOT))


def test_ros2_ws_architectural_readmes_follow_the_standard():
    for path, heading in ARCHITECTURAL_READMES.items():
        text = path.read_text(encoding="utf-8")
        assert _first_heading(text) == heading, str(path.relative_to(REPO_ROOT))
        assert _LAST_REVIEWED.search(text), str(path.relative_to(REPO_ROOT))


def test_workspace_readme_has_no_stale_contract_wording():
    text = WORKSPACE_README.read_text(encoding="utf-8")
    assert "schema v3" not in text
    assert "schema v4" in text
    assert "Neither supersedes the other" not in text


def test_thesis_bringup_readme_names_every_console_script():
    scripts = _console_scripts()
    assert "perception_camera_node" in scripts  # sanity: parsing worked
    text = (WS / "src/thesis_bringup/README.md").read_text(encoding="utf-8")
    for name in scripts:
        assert name in text, name


def test_thesis_tracker_readme_names_every_backend():
    text = (WS / "src/thesis_tracker/README.md").read_text(encoding="utf-8")
    for backend in ("sort", "ocsort", "bytetrack", "deepsort"):
        assert backend in text, backend
