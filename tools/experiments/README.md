# tools/experiments

Last reviewed: 2026-09-09

## Purpose

Replay and capture runners that reproduce TIM-MARS and tracker evaluations.
These are not generic utilities: each encodes a thesis-specific contract for
bag naming, output roots, ROS topics and selected-target publication mode. The
layout is deliberately flat because these paths are cited verbatim by frozen
manifests and by reproduction documentation.

## Contents

Representative entrypoints by category — not every file is listed.

| Path | Category | Role |
| --- | --- | --- |
| `run_one_memory_tim_replay.sh` | Core replay | Memory-only TIM-MARS replay over existing tracks/targets/annotations. |
| `run_deterministic_tim_replay.py` | Core replay (frozen) | Deterministic TIM-MARS replay with resolved-runtime provenance. |
| `run_deterministic_tracker_replay.py` | Core replay (frozen) | Freezes one tracker and a fixed-ID raw target from recorded evidence. |
| `run_one_clean_tim_replay.sh`, `run_one_detector_tim_replay.sh` | Full/partial pipeline | Replay with reused or regenerated detector/tracker outputs. |
| `run_tim_component_ablation.py` | Ablation | Frozen seven-row component-ablation matrix (Issue #28). |
| `run_tim_parameter_sensitivity.py`, `run_bytetrack_tim_sensitivity.py` | Sensitivity | Historical Issue #31 OFAT sweep; Issue #58b ByteTrack config screen. |
| `record_p027_heldout_sequence.sh` | Capture (frozen) | Held-out source capture helper (Issue #27). |
| `record_p064_drone_sequence.sh` | Capture | Representative small-target capture (Issue #64). |
| `publish_annotated_track_target.py`, `publish_selected_track_target.py` | Publishers | Oracle-style and fixed-ID `/target` sources for controlled replays. |
| `wait_for_track_selection.py`, `select_largest_track_id.py`, `write_tim_run_metadata.py`, `build_common_input_bag.py`, `images_to_camera_bag.py` | Support | Track selection, run-metadata provenance, input-bag construction. |
| `run_p058_target_reid_replay.py` (frozen), `run_tim_resilience_development.py` | Issue-scoped | Issue #58 Target-ReID replay; Issue #90 resilience study. |
| `run_p044_*.sh`, `sample_p044_*.py`, `collect_p044_transport_evidence.py`, `analyze_p044_sustained_soak.py`, `p044_*_relay.py` | Historical | Issue #44 (closed) Hailo ReID-offload evidence, retained for reproduction. |
| `p064_appearance_contract.py`, `prepare_p064_appearance_variants.py`, `measure_p054_raw_image_transport_cost.sh`, `capture_external_detector_tracker.sh`, `profile_tim_resilience_service.py`, `sample_process_groups.py` | Issue-scoped | Per-issue capture, measurement and profiling helpers. |

## Rules

- The flat structure is intentional — do not add `current/`, `historical/` or
  other subdirectories; frozen manifests and reproduction docs pin these paths.
- Paths pinned in the prospective-freeze JSON must not move before H01–H03.
- Full-pipeline runners regenerate tracker IDs; use them only when annotations
  and evaluation tolerate regenerated IDs.
- Prefer explicit output roots for final runs so bags and reports trace back to
  the experiment.

## Reproduce the canonical matrix

    python3 tools/experiments/run_tim_component_ablation.py --set development

Single end-to-end reproduction command:
`python3 tools/reproduce_tim_mars.py --set development`.

## See also

- `docs/design/tim_tooling_index.md` — replay/evaluation path authority
- `docs/data/reproduce_final_results.md` — full reproduction steps
- `docs/issues/p1-14-final-runtime-characterization.md` — Issue #32 context;
  the default-off controller (`RUN_CONTROLLER`) and resource-sampling
  (`RESOURCE_SAMPLING_ENABLED`) modes are documented in the header and inline
  checks of `run_one_detector_tim_replay.sh`
