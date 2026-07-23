# TIM-MARS evidence-version map

Date: 2026-07-23

The machine-readable authority is
`docs/data/catalogue/tim_evidence_versions.json`. A TIM-MARS result is valid
only for the configuration hash, algorithm commit, model, bags, annotations,
oracles, and claim boundary recorded by its evidence version.

## Current runtime identity

- Configuration:
  `ros2_ws/src/thesis_bringup/config/tim_mars_canonical.yaml`
- SHA-256:
  `e7620313be428cac4d2d1f5595dc48b1f6127a43c22f1b4149049beba1e207ff`
- Last evaluated algorithm commit:
  `c5ba9d30997e47c7f555baee5257bc687698508a`
- Current evidence version: `p028_dual_oracle_development`

“Canonical” means the current reproducible runtime configuration. It does not
mean that every historical report used the same bytes or that the current
configuration has a universal safety guarantee.

## Version map

| Evidence version | Algorithm commit | Config SHA-256 | Result status |
| --- | --- | --- | --- |
| P0.4 clean cross-tracker | `1b7dc4002c19e5235703913826e174df1025f1d0` | `16f21b2032135858d2ea7d5d8081536eb24204a3ef0f12efb05a628d626a0655` | One-preset safety portability rejected |
| P0.6b hard-negative structure | `03409564f5107d6808054dac12294b004d9d4381` | `55332935fe859edff60bedf910f126487b5da6a8e13bbe5bb7662f2645359dbc` | Structural promotion and behavior preservation |
| P0.7 rank-aware preservation | `add2b8b87963ac26ae2551762ecccfaf119a7780` | `55332935fe859edff60bedf910f126487b5da6a8e13bbe5bb7662f2645359dbc` | Confirmation fix with preserved development outcomes |
| P0.17 dual-oracle development | `c5ba9d30997e47c7f555baee5257bc687698508a` | `e7620313be428cac4d2d1f5595dc48b1f6127a43c22f1b4149049beba1e207ff` | Improves over raw; not zero-wrong and not held-out |

All versions use MARS model SHA-256
`e96f3cc09dbce76e2f6aeff09c8f2502916b4745f21e27911ee50d102a4a75f1`.

## Configuration transitions

P0.4 → P0.6b added:

- `hard_negative_confirm_observations: 2`

P0.6b/P0.7 → P0.17 added:

- `freshness_max_output_age_s: 0.90`
- `freshness_future_tolerance_s: 0.05`
- `same_id_hijack_protection_enabled: true`

The active margins are:

- conservative appearance margin: `0.05`
- hard-negative rejection margin: `0.03`
- rank-aware lost appearance margin: `0.03`
- absence appearance margin: `0.20`, inactive because absence recovery is
  disabled

These values are different policy quantities. Historical strict-margin
experiments do not redefine the current configuration.

## Claim boundaries

### P0.4

Use
`docs/results/selected_target_tracking/hard_reentry_multi_tracker_summary.md`.
Within-tracker comparisons are valid, but the single preset was rejected for
cross-tracker safety portability. Absolute tracker ranking is invalid because
each tracker selected its own physical target.

### P0.6b and P0.7

Use
`reports/p006b_hard_negative_03409564_2026_07_21/closure_summary.md`
and
`reports/p007_rank_aware_add2b8b8_2026_07_21/closure_summary.md`.
These packages support structural correctness and preservation claims, not a
new final performance table.

### P0.17

Use
`docs/results/selected_target_tracking/p028_wrong_oracle_audit.md`.
The four development sequences improve over raw under both wrong-target
oracles. The optimistic spatial oracle reports `0.000 s` final wrong output,
while the conservative annotated-ID oracle reports `1.300 s`. The evidence is
not flawless and is not held out.

## Tracker and motion statements

The interface accepts multiple tracker backends, but safety is not
tracker-independent. TIM-MARS does not add an independent velocity or
motion-prediction model; geometric continuity is measured against the last
trusted bbox, while any tracker motion model remains part of the base tracker.

## Launch and paper/thesis status

`tools/start_live_stack.sh` loads the installed copy of the canonical YAML via
`tools/lib/live_defaults.sh` and `--params-file`. Launch scripts do not own
copies of algorithm thresholds. The controller's `stale_timeout_s` remains a
separate profile-dependent control deadline; it does not override TIM-MARS
`freshness_max_output_age_s`.

The former design documents
`docs/design/selected_target_memory.md`,
`docs/design/tim_mars_design.md`, and
`docs/design/tim_evaluation_protocol.md` were removed from the active tree.
Their historical text is superseded by this file, the final algorithm
description, and the current evaluation documentation.

The historical `paper_tim_mars` source was removed by cleanup commit
`9b33508`; it is not an active result source. No tracked `.tex` or `.bib`
thesis source exists in this repository. Paper or thesis text must be written
from the versioned evidence above rather than copying obsolete result values.
