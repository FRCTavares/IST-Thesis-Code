# P1.13 Parameter Sensitivity

GitHub Issue: #31
Branch: `issue-31-parameter-sensitivity`
Baseline: `c2bf9ef56f164f83a9e47446478f0284c5eb7362` (main after Issue #30's PR #71 merge)

## Objective

Test whether the safety/correctness conclusions of the canonical TIM-MARS
configuration are robust to reasonable one-factor-at-a-time (OFAT)
perturbations of its seven main decision parameters, and characterise the
safety-availability trade-offs that emerge as each parameter becomes less or
more conservative.

> Are the safety/correctness conclusions of the canonical TIM-MARS
> configuration robust to reasonable perturbations of its main decision
> parameters, and what safety-availability trade-offs arise as those
> parameters become less or more conservative?

This issue is a robustness/sensitivity study, not a retuning exercise. The
canonical TIM-MARS configuration remains canonical throughout Issue #31.
Detector, ByteTrack, sequence selection, canonical YAML, and physical-target
identity semantics are not changed.

## Research boundary

This issue does not:

- select a "better" configuration than canonical;
- change the canonical TIM-MARS YAML on disk;
- run the primary sensitivity study in Issue #30's oracle `selected_id`
  candidate-stream mode (that mode changes the candidate-stream question and
  would confound parameter-sensitivity interpretation; if ever used, oracle
  sensitivity must be a separately labelled diagnostic, not mixed into this
  primary result);
- add interaction (multi-dimension) configurations before the OFAT evidence
  itself justifies one, declared before its results are inspected.

## Prerequisite: Issue #30 integration

Before Issue #31 work started, Issue #30 ("P1.12 Add broader sequences") had
to be present on `main`. Issue #30's 30-commit branch
(`issue-30-broader-sequences`, baseline `f1f02ebb` -> `37ed4573`, plus
post-closure documentation-promotion commit `460570c1`) existed only in an
isolated session and was not yet reachable from `origin/main`. That branch
was pushed and merged via PR #71
(`git@github.com:FRCTavares/IST-Thesis-Code.git`), producing merge commit
`c2bf9ef56f164f83a9e47446478f0284c5eb7362` on `main`. `issue-31-parameter-sensitivity`
was branched from that updated `main`, so Issue #31 starts from the
corrected-ByteTrack Seq03/Seq04 evidence Issue #30 established.

### Slice 1 -- protocol freeze and deterministic sweep matrix

Before any TIM replay outcome exists, this slice freezes the scientific
protocol, the machine-readable sweep manifest, and the sweep tooling, and
commits them as one reviewable unit.

**Canonical configuration.** The live canonical YAML
(`ros2_ws/src/thesis_bringup/config/tim_mars_canonical.yaml`) was
re-verified by `sha256sum` directly against the file on the authoritative Pi
repository immediately before writing the manifest:
`e9dc78c8e60d5c108e608a449803832738e39867ddd708a4d6855bbb782fe931`. This
hash is pinned in the manifest and re-verified by the sweep tool at every
invocation (materialize, dry-run, or eventual run), failing closed on any
mismatch (`CanonicalHashMismatch`).

**Stale canonical-config hash review.** Two other tracked documents record a
different canonical-config SHA-256
(`e7620313be428cac4d2d1f5595dc48b1f6127a43c22f1b4149049beba1e207ff`):
`docs/data/splits/tim_mars_split_v1.json`'s `freeze.canonical_config.sha256`
(freeze dated 2026-07-23) and `docs/TODO_LIST.md` item 12's P0.17 completion
note, which describes "deterministic development replay and the complete
seven-row ablation matrix were rerun from the clean committed implementation
under canonical configuration SHA-256 `e7620313...`" -- a specific historical
run, not a present-tense claim about the current file. `docs/NOVELTY.md`
section 8.4 cites a third, still-different hash
(`16f21b2032135858d2ea7d5d8081536eb24204a3ef0f12efb05a628d626a0655`),
explicitly tied to the P0.4 clean-freeze report and commit `1b7dc4002...`.
All three are correctly-scoped historical snapshots -- the canonical
configuration has legitimately changed since each freeze/run date -- so none
were edited. Issue #31 pins only the live hash above; it does not rewrite
any historical snapshot to make it match today's file, per the operator's
explicit instruction not to mutate frozen/historical artifacts to force
hash agreement.

**Development-set membership and the Seq03/Seq04 provenance correction.**
`docs/data/splits/tim_mars_split_v1.json` remains the sole authority for
which four physical sequences belong to the development set:
`dev_may_hard_reentry`, `dev_june_seq01`,
`dev_june_seq03` (split entry `dev_june_seq03_ocsort`), and
`dev_june_seq04` (split entry `dev_june_seq04_ocsort`). The split's own
Seq03/Seq04 entries point to an OC-SORT replay chain
(`bags/replay/p018_ocsort_sequences_305578f3_2026_07_19/seq0{3,4}_ocsort_freeze_r1`),
which Issue #30 Slice 15 (`docs/issues/p1-12-broader-sequences.md`) traced
and found did not satisfy a ByteTrack-baseline requirement. Issue #30
generated corrected ByteTrack deterministic-replay evidence for the *same
two physical sequences* from their official ByteTrack `full_pipeline`
capture bags. Issue #31 maps `dev_june_seq03`/`dev_june_seq04` to that
corrected-ByteTrack provenance in the manifest, with the stale OC-SORT
path/annotation retained alongside it as `stale_split_reference` for
traceability. This is a provenance correction to which artifact represents
an already-frozen physical sequence, not a change to development-set
membership and not an outcome-driven substitution -- the correction predates
and is independent of any Issue #31 sensitivity outcome.
`docs/data/splits/tim_mars_split_v1.json` itself is not modified.

Exact corrected artifacts (re-hashed directly from the Pi repository,
matching `docs/data/external_benchmark/sequence_manifest.json` entries
`ros2_internal_development_seq03_crossing` /
`ros2_internal_development_seq04_occlusion`):

| Sequence | Source bag (ByteTrack `full_pipeline`) | Source `sha256` | Annotation | Annotation `sha256` | Target ID |
|---|---|---|---|---|---:|
| `dev_june_seq03` | `bags/source/official_flights/2026-06-19/seq03_crossing_ambiguity/full_pipeline/2026-06-19__12-57-48__video__2026-06-19__official__seq03__four_person_crossing_ambiguity__yolov8s_bytetrack_tim_mars` | `c3016fc90db91efb0a3a4c72a10a675ecb278e378f961d92d587364f3431be8d` | `docs/data/annotations/june_hard_sequences/seq03_bytetrack.csv` | `712665aee6d40ff2d060761896c6f8e82037fe4f596f951f42b41c2a8042e43b` | 2 |
| `dev_june_seq04` | `bags/source/official_flights/2026-06-19/seq04_occlusion_no_exit/full_pipeline/2026-06-19__13-01-36__video__2026-06-19__official__seq04__four_person_occlusion_no_exit__yolov8s_bytetrack_tim_mars` | `50455abd49d0be4d189c58635cbdccdfcc12f62506a9acdafb0d44fd1fa18423` | `docs/data/annotations/june_hard_sequences/seq04_bytetrack.csv` | `27ba56dcbfcfffbdaf4027cae3806193c07de949e7601cb4fc16196e06d92428` | 1 |

`dev_may_hard_reentry` and `dev_june_seq01` are unchanged from the split
file (both already ByteTrack).

**Seven sensitivity dimensions, 29 configurations.** The frozen matrix
holds exactly 1 canonical baseline plus 4 non-canonical perturbations per
dimension across 7 dimensions (1 + 7*4 = 29):

1. **Acceptance threshold pair** (`accept_score_locked` / `accept_score_lost`,
   canonical `0.52`/`0.60`) -- swept jointly as one conceptual dimension,
   preserving the canonical `0.08` LOST-LOCKED gap at every point:
   `0.42/0.50`, `0.47/0.55`, canonical, `0.57/0.65`, `0.62/0.70`.
2. **Ambiguity margin** (`ambiguity_margin`, canonical `0.07`): `0.03`,
   `0.05`, canonical, `0.09`, `0.11`.
3. **Conservative appearance minimum**
   (`appearance_conservative_min_similarity`, canonical `0.65`): `0.55`,
   `0.60`, canonical, `0.70`, `0.75`. The simpler `appearance_min_similarity`
   base gate (`0.35`) is a distinct scoring gate, not this dimension, and is
   kept fixed throughout.
4. **Conservative appearance separation margin**
   (`appearance_conservative_margin`, canonical `0.05`): `0.01`, `0.03`,
   canonical, `0.07`, `0.09`.
5. **Hard-negative rejection threshold** (`hard_negative_reject_similarity`,
   canonical `0.80`): `0.70`, `0.75`, canonical, `0.85`, `0.90`.
   `hard_negative_min_candidate_similarity` (gallery admission, a different
   mechanism) is kept fixed.
6. **Hard-negative rejection margin** (`hard_negative_reject_margin`,
   canonical `0.03`): `0.00`, `0.015`, canonical, `0.045`, `0.06`.
7. **Confirmation time** (`min_confirm_frames_after_reacquire`, canonical
   configured value `1`, effective requirement `2` frames since the
   implementation requires one more frame than configured): configured
   `0`/`1`/`2`/`3`/`4` -> effective `1`/`2`(canonical)/`3`/`4`/`5` frames.
   Only one "lower" perturbation exists (configured value cannot go
   negative). `rank_aware_confirm_frames`, `hard_negative_confirm_observations`,
   `appearance_trusted_lock_frames_before_update`, and `max_uncertain_frames`
   are distinct mechanisms and are kept fixed at canonical throughout.

29 configurations x 4 development sequences = **116** deterministic TIM
replay experiments, none of which have been run as of this slice.

**Manifest.** `docs/data/parameter_sensitivity/tim_mars_parameter_sensitivity_v1.yaml`
stores the 7 dimensions (each with its 4 declared perturbations) as the
single source of truth; it does not separately enumerate the flattened
29-configuration list, so there is nothing that can drift out of sync with
the dimensions. `raw_target_mode: source` is declared once at manifest
level and enforced by schema validation.

**Tooling.** `tools/experiments/run_tim_parameter_sensitivity.py` mirrors
the architecture of `tools/experiments/run_tim_component_ablation.py`
(manifest -> validated, materialized per-configuration YAML -> deterministic
replay -> evaluation), adapted for the dimension/perturbation manifest shape
instead of a fixed row list, and delegates to the same
`run_deterministic_tim_replay.py` for replay and to
`tools/analysis/evaluate_tim_event_recovery.py` for evaluation (no TIM-MARS
algorithm logic is duplicated). It:

- deterministically derives the ordered 29-configuration list from the
  manifest's `dimensions` alone (`derive_configurations`);
- verifies the live canonical YAML's hash against the manifest's pinned
  value before materializing anything, failing closed on mismatch;
- materializes one YAML per configuration plus a `parameter_sensitivity_lock.json`
  (git commit/branch/dirty state, manifest hash, canonical hash, per-config
  hash) and never writes to the canonical YAML itself;
- verifies the materialized baseline configuration is byte-identical to the
  canonical file;
- verifies every non-baseline configuration's resolved parameters differ
  from canonical at exactly its declared dimension's parameter set (OFAT
  isolation) and that every acceptance-pair configuration preserves the
  `0.08` gap;
