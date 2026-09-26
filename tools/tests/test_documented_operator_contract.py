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
FLIGHT_INDEX = REPO_ROOT / "docs/flight/README.md"
FLIGHT_DAY = REPO_ROOT / "docs/flight/field_day_runbook.md"
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


def test_flight_day_sheet_stays_compact_and_fail_closed():
    text = FLIGHT_DAY.read_text(encoding="utf-8")
    index = FLIGHT_INDEX.read_text(encoding="utf-8")

    assert "**Canonical #50 procedure.**" in text
    assert "Remember: `B -> C -> B`." in text
    assert "Remember: `MANUAL -> B -> C -> B`." not in text
    assert "## COMPLETED 25 SEPTEMBER — MANUAL RC / DYNAMIC TIM-MARS" in text
    assert text.count("opportunity_start --run-id") == 9
    assert text.count("opportunity_end --run-id") == 9
    assert "## Finish every run" in text
    assert "## FLIGHT 4" not in text
    assert "docs/flight/field_day_runbook.md" in index
    assert "ssh francisco@192.168.8.174" in text
    assert "set_pi_network_mode.sh pixhawk" in text
    assert "set_pi_network_mode.sh unattended" in text
    assert "field_preflight_check.sh --passive-live-gate" in text
    assert "--record-structured-visual" not in text
    assert (
        "./tools/start_live_stack.sh --res vga --field-record --control-mavros "
        '--tag "$TAG"'
    ) in text
    assert "--acknowledge-yaw-recovery-candidate" in text
    assert "tools/flight/verify_field_run.sh" in text
    assert '--expect-bcb-opportunities "$TAG"' in text
    assert text.count(
        'target_selected --run-id "$RUN_ID" --trial-id "$TAG"'
    ) == 3
    assert (
        'trial_end --run-id "$RUN_ID" --trial-id "$TAG" '
        '--end-reason nominal_complete'
    ) in text
    assert (
        'trial_verdict --run-id "$RUN_ID" --trial-id "$TAG" '
        '--verdict accepted'
    ) in text
    assert (
        'abort --run-id "$RUN_ID" --trial-id "$TAG" '
        '--abort-class safety'
    ) in text
    assert "tools/flight/kill_exact_controller_for_gate.sh" in text
    assert "H01/H02/H03 are complete" in text
    assert "#64 is closed: VGA is retained" in text
    for scenario in ("h01", "h02", "h03"):
        assert f"record_p027_heldout_sequence.sh {scenario}" not in text
    assert "--field-record --record-raw" not in text
    assert "git pull" not in text
    assert "100.69.42.62" not in text
    assert "100.105.37.101" not in text


def test_p032_final_mounted_contract_is_disarmed_and_fail_closed():
    runbook = (
        REPO_ROOT / "docs/issues/p032-final-mounted-runbook.md"
    ).read_text(encoding="utf-8")
    wrapper = (
        REPO_ROOT / "tools/flight/verify_field_run.sh"
    ).read_text(encoding="utf-8")

    assert "--disarmed-runtime-characterization" in runbook
    assert "--disarmed-runtime-characterization" in wrapper
    assert "Exact DataFlash .bin" not in runbook
    assert "unrelated `.bin`" in runbook
    assert 'target_selected --run-id "$RUN_ID" --trial-id "$TAG"' in runbook
    assert 'trial_end --run-id "$RUN_ID" --trial-id "$TAG"' in runbook
    assert 'trial_verdict --run-id "$RUN_ID" --trial-id "$TAG"' in runbook
    assert "inside the exact `trial_start` to `trial_end` interval" in runbook
    assert "Startup and shutdown state transitions" in runbook
    assert "armed=false" in runbook


def test_documented_build_recording_and_evaluation_commands_are_supported():
    tools_readme = TOOLS_README.read_text(encoding="utf-8")
    root_readme = ROOT_README.read_text(encoding="utf-8")
    p027_runbook = P027_RUNBOOK.read_text(encoding="utf-8")
    flight_day = FLIGHT_DAY.read_text(encoding="utf-8")
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

    assert "--record --record-raw" in tools_readme
    assert "--record-structured-visual" in tools_readme
    assert "not an approved aircraft launch command" in tools_readme
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
            or option in flight_day
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
