"""Contract tests for the frozen TIM-MARS research questions."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

QUESTION_PATH = ROOT / "docs" / "research_question.md"
DOCS_README_PATH = ROOT / "docs" / "README.md"
NOVELTY_PATH = ROOT / "docs" / "NOVELTY.md"
TODO_PATH = ROOT / "docs" / "TODO_LIST.md"

MAIN_QUESTION = (
    "Can a fully onboard RGB selected-person-following architecture combine computationally lightweight multi-object tracking with post-tracker identity validation to improve correct-target continuity and reduce controller-facing wrong-target publication during occlusions, crossings, temporary absences, re-entry, and tracker identity instability on a small UAV?"
)

ALGORITHM_QUESTION = (
    "Can TIM-MARS, as a post-tracker selected-target identity-memory layer, improve correct-target continuity while reducing controller-facing wrong-target publication relative to the raw selected-target stream?"
)

DEPLOYMENT_QUESTION = (
    "Can Hailo acceleration be extended from detection to appearance-embedding inference so that detection, lightweight tracking, appearance-supported identity validation, and controller-facing perception run fully onboard a Raspberry Pi 5 without external inference while meeting the required throughput, latency, thermal, power, and safety constraints?"
)


def test_all_three_questions_are_frozen_exactly():
    text = QUESTION_PATH.read_text(encoding="utf-8")

    assert text.count(f"> {MAIN_QUESTION}") == 1
    assert text.count(f"> {ALGORITHM_QUESTION}") == 1
    assert text.count(f"> {DEPLOYMENT_QUESTION}") == 1


def test_novelty_contract_contains_all_questions():
    text = NOVELTY_PATH.read_text(encoding="utf-8")

    assert f"> {MAIN_QUESTION}" in text
    assert f"> {ALGORITHM_QUESTION}" in text
    assert f"> {DEPLOYMENT_QUESTION}" in text
    assert "docs/research_question.md" in text


def test_question_contract_defines_both_contributions():
    text = QUESTION_PATH.read_text(encoding="utf-8")

    required = (
        "Algorithmic subquestion",
        "Embedded-deployment subquestion",
        "Fully onboard",
        "Computationally lightweight tracker",
        "Correct-target continuity",
        "Wrong-target publication",
        "Hailo appearance offload",
        "Literature-gap boundary",
    )

    for phrase in required:
        assert phrase in text


def test_live_system_does_not_depend_on_an_oracle():
    text = QUESTION_PATH.read_text(encoding="utf-8")
    normalized = " ".join(text.split())

    assert (
        "The live system does not receive a reference identity "
        "or evaluation oracle."
    ) in normalized

def test_open_evidence_dependencies_are_explicit():
    text = QUESTION_PATH.read_text(encoding="utf-8")

    required = (
        "Issue #27",
        "Issue #32",
        "Issue #44",
        "Issue #39",
        # Issue #44 closed as completed on 2026-08-04; the doc now states this
        # explicitly rather than hedging it as "not a completed result".
        "closed as completed",
        "not final held-out evidence",
    )

    for phrase in required:
        assert phrase in text


def test_embedded_deployment_conclusion_still_gated_on_issue_32():
    # Issue #44 is closed, so the pre-closure hedge ("Until Issue #44 closes ...
    # not a completed result") was removed. The embedded-deployment subquestion
    # is still not claimed complete: it is now gated on Issue #32.
    text = QUESTION_PATH.read_text(encoding="utf-8")
    normalized = " ".join(text.split())

    assert "Issue #44 owned the dedicated Hailo appearance-offload" in normalized
    assert (
        "The final embedded-deployment conclusion remains broader than "
        "Issue #44 alone"
    ) in normalized
    assert (
        "runtime, resource, thermal, power, and sustained-operation evidence "
        "owned by Issue #32"
    ) in normalized


def test_absolute_literature_claim_is_rejected():
    text = QUESTION_PATH.read_text(encoding="utf-8")
    normalized = " ".join(text.split())

    assert '"to the best of our knowledge"' in text
    assert (
        "The thesis must not claim that no related target-person, "
        "Raspberry Pi, Jetson, UAV-tracking, ReID, or edge-inference "
        "system exists."
    ) in normalized

def test_documentation_navigation_links_the_contract():
    text = DOCS_README_PATH.read_text(encoding="utf-8")

    assert "research_question.md" in text


def test_closed_issue_is_removed_and_final_claim_is_blocked():
    text = TODO_PATH.read_text(encoding="utf-8")

    assert "[#38 —" not in text
    assert text.count("[#39 —") == 1
    assert "under #32" in text
    # The final claim (#39) stays blocked on the held-out (#27), tracker
    # comparison (#58), and embedded-deployment (#32) evidence. Issue #44 is
    # now closed and folded in as completed evidence, not a pending dependency.
    assert "#32 are complete" in text
    assert "#44 is already closed" in text
    assert "#58" in text
