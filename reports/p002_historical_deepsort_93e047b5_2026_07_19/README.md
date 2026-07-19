# P0.2 Historical Unsafe DeepSORT Reproduction

This directory is an intentionally tracked exception to the generated-report
ignore rule.

It closes GitHub Issue #1 using deterministic replay evidence generated from
clean commit:

- `93e047b55294a8280dc619b42787e6dfa23ad247`

The two generated ROS bags remain ignored because each is approximately
547 MiB. Their paths and SHA-256 fingerprints are recorded in
`replay_bag_manifest.sha256`.

## Reproduction result

| Policy | Correct ratio | Wrong ratio | Lost ratio |
| --- | ---: | ---: | ---: |
| Historical report from 3 July | 0.490 | 0.466 | 0.044 |
| Preserved July 12 policy, clean rerun | 0.476 | 0.471 | 0.053 |
| Current canonical policy, clean rerun | 0.897 | 0.000 | 0.103 |

The reconstructed fixed-ID raw target is identical in both clean reruns:

| Correct ratio | Wrong ratio | Lost ratio |
| ---: | ---: | ---: |
| 0.496 | 0.030 | 0.474 |

The clean July 12 rerun reproduces the historical unsafe result within
`+0.005` wrong-ratio difference.

## Provenance

- Source DeepSORT MCAP SHA-256:
  `fd4b0d0619c9c51de4e63803f6e92e9ed919b4968d459bf23393158572249201`
- Source metadata SHA-256:
  `0faf17111fb85a91fb9d700e6086fc8ac90de8b9d7e9545301602970e83e5b0f`
- Annotation SHA-256:
  `f0ba198211952e538167fc9dd6b62d065dc570dcbb6964d6cf6fbeb8c0c2affc`
- MARS model SHA-256:
  `e96f3cc09dbce76e2f6aeff09c8f2502916b4745f21e27911ee50d102a4a75f1`
- Current canonical configuration SHA-256:
  `16f21b2032135858d2ea7d5d8081536eb24204a3ef0f12efb05a628d626a0655`
- Preserved July 12 configuration SHA-256:
  `5871bc351a78c252a22cfa7ee81f951658b031c35626150979c5ef844f97e4d1`

Both replays used fixed selected tracker ID `1`, replaced the unusable source
`/target`, disabled reselection, and generated 507 raw targets, 507 TIM targets,
and 507 status messages.

## Failure sequence

- Frame 583: both policies suppress new DeepSORT ID `2`.
- Frame 595: July 12 enters `REACQUIRED` on ID `2`; current canonical rejects
  it because appearance `0.717 < 0.780`.
- Frame 598: July 12 locks wrong ID `2`; current canonical remains LOST.
  The nearest image is 331 ms stale, so exact status and target messages are
  authoritative for this frame.
- Frame 608: image timing is exact. July 12 remains locked to the visible
  distractor ID `2`; current canonical continues to reject it.
- Frame 617: current canonical selects physical-target ID `69` approximately
  4.27 ms before the structured annotation boundary.
- Frame 619: the annotation expects ID `69`; current canonical is correct while
  July 12 remains locked to wrong ID `2`.

The visual contact sheet binds tracks, raw target, TIM target and status
directly by tracker frame ID. Only the image background uses nearest header
time, and its offset is recorded.

## Root cause

The historical failure is a configuration-policy failure in the ID-switch
recovery path:

1. DeepSORT ID `1` disappears.
2. DeepSORT ID `2` appears on the wrong person with extremely strong geometry.
3. The July 12 rank-aware path accepts appearance similarity around
   `0.72-0.74`, reacquires ID `2`, and then reinforces it through tracker-ID
   continuity.
4. The current `id_switch_min_appearance_similarity: 0.78` gate blocks the
   switch and keeps control in LOST/HOVER until ID `69` is supported.

Diagnostic ablations support this attribution:

| Ablation | Correct ratio | Wrong ratio | Lost ratio |
| --- | ---: | ---: | ---: |
| ID-switch gate only | 0.911 | 0.000 | 0.089 |
| Protected memory only | 0.481 | 0.339 | 0.179 |

The gate alone eliminates sampled wrong-target duration on this sequence.
Protected memory reduces the failure but is not independently sufficient.

The ablations were generated before the clean tooling commit, from a dirty
working tree and temporary configurations. They are retained only as causal
diagnostics. The clean committed July 12/current pair is the primary evidence.

## Regression coverage

The identified algorithmic behavior already has direct regressions:

- `test_target_memory_appearance.py::test_id_switch_rejects_low_appearance_similarity`
- `test_target_memory_rank_aware_reacquisition.py::test_rank_aware_id_switch_respects_minimum_appearance_similarity`
- `test_run_deterministic_tim_replay.py::test_build_memory_config_preserves_id_switch_appearance_threshold`

No duplicate sequence-level unit regression was added.

## Limitations and claim scope

- Correctness is tracker-ID based and is valid because the preserved source
  lineage and annotation both use DeepSORT IDs `1` then `69`.
- Frame 617 has a 4.27 ms annotation-boundary discrepancy.
- The result is tracker-specific. It does not authorize tracker-independent
  TIM-MARS claims.
- The current policy trades uncertainty for LOST rather than risking the wrong
  target, consistent with the flight-safety objective.
- Generated ROS bags remain local and ignored; compact provenance and hashes
  are tracked here.

## Package contents

- `comparison.json`: clean current-versus-July-12 metrics.
- `current/`: current canonical configuration, provenance and evaluation.
- `july12/`: preserved policy configuration, provenance and evaluation.
- `visual/`: exact-frame mapping and reviewed contact sheet.
- `diagnostic_ablations/`: exploratory causal attribution.
- `root_cause_summary.json`: machine-readable conclusion.
- `commands.md`: primary replay and evaluator commands.
- `verification.txt`: verification record and lint limitation.
- `replay_bag_manifest.sha256`: hashes for ignored replay MCAP files.
- `report_manifest.sha256`: integrity manifest for the tracked package.