- supports `--print-matrix` (prints all 29 configurations and the 116-run
  accounting, no materialization or TIM execution) and `--materialize-only`
  (writes configs + lock file, no TIM execution);
- supports `--dry-run` (prints every replay/evaluate command that `--run`
  would execute and writes `run_provenance.json`, without invoking any
  subprocess -- verified to work against the real manifest and real source
  bags without requiring a MARS model or executing anything);
- supports (for later use) `--run`, `--resume`, and per-sequence/per-config
  filtering, and refuses to aggregate results while any expected
  config x sequence cell is missing (`MissingCellError`);
- verifies the raw/ByteTrack reference stream for each sequence is
  invariant across configurations (`assert_raw_invariant`), so a repeated
  raw baseline is checked for equality rather than treated as new
  independent evidence.

**Validation.** 34 focused tests
(`tools/tests/test_run_tim_parameter_sensitivity.py`) cover: manifest
determinism; exactly one canonical baseline; exactly 29 unique
configurations; exactly 116 expected cells; OFAT isolation per dimension;
the acceptance-pair `0.08` gap (including a rejection test for a broken
gap); the canonical YAML being byte-unchanged after materialization; the
baseline configuration being byte-identical to canonical; fail-closed
canonical-hash-mismatch behaviour; rejection of `legacy_validation`/
`final_held_out` split membership; the explicit Seq03/Seq04
corrected-ByteTrack mapping; rejection of a perturbation that does not
actually move away from canonical; rejection of a configuration that
touches a parameter outside its declared dimension; rejection of a
negative confirmation-time value; the configured/effective confirmation
frame mapping; `--raw-target-mode source` always being passed to the
replay tool; a real `--dry-run` invocation's provenance recording runtime
overrides and 58 child commands (29 configs x 2 commands) for a
single-sequence slice; and that missing cells block aggregation while
complete cells do not. All 34 pass.

