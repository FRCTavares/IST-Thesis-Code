"""Repository-wide local Markdown reference validation."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[2]
LINK_PATTERN = re.compile(
    r"!?\[[^\]]*\]\(([^)]+)\)"
)


def markdown_files() -> list[Path]:
    output = subprocess.run(
        [
            "git",
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            "*.md",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    return [
        ROOT / line
        for line in output.splitlines()
        if line.strip()
    ]


def resolve_target(
    source: Path,
    raw_target: str,
) -> Path | None:
    target = raw_target.strip()

    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]

    if re.match(
        r"^[A-Za-z][A-Za-z0-9+.-]*:",
        target,
    ):
        return None

    if target.startswith("#"):
        return None

    if " " in target:
        target = target.split(" ", 1)[0]

    target = unquote(target)
    target = target.split("#", 1)[0]
    target = target.split("?", 1)[0]

    if not target:
        return None

    if target.startswith("/"):
        return (ROOT / target.lstrip("/")).resolve()

    return (source.parent / target).resolve()


def test_all_local_markdown_links_resolve():
    broken = []

    for source in markdown_files():
        text = source.read_text(
            encoding="utf-8",
            errors="replace",
        )

        for line_number, line in enumerate(
            text.splitlines(),
            start=1,
        ):
            for raw_target in LINK_PATTERN.findall(line):
                resolved = resolve_target(
                    source,
                    raw_target,
                )

                if resolved is None:
                    continue

                try:
                    resolved.relative_to(ROOT)
                except ValueError:
                    broken.append(
                        (
                            source.relative_to(ROOT),
                            line_number,
                            raw_target,
                            str(resolved),
                        )
                    )
                    continue

                if not resolved.exists():
                    broken.append(
                        (
                            source.relative_to(ROOT),
                            line_number,
                            raw_target,
                            str(resolved.relative_to(ROOT)),
                        )
                    )

    assert not broken, "\n".join(
        f"{source}:{line}: {target} -> {resolved}"
        for source, line, target, resolved in broken
    )


def test_core_documentation_cross_references_exist():
    required = (
        ROOT / "docs" / "README.md",
        ROOT / "docs" / "NOVELTY.md",
        ROOT / "docs" / "research_question.md",
        ROOT / "docs" / "TODO_LIST.md",
        ROOT
        / "docs"
        / "algorithm"
        / "tim_mars_versions.md",
        ROOT
        / "docs"
        / "algorithm"
        / "tim_mars_evidence_versions.md",
        ROOT
        / "docs"
        / "design"
        / "tim_tooling_index.md",
        ROOT
        / "docs"
        / "results"
        / "selected_target_tracking"
        / "p028_component_ablation_development"
        / "README.md",
        ROOT
        / "docs"
        / "results"
        / "selected_target_tracking"
        / "p028_wrong_oracle_audit.md",
    )

    for path in required:
        assert path.is_file()


# Canonical operator/architecture docs whose inline path references are checked
# below. These files describe the repository layout; a stale path here misleads
# a reader immediately, and such references are usually written as inline code
# spans rather than Markdown links, so the link checker above does not see them.
# `artifacts/README.md` is intentionally excluded: it documents disposable output
# directories that only exist after a tool has run.
CANONICAL_PATH_DOCS = (
    "README.md",
    "ros2_ws/README.md",
    "bags/README.md",
    "reports/README.md",
    "reports/PROMOTED.md",
    "models/README.md",
    "docs/README.md",
)

# Directories whose contents are always tracked, so a path into them must exist.
# bags/, reports/, artifacts/, data/, models/reid, figures/ are deliberately
# excluded: they hold git-ignored, generated, or frozen-but-untracked content.
_REPO_TOP_LEVEL = (
    "docs/",
    "tools/",
    "ros2_ws/",
)

_INLINE_CODE = re.compile(r"`([^`]+)`")
_SCREAMING_MD = re.compile(r"^[A-Z0-9][A-Z0-9_]*\.md$")
# Tokens carrying a filled-in-later placeholder are patterns, not real paths.
_PLACEHOLDER = re.compile(r"<[^>]+>|\{[^}]+\}|YYYY")


def _tracked_basenames() -> set[str]:
    output = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return {line.rsplit("/", 1)[-1] for line in output.splitlines() if line.strip()}


def test_canonical_doc_inline_path_references_resolve():
    """Inline `code`-span repo paths in the canonical layout docs must exist.

    Covers two rot patterns the Markdown-link checker misses:
    - a repo-root-relative path written as an inline code span
      (e.g. `docs/bag_cleanup_2026_07_09/`);
    - a bare SCREAMING_CASE Markdown filename that has moved or been deleted
      (e.g. `TIMING_FIELD_AUDIT.md`).
    """
    tracked_basenames = _tracked_basenames()
    broken: list[str] = []

    for rel in CANONICAL_PATH_DOCS:
        source = ROOT / rel
        if not source.is_file():
            continue

        text = source.read_text(encoding="utf-8", errors="replace")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for token in _INLINE_CODE.findall(line):
                token = token.strip()

                if _PLACEHOLDER.search(token) or "*" in token or " " in token:
                    continue

                if token.startswith(_REPO_TOP_LEVEL):
                    candidate = token.split("#", 1)[0].rstrip("/")
                    if not (ROOT / candidate).exists():
                        broken.append(f"{rel}:{line_number}: `{token}` does not exist")
                    continue

                if _SCREAMING_MD.match(token) and token not in tracked_basenames:
                    broken.append(
                        f"{rel}:{line_number}: `{token}` is not a tracked file"
                    )

    assert not broken, "\n".join(broken)
