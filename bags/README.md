# bags/

Last reviewed: 2026-09-09

## Purpose

Local ROS 2 recordings used as source evidence, live/field evidence, reference
material, or generated replay output.

Bag protection is determined by **data role and evidence provenance**, not only
by the directory name. Raw/source recordings are precious. Generated replay
bags are removable only after the evidence-retention gate says they are safe to
delete.

## Current folder roles

| Folder | Role | Default treatment |
| --- | --- | --- |
| `source/curated/` | Protected rerunnable development source bags. | Never delete or overwrite. |
| `source/official_flights/` | Protected original field-flight evidence. | Never delete or overwrite. |
| `source/held_out/` | Prospective held-out source recordings, including H01-H03. | Protected; do not inspect outcomes before the release gate permits it. |
| `live_camera/` | Normal live-stack pipeline recordings produced by `start_live_stack.sh`. | Retain according to experiment/evidence role. |
| `datasets/` | Dataset-style recordings produced by the live stack. | Retain according to experiment/evidence role. |
| `source_video/` | Source-first/raw recording root used by the live stack and Issue #64 capture workflow. | Treat completed source recordings as protected until their owning experiment closes. |
| `mavros/` | Synchronized Pixhawk/MAVROS telemetry recordings produced by field/source recording modes. | Retain with the paired source/field evidence when required. |
| `replay/` | Generated deterministic replay, tracker, detector, and evaluation bags. | Disposable only after retention-policy review. |
| `reference/` | Known-good reference bags and deliberate symlink aliases. | Keep curated entries while their targets and workflows remain valid. |
| `ground/` | Retained ground-validation recordings from earlier/current integration work. | Preserve while referenced; no generic new-output contract is implied. |

Directories such as historical `annotation_inputs/`, `review/`, and UI-specific
replay workspaces are not part of the current repository workflow.

## Current recording routes

The live-stack defaults are defined in `tools/lib/live_defaults.sh` and
`tools/start_live_stack.sh`.

Current producer paths include:

- normal live pipeline recording -> `bags/live_camera/`;
- dataset-style recording -> `bags/datasets/`;
- source-first/raw recording -> `bags/source_video/` unless an issue-specific
  `SOURCE_RECORD_ROOT` overrides it;
- synchronized MAVROS telemetry -> `bags/mavros/`.

Issue-specific procedures may deliberately override the generic source root.

For Issue #27, the prospective held-out helper writes H01-H03 source recordings
under:

    bags/source/held_out/2026-09/<scenario>/

using:

    tools/experiments/record_p027_heldout_sequence.sh

For Issue #64, `record_p064_drone_sequence.sh` preserves the completed source
capture under `bags/source_video/`.

Do not relocate these paths before their owning experiment/provenance contract
is complete merely to make the directory tree look more uniform.

## Protection and deletion rules

Always protect:

- every original source/raw recording required to reproduce thesis evidence;
- `bags/source/curated/`;
- `bags/source/official_flights/`;
- `bags/source/held_out/`;
- `bags/reference/tim_good/`;
- source, live, MAVROS, or replay evidence referenced by a frozen manifest,
  promoted result, active evaluation, or open roadmap dependency.

Generated replay evidence must pass the current retention policy before
deletion. Unknown evidence is retained by default.

Current retention authority:

- `docs/data/catalogue/evidence_retention_policy.md`
- `docs/data/catalogue/evidence_retention_manifest_2026_09_05.json`

Historical deletion provenance is retained under:

- `docs/archive/bag_cleanup_2026_07_09/`

## Source naming

For new source recordings, use double underscores between semantic fields.

Pattern:

    YYYY-MM-DD__HH-MM-SS__source__<campaign>__<seq_id>__<scenario>__<stream_kind>

Example:

    2026-06-19__12-55-58__source__2026-06-19__official__seq03__four_person_crossing_ambiguity__image_raw

Historical names remain unchanged for provenance.

## Replay bags

Replay bags are generated outputs. Existing experiment-specific replay names
remain frozen when cited by tracked evidence.

For new work, keep replay output under `bags/replay/` and give the directory a
run/experiment identity that is sufficient to recover its configuration and
source evidence.

Do not infer that a replay is final evidence from its name. Promotion is defined
by tracked manifests and reviewed result documentation.

## Reference aliases

Stable symlink aliases may live under `bags/reference/` while the target exists
and the shortcut serves an active workflow.

Broken aliases are repository-hygiene defects and should be removed rather than
kept as historical markers. Historical target names belong in tracked
provenance.

`bags/reference/annotation_aliases/` may remain as historical/convenience
aliases, but current manual physical-reference annotation is performed in CVAT
and does not require a repository-local annotation UI or permanent alias tree.

## Boundary with other storage roots

- `data/` owns external datasets and processed research workspaces, not primary
  ROS recording evidence.
- `reports/` owns generated analysis output and explicitly promoted compact
  evidence packages.
- `artifacts/` owns disposable reproducible intermediate output.
- reviewed thesis-facing result summaries live under `docs/results/`.
