# P1.13+ Lightweight tracker + TIM-MARS vs. integrated appearance-aware tracking

GitHub Issue: #58
Branch: `issue-58-lightweight-vs-integrated-tracking`
Baseline: `6231fdc1370b78a55ffeee9a403adbbddf4fb424` (main after Issue #31's PR #72 merge)

## Objective

Determine whether a computationally lightweight, appearance-free tracker
paired with selective TIM-MARS identity validation provides a better onboard
safety-availability-cost trade-off than a heavier tracker that performs
appearance association internally, per the live issue body's objective and
scientific question. This is a robustness/architecture-comparison study; it
does not reopen the rejected one-preset-portability claim from Issue #43.

## Slice 1 -- read-only audit and dependency classification

### Repository state at audit time

`main == origin/main == 6231fdc1370b78a55ffeee9a403adbbddf4fb424`, clean,
no root `log/`/`hailort.log`, 69 GB free, no pre-existing Issue #58 branch,
commits, reports, or open PR.

### Live GitHub contracts read in full

Issue #58, #44, #32, #54, #27, #39, and (discovered via #58's own text)
#43.

**Held-out boundary (Issue #27).** #58's completion contract explicitly
requires "every promoted pairing passes the asymmetric safety gate on
held-out data," and the fairness contract ties "held-out" explicitly to
"the split owned by Issue #27." #27's own comments confirm
`final_ready=0/3`, H01-H03 deferred to September 2026 by the operator's 23
July 2026 decision. This manifest and all evidence below is development-set
only; held-out promotion is separate future work gated by #27, exactly as
#39 (final claim freeze) already independently states.

**#44 (CLOSED).** Selective Hailo RepVGG ReID path validated but explicitly
observational-only: "RepVGG ranking, memory, cache and target-decision
integration remain disabled... CPU MARS remains authoritative." No promoted
Hailo decision-path evidence exists. #44's own claim boundary states it
"does not establish... the final resource characterisation owned by Issue
#32." Reused: the 30-minute sustained guarded-load/contention dataset is
available as partial, narrowly-scoped cost context, not as #58's cost
evidence.

**#32 (OPEN).** No canonical per-stage latency/p50-p99/cadence/resource
methodology exists in the codebase yet; only partial primitives
(`tools/timing_contract.py`, `Timing.msg`, `sample_process_groups.py`,
dashboard system metrics). #58's completion contract requires "runtime
evidence uses the canonical Issue #32 methodology" -- genuinely blocked.

**#43 (CLOSED).** The historical "P0.4 clean tracker matrix" referenced by
#58's own text ("does not reopen the rejected one-preset-portability claim
from Issue #43"). Produced a 4-tracker (ByteTrack/SORT/OC-SORT/DeepSORT)
comparison under one shared canonical TIM preset, explicitly finding that
preset unsafe for every non-ByteTrack tracker and calling for
tracker-specific calibration -- exactly #58's job, not something #43
already did. Its raw/TIM numbers are historical context, not reused as
#58 evidence (wrong preset, and for June sequences, as discovered below,
wrong source bag for the non-ByteTrack trackers).

### Requirement classification

| Requirement | Class | Disposition |
|---|---|---|
| Safety/availability architecture comparison on development data | A | Completed for available cells (below) |
| Tracker-specific calibration (fairness contract) | A | SORT+TIM calibration sweep executed |
| Canonical Issue #32 cost methodology | C | Genuinely blocked; #32 open |
| Held-out safety gate | C | Genuinely blocked; #27 deferred to September |
| Hailo appearance backend ablation | C | Blocked; #44 kept the path observational-only |
| Reuse #44 sustained-load evidence | B | Reused as narrow context, not #58-quality cost data |

## Slice 2 -- architecture roles frozen (operator-directed, 2026-08-08)

- `bytetrack_raw` / `bytetrack_tim`: lightweight raw baseline / the intended
  architecture. `bytetrack_tim` reuses the Issue #31 canonical baseline cell
  directly (`data_source: reuse_p031`); canonical TIM-MARS is not retuned.
- `sort_raw` / `sort_tim`: minimal appearance-free pairing, required by
  #58's own "Required systems" checklist ("using SORT or an IoU-only
  tracker" -- not the optional item; SORT satisfies the required role).
  `sort_tim` requires new tracker-specific calibration (Slice 3).
- `deepsort_raw` / `deepsort_tim`: integrated appearance-aware reference /
  diagnostic. Real MARS ReID verified active by code inspection before
  trusting the label (`build_backend()` requires a real `--model` path to
  `mars-small128.pb`, raises if absent). `deepsort_tim` is diagnostic only
  per the issue's own text, never promoted as competitive with
  `bytetrack_tim`.
- ByteTrack, not OC-SORT, fills the "stronger appearance-free tracker"
  role: ByteTrack+TIM is already the frozen canonical thesis architecture
  (#26/#30/#31); a fresh OC-SORT calibration sweep would answer a
  portability question beyond #58's core scope and was excluded by
  operator decision. StrongSORT/BoT-SORT excluded per the issue's own
  "only if... does not displace higher-priority work" hedge.

Manifest: `docs/data/lightweight_vs_integrated_tracking/p058_lightweight_vs_integrated_tracking_v1.yaml`.

## Slice 3 -- SORT+TIM calibration protocol and result

Reuses the frozen Issue #31 7-dimension/29-configuration OFAT parameter
grid verbatim (imported from `run_tim_parameter_sensitivity.py`, never
copied) against SORT's own `/tracks` stream instead of ByteTrack's. Does
not retune canonical ByteTrack+TIM-MARS and never writes to the canonical
YAML.

**Scope correction discovered during manifest construction.** SORT
physical-target annotations exist only for `dev_may_hard_reentry`
(`docs/data/annotations/may_hard_reentry/sort_f17cdf80_autonomous.csv`).
`dev_june_seq03`/`dev_june_seq04` have no SORT annotation at all. The
calibration manifest was corrected to calibrate on May alone (29 cells,
not 87) rather than fabricate or silently skip the gap.

Manifest: `docs/data/lightweight_vs_integrated_tracking/p058_sort_tim_calibration_v1.yaml`.
Runner: `tools/experiments/run_tim_tracker_calibration.py` (print-matrix /
materialize-only / run --resume, mirroring the P031 pattern). Tests:
`tools/tests/test_run_tim_tracker_calibration.py` (10 tests, all passing).

**Result: no configuration passes the asymmetric safety gate.** Raw SORT
on May never publishes a wrong-target output at all
(`raw_wrong_s = 0.000`, consistent with the historical #43 evidence, which
also measured exactly 0.000). Every one of the 29 TIM configurations
increases wrong-target duration to 15.331-16.331 s -- the closest
candidate (`confirmation_time_higher_3`, the most conservative
reacquisition setting tested) still fails the gate by orders of magnitude.
This is a genuine finding, not a tooling failure: it matches one of the
valid conclusions #58's own text anticipates ("the minimal tracker does not
expose enough viable candidates, establishing TIM-MARS's lower operational
boundary"). The selector fails closed (`NoPromotableConfiguration`) rather
than silently promoting a losing configuration; `sort_tim` is recorded with
status `no_safe_configuration_found`, not `available`, with the closest
candidate's numbers attached for transparency.

Aggregate: `reports/p058_sort_tim_calibration_6231fdc1_2026_08_08/aggregate/calibration_aggregate.csv`.

## Slice 4 -- second annotation-integrity finding (Seq03/Seq04 DeepSORT)

While preparing DeepSORT execution on the June sequences, cross-checking
the existing `seq04_deepsort.csv` annotation's first-interval
`correct_target_track_id=5` against a fresh deterministic replay of the
canonical `full_pipeline` source found that track ID 5 never appears
anywhere in the replay. Investigation traced this to the annotation's
`bag_name` field referencing a *different* source bag entirely: a separate
"image_raw"-only diagnostic capture recorded roughly two minutes before the
canonical `full_pipeline` bag (`12-59-53` vs `13-01-36` for Seq04;
`12-55-58` vs `12-57-48` for Seq03) -- a genuinely different recording, not
a renumbering artifact. Reusing these annotations against the canonical
source would have silently produced meaningless evidence, the same failure
mode already proven for SORT-on-Seq01.

May's SORT and DeepSORT annotations were separately verified *not* to have
this problem (no alternate timestamped capture exists for May; SORT's
`track_id=1` presence pattern in a fresh replay matches the annotation's
expected interval) before being trusted.

**Net effect on availability:**

| | May | Seq01 | Seq03 | Seq04 |
|---|---|---|---|---|
| ByteTrack | available (#31 reuse) | available (#31 reuse) | available (#31 reuse) | available (#31 reuse) |
| SORT | available | pending_annotation | pending_annotation | pending_annotation |
| DeepSORT | available | pending_annotation | pending_annotation (annotation references wrong source bag) | pending_annotation (annotation references wrong source bag) |

Six pending-annotation files are recorded explicitly in the manifest
(`pending_annotation_files`), each with its blocking (architecture,
sequence) pairs and reason (`no_annotation_exists` or
`existing_annotation_references_wrong_source_bag`), never silently dropped.

## Slice 5 -- execution and aggregation

Tracker-output bags for SORT and DeepSORT generated deterministically from
the same frozen source bags used throughout #26/#30/#31 (same
`/detections` stream regardless of tracker, by construction of
`run_deterministic_tracker_replay.py`, which regenerates `/tracks` fresh
from a bag's existing detections):
`bags/replay/p058_lightweight_vs_integrated_6231fdc1_2026_08_08/tracker_bags/`.

Aggregator: `tools/analysis/aggregate_lightweight_vs_integrated_report.py`.
Tests: `tools/tests/test_aggregate_lightweight_vs_integrated_report.py` (9
tests: asymmetric-gate selection logic including the fail-closed path,
pending-cell accounting, correct raw-vs-TIM stream extraction).

**24/24 cells accounted for** (6 architectures x 4 sequences): 11
`available`, 12 `pending_annotation`, 1 `no_safe_configuration_found`. Zero
silently missing, zero fabricated.

### Results (May hard re-entry -- the only sequence with complete evidence across all three trackers)

| Architecture | Correct [s] | Wrong [s] | Lost [s] | Status |
|---|---:|---:|---:|---|
| `bytetrack_raw` | 38.283 | 7.927 | 21.490 | available |
| `bytetrack_tim` | 62.513 | 0.100 | 5.087 | available |
| `sort_raw` | 29.286 | 0.000 | 37.032 | available |
| `sort_tim` | -- | 15.331 (closest, not promoted) | 6.919 | no_safe_configuration_found |
| `deepsort_raw` | 18.678 | 32.087 | 17.100 | available |
| `deepsort_tim` | 16.178 | 26.734 | 24.953 | available |

`bytetrack_tim`'s numbers are byte-identical to Issue #31's canonical
baseline cell for `dev_may_hard_reentry` (reused directly, not
re-executed), which also cross-validates that this issue's fresh
`deepsort`/`sort` replays used the same canonical source and evaluator
contract.

Full matrix (including the 4 fully-`available` ByteTrack rows on
Seq01/Seq03/Seq04, reused from Issue #31):
`reports/p058_lightweight_vs_integrated_6231fdc1_2026_08_08/aggregate/matrix_all_cells.csv`.

## Scientific interpretation (May only; other sequences pending)

On the one sequence with complete cross-architecture evidence:

- **The intended architecture (ByteTrack + canonical TIM-MARS) is both the
  safest and most available system measured**: wrong-target duration falls
  to 0.100 s (from a 7.927 s raw baseline) while correct-target duration
  rises to 62.513 s, the highest of any row.
- **The minimal lightweight pairing (SORT + TIM-MARS) does not clear the
  safety bar within the tested calibration grid.** Raw SORT itself is
  perfectly safe by this metric (0.000 s wrong) but loses the target for
  more than half the sequence; every tested TIM configuration trades that
  availability gap for a large, disqualifying wrong-target regression. This
  is evidence for TIM-MARS's *lower operational boundary*, one of the
  explicitly valid conclusions in #58's own text, not a defect in the
  comparison.
- **The integrated appearance-aware reference (DeepSORT) is, surprisingly,
  the least safe raw tracker measured on this sequence** (32.087 s wrong,
  more than ByteTrack raw's 7.927 s and far more than SORT raw's 0.000 s),
  and layering TIM-MARS on top only partially mitigates it (32.087 to
  26.734 s) while reducing correct-target time. Framed per the issue's own
  architecture boundary text, this is consistent with `deepsort_tim`
  duplicating appearance-based identity reasoning already present in
  DeepSORT's own association step -- diagnostic evidence of exactly the
  conflict the issue anticipated, not a claim that DeepSORT is broadly
  unsafe.

**This is single-sequence evidence and must not be generalized.** Seq01,
Seq03, and Seq04 remain `pending_annotation` for both SORT and DeepSORT;
the pattern above may not hold once those sequences are added.

## Cost evidence

No canonical Issue #32 measurement exists for any architecture. Recorded
now (schema in the manifest's `cost_evidence_schema`, ready for #32 to join
later without rerunning anything): replay operation counts and per-cell
provenance (config/model hashes, commit, repository state). All
wall-clock-latency/CPU-service-time/RSS/Hailo-contention/thermal/power
fields are explicitly `unavailable_pending_issue_32`, never zero, never
omitted.

## Not yet done

- Seq01/Seq03/Seq04 SORT and DeepSORT annotations (6 files) --
  `pending_annotation`, explicitly not fabricated. The complete workload
  (replay bags, full provenance/hashes, recommended annotation order,
  per-sequence physical-target/ID-switch/target-absence instructions, and
  a fail-closed stale-source-bag validator with 15 tests) is prepared in
  `docs/results/selected_target_tracking/p058_lightweight_vs_integrated_tracking_development/PENDING_ANNOTATION_QUEUE.md`
  for a later manual-annotation session; inserting a completed CSV requires
  no protocol, calibration, or architecture change (Section "Inserting a
  completed annotation later requires no protocol change" in that file).
  Until then, the May-only results above are a development finding, not a
  general architecture conclusion.
- Held-out evaluation -- blocked on Issue #27 (September 2026).
- Canonical cost/resource evidence -- blocked on Issue #32 (open).
- Promoted Hailo appearance-backend ablation -- blocked on Issue #44's
  observational-only scope (closed, would require new work to promote).
- Deterministic thesis figures and a fully polished CLI runner for the main
  comparison (materialize/print-matrix/dry-run parity with the calibration
  runner) -- deferred; the underlying evidence and aggregation are complete
  and tested, figure generation was not reached in this session.

Issue #58 is not closed. The branch is not merged.
