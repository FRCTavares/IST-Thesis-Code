#!/usr/bin/env python3
"""Create detailed GitHub issues from unfinished TODO_LIST.md sections."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


DEFAULT_REPOSITORY = "FRCTavares/IST-Thesis-Code"
DEFAULT_ROADMAP = Path("TODO_LIST.md")
UMBRELLA_TITLE = "TIM-MARS thesis execution roadmap"


@dataclass(frozen=True)
class RoadmapSection:
    order: int
    phase_number: str
    phase_title: str
    heading: str
    body: str

    @property
    def issue_title(self) -> str:
        heading = self.heading.strip()

        if heading.startswith('P0.9 '):
            return (
                'P0.9 Finalize deterministic replay evidence '
                'and clean provenance'
            )

        return heading

    @property
    def priority(self) -> str | None:
        match = re.match(r"^(P[0-3](?:\.\d+|\.\w+|\+)?)(?:\s+|$)", self.heading)
        if match:
            token = match.group(1)
            return token.split(".")[0].replace("+", "")
        return None


def run(
    command: list[str],
    *,
    check: bool = True,
    capture_output: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=check,
        text=True,
        capture_output=capture_output,
    )


def gh_json(arguments: list[str]) -> object:
    result = run(["gh", *arguments])
    if not result.stdout.strip():
        return None
    return json.loads(result.stdout)


def parse_sections(path: Path) -> list[RoadmapSection]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    phase_number = "unassigned"
    phase_title = "Unassigned"
    sections: list[RoadmapSection] = []
    index = 0
    order = 0

    while index < len(lines):
        line = lines[index]

        if line.startswith("## ") and not line.startswith("### "):
            phase_title = line[3:].strip()
            match = re.match(r"Phase\s+(\d+)", phase_title, re.IGNORECASE)
            phase_number = match.group(1) if match else "meta"
            index += 1
            continue

        if not line.startswith("### "):
            index += 1
            continue

        heading = line[4:].strip()
        section_lines: list[str] = []
        index += 1

        while index < len(lines):
            next_line = lines[index]
            if next_line.startswith('### ') or (
                next_line.startswith('## ')
                and not next_line.startswith('### ')
            ):
                break
            section_lines.append(next_line)
            index += 1

        body = '\n'.join(section_lines).strip()

        is_technical_task = re.match(
            r'^P[0-3](?:\.\d+[a-z]?|\.x)(?:\+)?(?:\s+|$)',
            heading,
            re.IGNORECASE,
        )
        if is_technical_task is None:
            continue

        is_explicitly_complete = re.search(
            r'—\s*(?:DONE|COMPLETE|COMPLETED|RESOLVED)\s*$',
            heading,
            re.IGNORECASE,
        )
        if is_explicitly_complete is not None:
            continue

        if not body:
            continue

        order += 1
        sections.append(
            RoadmapSection(
                order=order,
                phase_number=phase_number,
                phase_title=phase_title,
                heading=heading,
                body=body,
            )
        )

    return sections


def classify_work_type(section: RoadmapSection) -> str:
    text = f"{section.heading}\n{section.body}".lower()

    if any(
        token in text
        for token in (
            "flight",
            "live appearance",
            "ground dry-run",
            "control-sign",
            "onboard",
            "hailo",
            "thermal",
        )
    ):
        return "live-system"

    if any(
        token in text
        for token in (
            "experiment",
            "ablation",
            "sensitivity",
            "tracker",
            "detector",
            "reid",
            "sequence",
            "evaluation",
            "metric",
        )
    ):
        return "experiment"

    if any(
        token in text
        for token in (
            "documentation",
            "readme",
            "novelty",
            "paper",
            "thesis",
            "claim",
            "figure",
            "pseudocode",
        )
    ):
        return "documentation"

    return "engineering"


def labels_for(section: RoadmapSection) -> list[str]:
    labels = [
        "roadmap",
        f"phase:{section.phase_number}",
        f"type:{classify_work_type(section)}",
    ]

    if section.priority is not None:
        labels.append(f"priority:{section.priority}")

    return labels


def ensure_label(
    repository: str,
    name: str,
    description: str,
    color: str,
    *,
    apply: bool,
) -> None:
    if not apply:
        print(f"[dry-run] ensure label: {name}")
        return

    result = run(
        [
            "gh",
            "label",
            "create",
            name,
            "--repo",
            repository,
            "--description",
            description,
            "--color",
            color,
            "--force",
        ],
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Could not create/update label {name}: {result.stderr.strip()}"
        )


def existing_issues(repository: str) -> dict[str, dict[str, object]]:
    payload = gh_json(
        [
            "issue",
            "list",
            "--repo",
            repository,
            "--state",
            "all",
            "--limit",
            "1000",
            "--json",
            "number,title,state,url",
        ]
    )

    assert isinstance(payload, list)

    return {
        str(item["title"]): item
        for item in payload
        if isinstance(item, dict)
    }


def make_issue_body(section: RoadmapSection) -> str:
    labels = ", ".join(labels_for(section))

    return f"""## Objective

