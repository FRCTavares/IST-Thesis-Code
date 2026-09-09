"""Contracts for the maintained documentation hierarchy."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"


def test_core_authority_is_under_docs():
    required = (
        DOCS / "README.md",
        DOCS / "NOVELTY.md",
        DOCS / "TODO_LIST.md",
        DOCS / "research_question.md",
    )

    for path in required:
        assert path.is_file()

    assert not (ROOT / "NOVELTY.md").exists()
    assert not (ROOT / "TODO_LIST.md").exists()


def test_documented_top_level_directories_exist():
    readme = (DOCS / "README.md").read_text(encoding="utf-8")

    expected = {
        "algorithm",
        "control",
        "data",
        "debug",
        "design",
        "flight",
        "issues",
        "results",
        "archive",
    }

    listed = set(
        re.findall(
            r"^- `([^`]+?)/`",
            readme,
            re.MULTILINE,
        )
    )

    assert expected <= listed

    for directory in expected:
        assert (DOCS / directory).is_dir()


def test_historical_result_directories_are_archived():
    old_paths = (
        DOCS / "results" / "deepsort_vs_tim",
        DOCS / "results" / "tim_mars_active_reid",
        DOCS / "results" / "tim_v2",
        DOCS / "results" / "tim_v2q_mars_margin",
        DOCS / "data" / "catalogue" / "archive_legacy_cleanup",
    )

    for path in old_paths:
        assert not path.exists()

    new_paths = (
        DOCS / "archive" / "results" / "deepsort_vs_tim",
        DOCS / "archive" / "results" / "tim_mars_active_reid",
        DOCS / "archive" / "results" / "tim_v2",
        DOCS / "archive" / "results" / "tim_v2q_mars_margin",
        DOCS / "archive" / "data_catalogue_cleanup",
    )

    for path in new_paths:
        assert path.is_dir()


def test_current_result_index_preserves_active_sources():
    text = (DOCS / "results" / "README.md").read_text(
        encoding="utf-8"
    )

    required = (
        "hard_reentry_multi_tracker_summary.md",
        "p028_wrong_oracle_audit.md",
        "hard_reentry_compute_throughput_summary.md",
        "p023_output_freshness_validation.md",
        "../archive/results/",
    )

    for value in required:
        assert value in text


def test_tracker_readme_links_resolve():
    readme = ROOT / "ros2_ws" / "src" / "thesis_tracker" / "README.md"
    text = readme.read_text(encoding="utf-8")

    targets = (
        "../thesis_msgs/msg/Track2DArray.msg",
        "../thesis_msgs/msg/Timing.msg",
    )

    for target in targets:
        assert target in text
        assert (readme.parent / target).resolve().is_file()

    assert "../../thesis_msgs/msg/Track2DArray.msg" not in text
    assert "../../thesis_msgs/msg/Timing.msg" not in text


def test_issue_57_is_removed_after_completion():
    text = (DOCS / "TODO_LIST.md").read_text(encoding="utf-8")

    assert "[#57 —" not in text
    # The open-issue count is reconciled with GitHub regularly; assert only that
    # the count line still exists in its canonical form, not a fixed value.
    assert re.search(r"Open executable issues: \*\*\d+\*\*\.", text)

def test_maintained_documentation_domains_have_reviewed_readmes():
    required = (
        DOCS / "README.md",
        DOCS / "algorithm" / "README.md",
        DOCS / "control" / "README.md",
        DOCS / "data" / "README.md",
        DOCS / "debug" / "README.md",
        DOCS / "design" / "README.md",
        DOCS / "flight" / "README.md",
        DOCS / "issues" / "README.md",
        DOCS / "results" / "README.md",
        DOCS / "results" / "live" / "README.md",
        DOCS / "results" / "selected_target_tracking" / "README.md",
        DOCS / "archive" / "README.md",
    )

    date_pattern = re.compile(
        r"^Last reviewed: \d{4}-\d{2}-\d{2}$",
        re.MULTILINE,
    )

    for path in required:
        assert path.is_file()
        text = path.read_text(encoding="utf-8")
        assert text.startswith("# ")
        assert date_pattern.search(text)


def test_current_docs_do_not_advertise_retired_annotation_ui():
    current_docs = (
        DOCS / "README.md",
        DOCS / "data" / "README.md",
        DOCS / "data" / "catalogue" / "bag_layout.md",
        DOCS / "data" / "catalogue" / "evidence_retention_policy.md",
        DOCS / "design" / "tim_tooling_index.md",
        ROOT / "tools" / "README.md",
        ROOT / "tools" / "bag" / "README.md",
        ROOT / "tools" / "bag" / "render_tim_comparison_video.py",
    )

    retired = (
        "tools/bag_annotation_ui",
        "tim_clean_ui",
        "ui favourites",
        "fallback workspace",
        "prefer these over the annotation ui",
        "interactive fastapi annotation ui",
    )

    for path in current_docs:
        text = path.read_text(encoding="utf-8").lower()
        for phrase in retired:
            assert phrase not in text