`--print-matrix` was run against the real manifest and printed all 29
configurations and the `116 deterministic TIM replay experiments`
accounting line. `--materialize-only` was run against the real manifest and
produced 29 materialized configuration files plus a lock file recording
`unique_configurations: 29` and `total_replay_runs: 116`, with the
canonical YAML unchanged before/after (`sha256` identical).

**Not yet done (at end of Slice 1).** No replay or evaluation command was
executed (`--run` was never passed). No sensitivity outcome exists yet.
`docs/TODO_LIST.md` item 15 is updated to record that the protocol/tooling
stage is underway, but Issue #31 is not marked complete.

### Slice 2 -- Phase B execution (116 cells) and Phase C aggregation

All 116 deterministic TIM replay + event-recovery evaluation cells (29
configurations x 4 development sequences) were executed with `tools/
experiments/run_tim_parameter_sensitivity.py --run --resume`, one sequence
batch at a time, against the lock and manifest frozen in commit `5b340c2b`.
The canonical config hash
(`e9dc78c8e60d5c108e608a449803832738e39867ddd708a4d6855bbb782fe931`) was
re-verified by `sha256sum` directly against the live file on the
authoritative Pi repository after every batch and never drifted.

**Execution accounting.**

| Sequence | Cells | Missing | Duplicated | Notes |
|---|---:|---:|---:|---|
| `dev_may_hard_reentry` | 29/29 | 0 | 0 | 2 cells (`baseline`, `ambiguity_margin_lower_2`) pre-existed from an earlier smoke test and were correctly resumed/skipped, not re-executed or duplicated -- confirmed via the run's `child_commands` count (54 = 27x2, not 58 = 29x2) |
| `dev_june_seq01` | 29/29 | 0 | 0 | first launch attempt crashed on cell 1 with `ModuleNotFoundError: No module named 'rosbag2_py'`; zero cells had been written at that point; root cause was that the invoking non-interactive SSH shell did not source `/opt/ros/jazzy/setup.bash` + the workspace overlay (`.bashrc` is not sourced for non-interactive SSH command execution); `/opt/ros/jazzy` and the workspace overlay were confirmed present and importable once sourced, and `dpkg`/`unattended-upgrades` logs showed no relevant package change near the failure time, ruling out environment corruption; the invocation was corrected and the full sequence re-run cleanly (58 = 29x2 fresh commands, 0 failures) |
| `dev_june_seq03` | 29/29 | 0 | 0 | clean run, 58 = 29x2 fresh commands |
| `dev_june_seq04` | 29/29 | 0 | 0 | clean run, 58 = 29x2 fresh commands |