Complete the roadmap work defined in **{section.heading}**.

This issue is intentionally detailed. It replaces the corresponding operational
section in `TODO_LIST.md`; scope must not be reduced to a vague summary.

## Roadmap position

- Execution order: **{section.order}**
- Parent phase: **{section.phase_title}**
- Source heading: **{section.heading}**
- Classification: **{labels}**

## Required work

{section.body}

## Completion contract

This issue is complete only when all applicable items below are satisfied:

- [ ] Every unchecked task copied above is completed or explicitly rejected with
      repository-grounded evidence.
- [ ] Implementation and configuration changes are flag-gated when the roadmap
      requires the existing behaviour to remain the default.
- [ ] Relevant tests are added or updated before claiming completion.
- [ ] Focused tests pass.
- [ ] Relevant package or workspace build passes.
- [ ] `git diff --check` passes.
- [ ] No root-level `log/` or `hailort.log` runtime noise is introduced.
- [ ] Experimental outputs record the source bag, annotation, selected target,
      canonical configuration, runtime overrides, Git commit and repository state.
- [ ] Result changes are compared against the appropriate canonical baseline.
- [ ] Any wrong-target increase blocks promotion unless the issue explicitly
      documents and justifies a changed scientific objective.
- [ ] Documentation and thesis claims are updated only after clean committed
      evidence exists.
- [ ] The corresponding roadmap status is updated before `TODO_LIST.md` is archived.

## Evidence required in the closing comment

Provide:

1. commit or pull-request reference;
2. exact commands used;
3. test and build summary;
4. experiment/report paths where applicable;
5. before/after metrics where applicable;
6. known limitations or deferred follow-up;
7. confirmation that repository runtime-noise policy was respected.
"""


def create_issue(
    repository: str,
    section: RoadmapSection,
    *,
    apply: bool,
) -> dict[str, object] | None:
    title = section.issue_title
    labels = labels_for(section)
    body = make_issue_body(section)

    if not apply:
        print()
        print(f"[dry-run] issue {section.order}: {title}")
        print(f"          labels: {', '.join(labels)}")
        print(f"          body length: {len(body)}")
        return None

    command = [
        "gh",
        "issue",
        "create",
        "--repo",
        repository,
        "--title",
        title,
        "--body",
        body,
    ]

    for label in labels:
        command.extend(["--label", label])

    result = run(command)
    url = result.stdout.strip()

    issue = gh_json(
        [
            "issue",
            "view",
            url,
            "--repo",
            repository,
            "--json",
            "number,title,state,url",
        ]
    )

    assert isinstance(issue, dict)
    return issue


def create_umbrella_issue(
    repository: str,
    issues: list[dict[str, object]],
    *,
    apply: bool,
) -> None:
    ordered = sorted(
        issues,
        key=lambda issue: int(issue.get("roadmap_order", 0)),
    )

    checklist = "\n".join(
        f"- [ ] #{issue['number']} — {issue['title']}"
        for issue in ordered
    )

    body = f"""## Purpose

This is the top-level execution index for the TIM-MARS thesis work.

The linked issues contain the complete implementation scope, validation contract,
scientific constraints and closing-evidence requirements. This umbrella issue is
an index, not a substitute for the detailed child issues.

## Execution order

{checklist}

## Global rules

- Work in issue order unless a dependency or flight deadline is explicitly
  documented.
- P0 evidence-chain and safety work takes precedence over model upgrades.
- Keep the existing behaviour as default unless an issue explicitly authorizes
  promotion of a replacement.
- Wrong-target increase blocks promotion.
- Dirty-tree experiment results remain diagnostic and must not become thesis
  numbers.
- Every promoted result must point to a clean commit and complete provenance.
- Hailo ReID promotion happens only after CPU/replay selection identifies a
  winner and quantized margins are revalidated.
- `TODO_LIST.md` may be archived only after this issue list has been reviewed
  for completeness.
