"""Structural contracts for the maintained tools directory."""

from pathlib import Path
import stat


REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS_ROOT = REPO_ROOT / "tools"

DOMAIN_DIRECTORIES = {
    "analysis",
    "bag",
    "bag_annotation_ui",
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
    "start_field_ui.sh",
    "start_live_stack.sh",
    "start_ui_stack.sh",
    "thesis_build.sh",
    "timing_contract.py",
}

REMOVED_TOOLS = {
    "thesis_eval.sh",
    "thesis_live.sh",
    "bag_annotation_ui/render_all_tracks_id_video.py",
    "bag_annotation_ui/video.py",
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
    assert not is_executable(
        TOOLS_ROOT / "bag_annotation_ui/tim_ui_backend.py"
    )
    assert not is_executable(
        TOOLS_ROOT / "bag_annotation_ui/tim_clean_ui.py"
    )


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
