# P1.12 Broader Sequences (External + ROS 2 Selected-Target Benchmark)

## Purpose

Issue #30 evaluates whether TIM-MARS improves selected-person tracking over
raw ByteTrack across a broader sequence set than the four original ROS 2
development sequences: DanceTrack and VisDrone-MOT external stress tests
were captured and evaluated alongside them, then a post-freeze,
pre-outcome scope decision retained a 7-sequence primary benchmark. It does
not change TIM-MARS runtime policy, canonical parameters, detector
settings, or ByteTrack settings.

## Evidence

- Branch: `issue-30-broader-sequences`, baseline `f1f02ebb8742e69bf6a1a5e416da2061b8efb1c4`
- Final commit range for this evidence: `f1f02ebb` .. `37ed4573` (30 commits)
- Frozen manifest: `docs/data/external_benchmark/sequence_manifest.json`
  (`schema_version: 1`, `status: frozen`, `frozen_date: 2026-08-07`,
  `manifest_commit: 124118b362ea1f44c8211722378c2347a84d4cfc`)
- Canonical TIM-MARS config SHA-256:
  `e9dc78c8e60d5c108e608a449803832738e39867ddd708a4d6855bbb782fe931`
- ReID model SHA-256:
  `e96f3cc09dbce76e2f6aeff09c8f2502916b4745f21e27911ee50d102a4a75f1`

  Both hashes are identical across every full-pipeline and oracle-candidate
  run in this evidence set (verified directly from each replay bag's own
  `tim_replay_metadata.json`); there is no configuration drift between
  sequences or between this issue's slices.
- Regression validation: 71 focused tests across
  `tools/tests/test_aggregate_first_phase_report.py`,
  `test_aggregate_oracle_report.py`, `test_select_first_phase_benchmark.py`,
  `test_add_ros2_first_phase_sequences.py`,
  `test_run_external_sequence_report.py`,
  `test_resolve_external_candidate_stream.py`,
  `test_build_oracle_candidate_bag.py`, and
  `test_bbox_size_stratified_report.py`, plus 17 tests in
  `ros2_ws/src/thesis_bringup/test/test_tim_mars_runtime.py`.
- Full engineering history, forensic investigations, and every intermediate
  finding: `docs/issues/p1-12-broader-sequences.md` (29 slices).

## Final retained primary scope

7 sequences: 4 ROS 2 development + 3 VisDrone-MOT.

| Sequence | Dataset | Status |
|---|---|---|
| `may_hard_reentry` | ros2_internal | evaluated |
| `seq01_clean` | ros2_internal | evaluated |
| `seq03_crossing` | ros2_internal | evaluated |
| `seq04_occlusion` | ros2_internal | evaluated |
| `uav0000117_02622_v` | visdrone_mot | initialization_failure |
| `uav0000137_00458_v` | visdrone_mot | initialization_failure |
| `uav0000339_00001_v` | visdrone_mot | evaluated |

Accounting: **5 evaluated, 2 genuine `initialization_failure`, 0 missing.**
Both initialization failures were forensically verified as real
detector/candidate misses under the frozen IoU/margin/confirmation rule,
not pipeline bugs, and are kept in the denominator rather than explained
away.

## Full-pipeline results (detector -> ByteTrack -> raw / TIM-MARS)

ROS 2 sequences use the Issue #26 event-recovery vocabulary (duration
ratios); the VisDrone sequences use the frame-level outcome taxonomy
(frame counts). The two vocabularies are related but not identical (see
`docs/issues/p1-12-broader-sequences.md`, Slice 13); they are reported
side by side, not merged into one number.

| Sequence | Raw correct | Raw wrong | TIM correct | TIM wrong |
|---|---:|---:|---:|---:|
| `may_hard_reentry` | 56.5% | 11.7% | 92.3% | 0.1% |
| `seq01_clean` | 45.4% | 0.0% | 88.9% | 0.0% |
| `seq03_crossing` | 13.0% | 56.4% | 77.2% | 6.3% |
| `seq04_occlusion` | 10.5% | 1.2% | 69.7% | 0.0% |
| `uav0000117_02622_v` | -- (initialization_failure) | -- | -- | -- |
| `uav0000137_00458_v` | -- (initialization_failure) | -- | -- | -- |
| `uav0000339_00001_v` | 26/275 (9.5%) | 0/275 (0.0%) | 72/275 (26.2%)&sup1; | 0/275 (0.0%) |

&sup1; 70 `correct_target` + 2 `correct_same_person_recovery`.

TIM-MARS raises correct-target fraction **and** reduces-or-matches
wrong-person fraction versus raw ByteTrack on every evaluable sequence --
no correctness/safety tradeoff anywhere in the primary result, and no
wrong-target increase that would block promotion under this issue's own
completion contract.

