# Bag Directory Policy

This directory stores large ROS bag data. Keep it organized by data role, not by experiment mood.

## Folder roles

| Folder | Role | Deletion policy |
|---|---|---|
| `source/curated/` | protected rerunnable source bags used for TIM, tracker, and full-pipeline reruns | do not delete |
| `source/official_flights/` | protected official field-flight bags kept as original flight evidence | do not delete |
| `replay/` | generated replay/evaluation bags | disposable unless promoted to final evidence |
| `reference/` | known-good bags and small symlink aliases | keep intentionally curated entries |
| `tmp/` | temporary generated bags | disposable |
| `ui_replays/` | UI-generated replay bags | disposable unless promoted |

## Core rule

Source/raw bags are precious. Replay/tmp/UI bags are disposable unless explicitly promoted.

After the 2026-07-09 cleanup, old lab archive bags, failed tuning replays, duplicate full-pipeline bags, annotation-input bags, and MAVROS-only support bags were removed. The cleanup audit trail is tracked at:

- `docs/archive/bag_cleanup_2026_07_09/`

It preserves the deleted bag names, the deletion rationale, and a per-bag
`metadata.yaml` sidecar for every removed bag. A local
`reports/bag_cleanup_2026_07_09/` working directory holds the same content plus
a few uncurated scratch listings.

## Current protected structure

Protection is role- and evidence-based rather than tied to the historical July
folder list.

Always protect:

- `bags/source/curated/`;
- `bags/source/official_flights/`;
- `bags/reference/tim_good/`;
- every source/raw recording;
- replay evidence referenced by promoted result documents, frozen experiment
  manifests, current thesis evaluation, or active roadmap dependencies.

Historical `paper_final_*` replay folders documented by the July cleanup may no
longer exist locally. Their deletion provenance remains under
`docs/archive/bag_cleanup_2026_07_09/`; do not recreate aliases to absent bags.

Generated replay evidence must be classified through the current evidence
retention policy before deletion. Unknown evidence is retained by default.

Current retention authority:

- `docs/data/catalogue/evidence_retention_policy.md`
- `docs/data/catalogue/evidence_retention_manifest_2026_09_05.json`

## Naming contract

Use double underscores between semantic fields.

## Source bags

Source bags preserve capture provenance, including timestamp and original role.

Pattern:

    YYYY-MM-DD__HH-MM-SS__source__<campaign>__<seq_id>__<scenario>__<stream_kind>

Example:

    2026-06-19__12-55-58__source__2026-06-19__official__seq03__four_person_crossing_ambiguity__image_raw

## Protected source set

The protected rerunnable source set lives in:

    bags/source/curated/

These bags contain `/camera/image_raw` where applicable and are preferred for realistic full detector/tracker/TIM reruns.

Rules:

- Do not delete curated source bags.
- Do not overwrite curated source bags.
- Use curated `/camera/image_raw` bags for realistic full-pipeline reruns.
- Do not use dashboard-only bags as full-pipeline source inputs.
- Dashboard/video replay bags may be used for visual review, but not as golden full-pipeline inputs.
- Event-level grouping should come from annotations, not from physically splitting bags.

## Official flight bags

Official field-flight bags are protected separately under:

    bags/source/official_flights/2026-06-19/

These preserve the official field-session material, including image, full-pipeline, and MAVROS-context bags. They are kept for traceability and should not be deleted during cleanup.

## Replay bags

Replay bags are generated outputs.

Pattern for future promoted replays:

    YYYY-MM-DD__seqXX__<scenario>__replay_<kind>__det_<detector>__trk_<tracker>__tim_<mode>__target_<policy>

Existing submitted-paper replay bags are kept under their historical final folders:

- `bags/replay/paper_final_tim_results_2026_07_03/`
- `bags/replay/paper_final_deepsort_may_2026_07_03/`
- `bags/replay/paper_final_deepsort_june_full_2026_07_04/`
- `bags/replay/paper_final_deepsort_june_memory_2026_07_04/`

The `paper_final_*` names are frozen for traceability and should not be used as the naming pattern for new thesis reruns.

Do not treat other replay folders as final evidence unless they are documented in:

- `docs/data/final_experiment_inventory.md`
- `docs/archive/bag_cleanup_2026_07_09/keep_bags.txt`

## Reference aliases

Stable symlink aliases may live under `bags/reference/`, but an alias is retained
only while its target exists and the shortcut serves an active workflow.

Broken aliases are repository-hygiene defects and should be removed rather than
left as historical markers. Historical target names belong in tracked cleanup
provenance, not in dangling filesystem links.

The annotation UI already supports role grouping and user favourites, so a
permanent alias is not required merely to make a bag discoverable.

## Annotation inputs

The old `bags/annotation_inputs/` folder was removed during cleanup.

Annotation workflows should now use:

- `bags/reference/annotation_aliases/`
- real replay/source bag paths directly

Annotation CSV `bag_name` values may refer to historical bag names. When the corresponding bag no longer exists locally, use the documented cleanup metadata and current aliases to resolve the intended source.
