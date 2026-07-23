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
