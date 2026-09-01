"""Executable contracts for documented operator paths and commands."""

from __future__ import annotations

from pathlib import Path
import re
import subprocess


REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS_ROOT = REPO_ROOT / "tools"
ROOT_README = REPO_ROOT / "README.md"
INDEX = REPO_ROOT / "docs/design/tim_tooling_index.md"
TOOLS_README = TOOLS_ROOT / "README.md"
P027_RUNBOOK = REPO_ROOT / "docs/flight/P027_HELDOUT_CAPTURE_RUNBOOK.md"
P050_STATUS = REPO_ROOT / "docs/flight/P050_FLIGHT_VALIDATION.md"
EXPERIMENTS_README = TOOLS_ROOT / "experiments/README.md"

REPOSITORY_PATH_PREFIXES = (
    "docs/",
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
    assert "live-ui/" not in index


def test_dashboard_docs_and_launcher_use_external_ui_repository():
    root_readme = ROOT_README.read_text(encoding="utf-8")
    index = INDEX.read_text(encoding="utf-8")
    tools_readme = TOOLS_README.read_text(encoding="utf-8")
    launcher = (TOOLS_ROOT / "start_ui_stack.sh").read_text(
        encoding="utf-8"
    )

    for document in (root_readme, index, tools_readme):
        assert "FRCTavares/IST-Thesis-UI" in document

    assert "THESIS_UI_ROOT" in launcher
    assert "IST-Thesis-UI" in launcher
    assert "start_dashboard.sh" in launcher
    assert 'exec "$UI_LAUNCHER"' in launcher

    assert "$THESIS_ROOT/live-ui" not in launcher
    assert "npm run dev" not in launcher
    assert "npm install" not in launcher
    assert "ros2_ws/log/ui_stack" not in launcher


def test_dashboard_backend_ownership_remains_in_thesis_code_docs():
    root_readme = ROOT_README.read_text(encoding="utf-8")
    index = INDEX.read_text(encoding="utf-8")

    for document in (root_readme, index):
        assert "dashboard_bridge_node" in document
        assert "web_video_server" in document
        assert "start_live_stack.sh" in document


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
    assert "Compatibility shim" in result.stdout
    assert "THESIS_UI_ROOT" in result.stdout
    assert "IST-Thesis-UI" in result.stdout


def test_documented_build_recording_and_evaluation_commands_are_supported():
    tools_readme = TOOLS_README.read_text(encoding="utf-8")
    root_readme = ROOT_README.read_text(encoding="utf-8")
    p027_runbook = P027_RUNBOOK.read_text(encoding="utf-8")
    p050_status = P050_STATUS.read_text(encoding="utf-8")
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
            or option in p027_runbook
            or option in p050_status
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