Source reports:
`artifacts/reports/p030_broader_sequences/external_frame_reports/visdrone_mot_val_uav0000339_00001_v.json`,
`reports/p026_event_recovery_b50f914a_2026_08_05/{may_hard_reentry,seq01_clean}/report.json`,
`artifacts/reports/p030_broader_sequences/seq0{3,4}_*_bytetrack/report.json`,
aggregated at
`artifacts/reports/p030_broader_sequences/first_phase_aggregate.json`.

## Oracle-candidate results (diagnostic, kept separate from the full pipeline)

Oracle mode replaces the detector and tracker with an idealized,
ground-truth-derived candidate stream, isolating TIM-MARS's own
identity-memory and appearance-confirmation behaviour from detector/tracker
candidate availability. It answers a different question than the table
above and is never combined with it into one headline metric. Only the 3
VisDrone sequences have a declared oracle contract; the 4 ROS 2 sequences
do not (no dense per-frame multi-person ground truth exists for them, only
a single official `correct_target_track_id` per sequence).

| Sequence | Raw correct | TIM correct | TIM wrong | TIM suppressed |
|---|---:|---:|---:|---:|
| `uav0000117_02622_v` | 349/349 (100%) | 1/349 (0.3%) | 0 | 348 |
| `uav0000137_00458_v` | 233/233 (100%) | 226/233 (97.0%) | 0 | 7 |
| `uav0000339_00001_v` | 275/275 (100%) | 61/275 (22.2%) | 0 | 214 |

Raw's 100% is a construction property of oracle mode (one fixed,
ground-truth-correct candidate ID for the whole sequence), not a
tracking-performance baseline -- it must not be read as "raw achieves
perfect tracking." TIM-MARS held **zero wrong-person frames across all
three oracle runs**, the same safety invariant as the full pipeline, but
its willingness to actively publish (versus safely suppress) when a
correct candidate is always available is sharply scene-dependent. The
`uav0000117_02622_v` 0.3% result was investigated against the recorded
per-frame TIM-MARS status diagnostics before acceptance: the target's crop
was always `encoding_eligible` (never too small to encode), but
`group_centre_too_close` fires on every one of its 348 diagnosed frames
and `overlap_with_person` on 61% of them, gating the appearance-memory
update on crowd proximity, not crop size or absolute target height (full
mechanism: `docs/issues/p1-12-broader-sequences.md`, Slice 27).

Source reports:
`artifacts/reports/p030_broader_sequences/oracle_frame_reports/*.json`,
aggregated at
`artifacts/reports/p030_broader_sequences/oracle_aggregate.json`.

## Bbox-height-stratified findings

Ground-truth target bbox height (source-image pixels) is the primary
size measure; normalized height (`bbox_height / image_height`) is retained
per frame in the underlying data. Bins were chosen from the actual pooled
distribution across the 3 VisDrone sequences (66-132px, 857 GT-visible
frames) after the originally-proposed `<20/20-39/40-79/80-159/>=160px`
scheme was found to place 100% of every sequence's frames in one bin:
`<70px`, `70-89px`, `90-109px`, `110-129px`, `>=130px`. This analysis
applies only to the 3 VisDrone sequences; the 4 ROS 2 sequences have no
per-frame multi-person GT bbox contract to stratify by, and no
pseudo-annotation was invented to cover them.

Full-pipeline outcome by bin (only `uav0000339_00001_v` contributes --
the two initialization failures contribute size-distribution and
candidate-availability data only, not raw/TIM outcomes):

| Bin | Frames | Raw correct | TIM correct |
|---|---:|---:|---:|
| `<70px` | 33 | 63.6% | 63.6% |
| `70-89px` | 202 | 2.5% | 25.2% |
| `90-109px` | 40 | 0.0% | 0.0% |

Oracle-candidate outcome by bin (all 3 sequences contribute):

| Bin | Frames | TIM correct | TIM suppressed |
|---|---:|---:|---:|
| `<70px` | 33 | 97.0% | 1 |
| `70-89px` | 443 | 12.9% | 386 |
| `90-109px` | 245 | 46.9% | 130 |
| `110-129px` | 120 | 57.5% | 51 |
| `>=130px` (16 frames, low support) | 16 | 93.8% | 1 |

Zero wrong-person in every bin, every sequence, every mode. The two
initialization failures do not share a size-based root cause:
`uav0000117_02622_v` is poor across *all* of its bins uniformly (not
concentrated in a "too small" bin, arguing against a pure size
explanation), while `uav0000137_00458_v` performs well across nearly all
of its oracle bins. The pooled oracle `70-89px` figure (12.9%) is a
composition effect dominated by `uav0000117_02622_v`'s frames, not a clean
size effect, and should not be read as "TIM is uniquely bad at 70-89px."

