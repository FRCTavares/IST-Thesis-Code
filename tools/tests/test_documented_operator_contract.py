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


def test_internal_live_ui_tree_is_removed_from_thesis_code():
    assert not (REPO_ROOT / "live-ui").exists()


def test_dashboard_compatibility_launcher_uses_external_ui_repository():
    launcher = TOOLS_ROOT / "start_ui_stack.sh"
    source = launcher.read_text(encoding="utf-8")

    subprocess.run(["bash", "-n", str(launcher)], check=True)

    assert (
        'THESIS_UI_ROOT="${THESIS_UI_ROOT:-$HOME/Desktop/IST-Thesis-UI}"'
        in source
    )
    assert (
        'UI_LAUNCHER="$THESIS_UI_ROOT/tools/start_dashboard.sh"'
        in source
    )
    assert 'exec "$UI_LAUNCHER" "${FORWARD_ARGS[@]}"' in source

    # Thesis-Code must no longer implement the frontend runtime itself.
    assert "UI_DIR=" not in source
    assert "npm run dev" not in source
    assert "npm install" not in source
    assert "ros2_ws/log/ui_stack" not in source


def test_dashboard_compatibility_launcher_forwards_legacy_contract(
    tmp_path: Path,
):
    external_root = tmp_path / "IST-Thesis-UI"
    external_tools = external_root / "tools"
    external_tools.mkdir(parents=True)

    fake_launcher = external_tools / "start_dashboard.sh"
    fake_launcher.write_text(
        """#!/usr/bin/env bash
printf 'api=%s\\n' "${VITE_DASHBOARD_API_BASE_URL:-}"
printf 'ws=%s\\n' "${VITE_DASHBOARD_WS_URL:-}"
printf 'args='
printf '<%s>' "$@"
printf '\\n'
""",
        encoding="utf-8",
    )
    fake_launcher.chmod(0o755)

    launcher = TOOLS_ROOT / "start_ui_stack.sh"
    result = subprocess.run(
        [
            "bash",
            str(launcher),
            "--api-base-url",
            "http://127.0.0.1:8090",
            "--ws-url",
            "ws://127.0.0.1:8765",
            "--skip-install",
            "--mode",
            "backend",
            "--host",
            "0.0.0.0",
            "--port",
            "5174",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        env={
            "PATH": "/usr/bin:/bin",
            "HOME": str(tmp_path),
            "THESIS_UI_ROOT": str(external_root),
        },
    )

    assert "api=http://127.0.0.1:8090" in result.stdout
    assert "ws=ws://127.0.0.1:8765" in result.stdout
    assert (
        "args=<--mode><backend><--host><0.0.0.0><--port><5174>"
        in result.stdout
    )
    assert "--skip-install" not in result.stdout


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