**Total: 116/116 cells, 0 missing, 0 duplicated, 1 tooling-invocation retry
that wrote no cells before being corrected, 0 data/evidence-affecting
failures.**

The raw/ByteTrack reference stream invariance the runner enforces per
sequence (`assert_raw_invariant`) was independently re-verified across all
116 cells after execution by hashing `duration_metrics.raw_target` and the
per-cell `provenance.source_manifest` (reference bag name/hash/size): both
hash to a single value across all 29 configurations within every one of the
4 sequences.

**Aggregation.** `tools/analysis/aggregate_parameter_sensitivity_report.py`
(new; imports `expected_cells`/`missing_cells` from the frozen runner rather
than reimplementing the completeness check, and refuses to run while any
cell is missing) combines all 116 per-cell `report.json` files into a
116-row all-cells table and a 29-row cross-sequence aggregate table (durations
summed across the 4 sequences per configuration), then reshapes the
aggregate into a per-dimension trade-off table sorted by true parameter
value with canonical inserted at its correct monotonic position (not
positionally first -- an early version of the figure script prepended
canonical unconditionally, which silently mislabelled the x-axis order for
every dimension; caught by inspecting the rendered figure before promotion,
not by a test). `tools/analysis/plot_parameter_sensitivity.py` renders two
deterministic figures (Agg backend, fixed styling) from the aggregate CSV
only.

