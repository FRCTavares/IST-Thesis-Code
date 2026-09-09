"""Structural contracts for the maintained tools directory."""

from pathlib import Path
import re
import stat


REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS_ROOT = REPO_ROOT / "tools"

DOMAIN_DIRECTORIES = {
    "analysis",
    "bag",
    "camera",
    "catalogue",
    "experiments",
    "host",
    "lib",
    "live",
    "setup",
    "tests",
}

TOP_LEVEL_FILES = {
    "README.md",
    "reproduce_tim_mars.py",
    "start_live_stack.sh",
    "start_ui_stack.sh",
    "thesis_build.sh",
    "timing_contract.py",
}

REMOVED_TOOLS = {
    "thesis_eval.sh",
    "thesis_live.sh",
}


def is_executable(path: Path) -> bool:
    return bool(path.stat().st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))


def test_every_tool_domain_is_documented():
    actual = {
        path.name
        for path in TOOLS_ROOT.iterdir()
        if path.is_dir() and path.name != "__pycache__"
    }
    assert actual == DOMAIN_DIRECTORIES
    for name in DOMAIN_DIRECTORIES:
        assert (TOOLS_ROOT / name / "README.md").is_file()


def test_top_level_contains_only_stable_shared_entrypoints():
    actual = {path.name for path in TOOLS_ROOT.iterdir() if path.is_file()}
    assert actual == TOP_LEVEL_FILES


_LAST_REVIEWED = re.compile(r"^Last reviewed: \d{4}-\d{2}-\d{2}$", re.MULTILINE)


def _first_heading(text: str) -> str:
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return ""


def test_folder_readmes_follow_the_documentation_standard():
    """Every tools folder README identifies its path and carries a review date.

    See docs/design/README_STANDARD.md. This guardrail does not check the
    review date's value, prose, line count, or table shape.
    """
    root_readme = (TOOLS_ROOT / "README.md").read_text(encoding="utf-8")
    assert _first_heading(root_readme) == "# tools"
    assert _LAST_REVIEWED.search(root_readme)

    for name in sorted(DOMAIN_DIRECTORIES):
        text = (TOOLS_ROOT / name / "README.md").read_text(encoding="utf-8")
        assert _first_heading(text) == f"# tools/{name}", name
        assert _LAST_REVIEWED.search(text), name


def test_removed_or_moved_tools_do_not_return():
    for relative_path in REMOVED_TOOLS:
        assert not (TOOLS_ROOT / relative_path).exists()
    assert (TOOLS_ROOT / "bag/render_tim_comparison_video.py").is_file()


def test_entrypoint_and_library_modes_match_their_roles():
    for relative_path in (
        "analysis/analyse_bag_timing.py",
        "analysis/analyse_bag_tracking.py",
        "bag/render_tim_comparison_video.py",
    ):
        assert is_executable(TOOLS_ROOT / relative_path)

    for path in (TOOLS_ROOT / "lib").glob("*.sh"):
        assert not is_executable(path)


def test_timing_entrypoints_bootstrap_the_repository_import_path():
    for relative_path in (
        "analysis/analyse_bag_timing.py",
        "analysis/check_live_timing_invariants.py",
        "analysis/collect_live_timing_stats.py",
    ):
        source = (TOOLS_ROOT / relative_path).read_text(encoding="utf-8")
        assert "Path(__file__).resolve().parents[2]" in source
        assert "sys.path.insert(0, str(REPO_ROOT))" in source
        assert "from tools.timing_contract import" in source


def test_timing_analyser_defaults_generated_figures_to_artifacts():
    source = (TOOLS_ROOT / "analysis/analyse_bag_timing.py").read_text(
        encoding="utf-8"
    )

    assert (
        'os.path.join(thesis_root, "artifacts", "figures", "timing", bag_name)'
        in source
    )
    assert (
        'os.path.join(thesis_root, "figures", "timing", bag_name)'
        not in source
    )
    assert "default: artifacts/figures/timing/<bag>/" in source
