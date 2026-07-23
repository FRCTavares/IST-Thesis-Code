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


def test_issue_57_records_remaining_ablation_work():
    text = (DOCS / "TODO_LIST.md").read_text(encoding="utf-8")

    assert text.count("[#57 —") == 1
    assert "historical-result segregation" in text
    assert "seven-row development ablation package" in text
    assert "correction-aware interpretation" in text
