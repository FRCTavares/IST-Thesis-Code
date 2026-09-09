# data/

Last reviewed: 2026-09-09

## Purpose

Local, large, or generated dataset material that is useful for research work
but is not itself tracked thesis authority.

The directory is intentionally separate from `bags/`: primary ROS recording
evidence belongs under `bags/`, while `data/` holds downloaded datasets,
extracted frames, annotation workspaces, normalized inputs, and other processed
research data.

## Contents

| Path | Role |
| --- | --- |
| `datasets/external/` | Downloaded external benchmark datasets such as VisDrone MOT. |
| `datasets/processed/cvat/` | Local CVAT preparation/export/conversion workspaces, including physical-reference annotation packages. |
| `datasets/processed/p064/` | Processed Issue #64 resolution-study inputs and derived workspaces. |
| `datasets/processed/` | Other reproducible processed dataset/cache material. |

## Authority boundary

Large contents under this tree are local and git-ignored.

Tracked machine-readable research contracts belong under `docs/data/`, including:

- dataset source definitions;
- prospective/development splits;
- frozen physical-target references;
- evaluation manifests;
- sensitivity/ablation definitions.

A CVAT workspace under `data/` is not canonical merely because human review
occurred there. The reviewed result becomes authority only when the appropriate
validated reference/manifest is deliberately promoted into its tracked
`docs/data/` location.

## Rules

- Do not place primary source ROS captures here; use `bags/`.
- Do not commit downloaded datasets, frame archives, CVAT image packages, or
  generated processed caches.
- Preserve local workspaces that are still required by an open experiment.
- Historical/local processed paths referenced by frozen evidence are not moved
  solely for cosmetic cleanup.
- `artifacts/` remains the correct home for disposable scratch output that is
  not intended to be retained as a research workspace.