Full data, both figures, and the complete per-sequence breakdown:
`artifacts/reports/p030_broader_sequences/bbox_size_stratified_report.{json,csv}`,
`bbox_size_outcome_fractions.png`, `bbox_size_candidate_availability.png`.

## Documented, pre-outcome exclusions (not silent removals)

| Exclusion | Reason | Where recorded |
|---|---|---|
| DanceTrack (5 sequences, captured and evaluated) | Substantially out-of-domain for this thesis's selected-person UAV-following objective | Manifest `status: "excluded"` per sequence; Slice 25 |
| `uav0000268_05773_v` (4K VisDrone) | Disproportionate resource-cost outlier (two capture-tooling bugs found and fixed along the way; report never generated after a disk-safety-guard shortfall) | Manifest `status: "excluded"`; Slice 25 |
| MOT17 (4 sequences originally planned) | Official MOTChallenge source unreachable from the development network (routing-level failure, confirmed from two independent networks) | Slice 12 |
| Detector/tracker/TIM runtime cost (reporting item) | Deferred to the separate, dedicated, still-open Issue #32 (P1.14), which covers it in more depth | Slice 27 |

All exclusions were made before inspecting the excluded sequence's outcome
except DanceTrack's, whose evaluated report (`dancetrack0004`) already
existed at exclusion time and is retained as exploratory evidence, not
promoted into this primary result -- no replacement sequence was selected
to backfill any excluded slot.

## Scenario coverage (GitHub issue's "Required work" list)

| Category | Status |
|---|---|
| Clean multi-person tracking | Covered (`seq01_clean`) |
| Repeated crossings | Covered (`seq03_crossing`; `uav0000117_02622_v` attempted) |
| Short occlusion | Covered -- `may_hard_reentry` (8 `occlusion_ambiguity` intervals, 0.234-2.34s, target-visible) and `seq03_crossing` (7 more, 0.855-6.53s); raw is 0.0% correct / 96.1% wrong during seq03's short-occlusion intervals specifically, TIM-MARS recovers to 69.1% correct / 5.6% wrong |
| Long occlusion | Covered (`seq04_occlusion`: 3 `target_absent` intervals, 8.987s) |
| Exit and re-entry | Covered (`may_hard_reentry`, `seq04_occlusion`) |
| Similar clothing | Excluded from primary scope (DanceTrack only) |
| Small/distant people | Partially covered (bbox-height stratification, 66-132px on retained VisDrone) |
| Partial crops | Explicitly rejected -- not central to the frozen research question; future-work item |
| Illumination change | Explicitly rejected -- same rationale |
| UAV / camera motion | Covered (all 3 retained VisDrone sequences) |

## Limitations

- MOT17, DanceTrack, and `uav0000268_05773_v` are out of primary scope for
  the documented reasons above, not because they were attempted and found
  uninformative.
- Detector/tracker/TIM runtime cost is not characterized here; see #32.
- Partial-crop and illumination-change robustness are open questions this
  evidence does not answer.
- The bbox-size-stratified sample is 3 sequences and 857 frames spanning
  66-132px; it neither validates nor invalidates the project's existing
  `>=20px` target-height operating guideline as a universal threshold --
  no observed target in this sample goes below 66px.
- `uav0000117_02622_v`'s oracle-mode suppression mechanism is documented
  from recorded diagnostics for that one sequence; it is not established as
  a general appearance-matching failure mode across scenes.

## What this evidence demonstrates, and does not demonstrate

**Demonstrates:** under real, imperfect detector/ByteTrack conditions (the
system's actual deployment condition), TIM-MARS's identity memory
substantially raises correct-target time/fraction and simultaneously
reduces or matches wrong-person time/fraction on every sequence that
reaches evaluation, including through short and long occlusion, crossings,
re-entry, and one small/distant external target case. Zero wrong-person
frames were produced in the oracle-candidate diagnostic across all three
runs, and in the primary full-pipeline result wrong-person time only ever
decreases or stays flat under TIM-MARS, never increases.

**Does not demonstrate:** a general claim about anchored-identity tracking
systems as a class (the two initialization failures are a property of this
frozen detector/ByteTrack/initialization pipeline on these two sequences,
not a proven limit of the approach); a universal minimum detectable target
size; robustness to partial crops or illumination change; runtime or
onboard resource cost; or performance on MOT17, DanceTrack, or 4K source
video, all of which remain outside this evidence's scope by explicit,
documented decision rather than by having been tried and found wanting.

## Promotion boundary

This is the canonical, thesis-facing summary of Issue #30's closed
evidence. The full chronological engineering record -- every forensic
investigation, bug fix, and intermediate finding that produced these
numbers -- remains in `docs/issues/p1-12-broader-sequences.md` and is not
duplicated here. Generated JSON/CSV/PNG evidence remains under
`artifacts/reports/p030_broader_sequences/`; this document references
those paths rather than copying their content.
