"""Executable contracts for documented operator paths and commands."""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess


REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS_ROOT = REPO_ROOT / "tools"
ROOT_README = REPO_ROOT / "README.md"
INDEX = REPO_ROOT / "docs/design/tim_tooling_index.md"
LIVE_UI_README = REPO_ROOT / "live-ui/README.md"
TOOLS_README = TOOLS_ROOT / "README.md"
FIELD_PLAN = REPO_ROOT / "docs/flight/SOURCE_FIRST_FIELD_RECORDING_PLAN.md"
EXPERIMENTS_README = TOOLS_ROOT / "experiments/README.md"

REPOSITORY_PATH_PREFIXES = (
    "docs/",
    "live-ui/",
    "models/",
    "reports/",
    "ros2_ws/",
    "tools/",
)


def markdown_repository_paths(document: Path) -> set[str]:
    """Extract repository-relative paths from inline-code spans."""
    text = document.read_text(encoding="utf-8")
    paths = set()
    for token in re.findall(r"`([^`\n]+)`", text):
        if " " in token:
            continue
        if token.startswith(REPOSITORY_PATH_PREFIXES):
            paths.add(token.rstrip("/"))
    return paths


def test_every_indexed_repository_path_exists():
    paths = markdown_repository_paths(INDEX)
    assert len(paths) >= 30
    missing = [
        relative_path
        for relative_path in sorted(paths)
        if not (REPO_ROOT / relative_path).exists()
    ]
    assert missing == []


def test_tooling_index_has_no_removed_runtime_or_ui_paths():
    index = INDEX.read_text(encoding="utf-8").lower()
    assert "user-interface" not in index
    assert "thesis_bringup/target_memory.py" not in index
    assert "nodes/target_memory_mars_node.py" not in index
    assert "hsv" not in index


def test_dashboard_docs_and_launcher_use_live_ui():
    readme = LIVE_UI_README.read_text(encoding="utf-8")
    launcher = (TOOLS_ROOT / "start_ui_stack.sh").read_text(
        encoding="utf-8"
    )

    assert "cd live-ui" in readme
    assert "./tools/start_ui_stack.sh --install" in readme
    assert "user-interface" not in readme
    assert '$THESIS_ROOT/live-ui' in launcher
    assert "user-interface" not in launcher


def test_every_dashboard_readme_source_path_exists():
    readme = LIVE_UI_README.read_text(encoding="utf-8")
    inline_tokens = set(re.findall(r"`([^`\n]+)`", readme))
    relative_paths = {
        token.rstrip("/")
        for token in inline_tokens
        if token.startswith("src/")
    }
    relative_paths.update(
        "src/" + token.rstrip("/")
        for token in inline_tokens
        if token
        in {
            "app/",
            "components/",
            "features/",
            "services/",
            "types/",
            "utils/",
        }
    )
    relative_paths.add(".env.example")

    missing = [
        relative_path
        for relative_path in sorted(relative_paths)
        if not (REPO_ROOT / "live-ui" / relative_path).exists()
    ]
    assert missing == []


def test_dashboard_package_exposes_every_documented_npm_command():
    package = json.loads(
        (REPO_ROOT / "live-ui/package.json").read_text(
            encoding="utf-8"
        )
    )
    scripts = package["scripts"]
    readme = LIVE_UI_README.read_text(encoding="utf-8")
    for command in ("dev", "build", "preview"):
        assert command in scripts
        assert f"npm run {command}" in readme


def test_ui_launcher_help_and_shell_syntax_from_clean_checkout():
    launcher = TOOLS_ROOT / "start_ui_stack.sh"
    subprocess.run(["bash", "-n", str(launcher)], check=True)
    result = subprocess.run(
        ["bash", str(launcher), "--help"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "PI_IP": "127.0.0.1"},
    )
    assert "--mode <backend|mock|offline>" in result.stdout
    assert "--install" in result.stdout


def test_documented_build_recording_and_evaluation_commands_are_supported():
    tools_readme = TOOLS_README.read_text(encoding="utf-8")
    root_readme = ROOT_README.read_text(encoding="utf-8")
    field_plan = FIELD_PLAN.read_text(encoding="utf-8")
    experiments = EXPERIMENTS_README.read_text(encoding="utf-8")
    live_cli = (TOOLS_ROOT / "lib/live_cli.sh").read_text(
        encoding="utf-8"
    )

    assert (TOOLS_ROOT / "thesis_build.sh").is_file()
    subprocess.run(
        ["bash", "-n", str(TOOLS_ROOT / "thesis_build.sh")],
        check=True,
    )
    subprocess.run(
        ["bash", "-n", str(TOOLS_ROOT / "start_live_stack.sh")],
        check=True,
    )

    assert "--field-record --record-raw" in tools_readme
    for option in (
        "--source-record",
        "--field-record",
        "--record-raw",
        "--record-mavros",
        "--tag",
    ):
        assert option in live_cli
        assert (
            option in root_readme
            or option in tools_readme
            or option in field_plan
        )

    command = (
        "python3 tools/experiments/"
        "run_tim_component_ablation.py --set development"
    )
    assert command in experiments
    assert (
        TOOLS_ROOT
        / "experiments/run_tim_component_ablation.py"
    ).is_file()