**Sensitivity outcome.** Four of the seven dimensions (acceptance-pair
thresholds, conservative-appearance minimum similarity, hard-negative reject
similarity, hard-negative reject margin) produced zero measurable change on
any of the 4 development sequences at any tested perturbation level: the
canonical safety/correctness conclusion is robust to reasonable OFAT
perturbation of these four parameters in this development set. Ambiguity
margin has a real but narrow effect entirely localized to
`dev_june_seq03` (the crossing-ambiguity sequence, which also carries almost
all of this development set's raw wrong-target duration), consistent with
the parameter's role and evidence this is genuine TIM-MARS behaviour rather
than a replay/evaluator/tooling artifact. Conservative-appearance margin
trades availability only and never safety across the tested range.
Confirmation time is the dominant trade-off, monotonic in the expected
direction on both metrics, with canonical sitting inside the trend rather
than at an extremum. No tested perturbation reduces both wrong-target and
lost-target duration simultaneously relative to canonical. Full tables and
figures: `docs/results/selected_target_tracking/p031_parameter_sensitivity_summary.md`.

**Issue #31 scope is complete.** The development-set OFAT
sensitivity/robustness question this issue was scoped to answer (this
document's own Objective, and the live GitHub issue #31 completion
contract) is answered: all 116 cells executed, aggregated, and interpreted
above.

**Held-out H01-H03 is not remaining Issue #31 work.** Per
`docs/research_question.md`, Issue #27 owns the prospective H01-H03
held-out recordings and remains deferred to September 2026 by the
operator's 23 July 2026 decision -- a decision that predates and is
independent of Issue #31. Held-out evidence remains required later, but
only for the thesis-wide final generalisation claim (gated through Issue
#39 on #27, #58, #32, and #44), not for closing this issue. This is a
scope clarification, not a weakening of the held-out requirement itself:
nothing about the eventual thesis-wide claim's dependence on H01-H03 has
changed.

**Not yet done (at end of Slice 2).** Only process items outside this
issue's scientific scope remain: the branch has not been reviewed/merged
and Issue #31 has not been closed.