"""

    if not apply:
        print()
        print(f"[dry-run] umbrella issue: {UMBRELLA_TITLE}")
        print(f"          linked issues: {len(issues)}")
        return

    result = run(
        [
            "gh",
            "issue",
            "create",
            "--repo",
            repository,
            "--title",
            UMBRELLA_TITLE,
            "--body",
            body,
            "--label",
            "roadmap",
        ]
    )
    print(f"[created] umbrella: {result.stdout.strip()}")


def configure_labels(
    repository: str,
    sections: list[RoadmapSection],
    *,
    apply: bool,
) -> None:
    definitions = {
        "roadmap": (
            "Task migrated from the TIM-MARS thesis roadmap",
            "5319E7",
        ),
        "priority:P0": (
            "Blocks trustworthy evidence, safety, or the final thesis claim",
            "B60205",
        ),
        "priority:P1": (
            "Major algorithmic, scientific, or engineering work",
            "D93F0B",
        ),
        "priority:P2": (
            "Useful improvement after critical-path work",
            "FBCA04",
        ),
        "priority:P3": (
            "Optional or stretch work",
            "0E8A16",
        ),
        "type:engineering": (
            "Implementation, refactoring, configuration, or tests",
            "1D76DB",
        ),
        "type:experiment": (
            "Replay, evaluation, ablation, model, or measurement work",
            "7057FF",
        ),
        "type:documentation": (
            "Paper, thesis, documentation, figures, or reproducibility",
            "0075CA",
        ),
        "type:live-system": (
            "Onboard, flight, control, Hailo, thermal, or live-pipeline work",
            "C2E0C6",
        ),
    }

    for section in sections:
        definitions.setdefault(
            f"phase:{section.phase_number}",
            (
                f"Roadmap work from {section.phase_title}",
                "D4C5F9",
            ),
        )

    for name, (description, color) in definitions.items():
        ensure_label(
            repository,
            name,
            description,
            color,
            apply=apply,
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo",
        default=DEFAULT_REPOSITORY,
    )
    parser.add_argument(
        "--roadmap",
        type=Path,
        default=DEFAULT_ROADMAP,
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually create labels and issues.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Create only the first N missing issues; zero means all.",
    )
    args = parser.parse_args()

    if not args.roadmap.is_file():
        print(f"[error] missing roadmap: {args.roadmap}", file=sys.stderr)
        return 1

    run(["gh", "auth", "status"])
    run(
        [
            "gh",
            "repo",
            "view",
            args.repo,
            "--json",
            "nameWithOwner,hasIssuesEnabled",
        ]
    )

    sections = parse_sections(args.roadmap)

    if not sections:
        print("[error] no unfinished roadmap sections found", file=sys.stderr)
        return 1

    print(f"unfinished sections: {len(sections)}")

    configure_labels(
        args.repo,
        sections,
        apply=args.apply,
    )

    known = existing_issues(args.repo)
    created_or_existing: list[dict[str, object]] = []
    missing_created = 0

    for section in sections:
        title = section.issue_title

        if title in known:
            issue = dict(known[title])
            issue["roadmap_order"] = section.order
            created_or_existing.append(issue)
            print(
                f"[existing] #{issue['number']} "
                f"{issue['title']}"
            )
            continue

        if args.limit > 0 and missing_created >= args.limit:
            print(f"[limit] skipped: {title}")
            continue

        issue = create_issue(
            args.repo,
            section,
            apply=args.apply,
        )
        missing_created += 1

        if issue is not None:
            issue["roadmap_order"] = section.order
            created_or_existing.append(issue)
            known[title] = issue
            print(f"[created] #{issue['number']} {issue['title']}")

    if args.apply:
        refreshed = existing_issues(args.repo)
        final_issues: list[dict[str, object]] = []

        for section in sections:
            issue = refreshed.get(section.issue_title)
            if issue is None:
                continue
            item = dict(issue)
            item["roadmap_order"] = section.order
            final_issues.append(item)

        if UMBRELLA_TITLE in refreshed:
            print(
                "[existing] umbrella "
                f"#{refreshed[UMBRELLA_TITLE]['number']}"
            )
        else:
            create_umbrella_issue(
                args.repo,
                final_issues,
                apply=True,
            )
    else:
        create_umbrella_issue(
            args.repo,
            created_or_existing,
            apply=False,
        )

    print()
    print(f"mode: {'apply' if args.apply else 'dry-run'}")
    print(f"roadmap sections considered: {len(sections)}")
    print(f"missing issues processed: {missing_created}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
