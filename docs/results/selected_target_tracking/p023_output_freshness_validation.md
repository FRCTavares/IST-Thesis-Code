# P0.14 output-freshness validation

Date: 22 July 2026  
Implementation commit: `c0052fed23ee88e7d6f39ca43d358ed199b6f371`  
Contract: `tim_mars_output_freshness_v1`  
Canonical maximum output age: 0.90 s  
Future timestamp tolerance: 0.05 s

## Scope

Issue #23 replaces indefinite latest-preceding output holding with a shared
freshness result. Live control checks source-observation age separately from
local receive age and fails closed for missing, invalid, future, duplicate,
non-monotonic, or stale source timestamps. TIM status and dashboard transport
the result, recorded metadata stores the selected maximum, and the ID,
event-type, and bbox evaluators classify stale output as lost while recording
its duration.

## Validation

Validation ran on the Raspberry Pi from a clean checkout whose `HEAD` and
`origin/main` both resolved to the implementation commit.

- Focused contract/control/evaluator tests: 45 passed.
- Focused tracker source-stamp tests: 3 passed.
- Full `thesis_bringup` suite: 205 passed, 1 skipped, 3 expected xfails.
- Full `thesis_tracker` suite: 12 passed, 1 skipped.
- Full `tools/tests` suite: 63 passed.
- `tools/thesis_build.sh --packages-select thesis_tracker thesis_bringup`: both
  packages passed.
- `git diff --check` and `bash -n tools/start_live_stack.sh`: passed.
- Root `log/`, `hailort.log`, and `.pytest_cache`: absent after validation.

The MAVROS-disabled live run `2026-07-22__15-45-02` confirmed:

- `/tracks.src_stamp_ns` was nonzero even when the separate timing callback had
  not populated tracker context;
- TIM copied the same nonzero source stamp into `TargetState`;
- TIM status reported `fresh`, source age 15.77 ms, and maximum age 900 ms;
- the no-target control command was exactly zero;
- all processes stopped cleanly.

## Clean-commit evaluator comparison

The authoritative ID evaluator was run twice on each retained source/reference
bag with image-header time: once with a practically infinite maximum
(`1000000000` s, representing the previous indefinite hold) and once with the
new 0.90 s maximum. These are evaluator-contract safety checks on retained
source streams; they do not replace the separately promoted P0.7 scientific
results.

| Sequence | Stream | Legacy correct/wrong/lost [s] | Fresh correct/wrong/lost [s] | Stale [s] |
|---|---|---:|---:|---:|
| seq01 | raw | 71.690 / 0.000 / 50.650 | 55.550 / 0.000 / 66.790 | 16.140 |
| seq01 | TIM | 71.690 / 0.000 / 50.650 | 54.600 / 0.000 / 67.740 | 17.340 |
| May | raw | 38.350 / 7.777 / 21.573 | unchanged | 0.000 |
| May | TIM | 60.490 / 0.270 / 6.940 | unchanged | 0.000 |
| seq03 | raw | 13.900 / 54.129 / 27.698 | unchanged | 0.000 |
| seq03 | TIM | 21.310 / 48.517 / 25.900 | unchanged | 0.000 |
| seq04 | raw | 6.439 / 0.200 / 50.183 | unchanged | 0.000 |
| seq04 | TIM | 6.043 / 21.179 / 29.600 | unchanged | 0.300 |

Seq01 exposes the defect directly: output gaps previously remained credited as
correct indefinitely. The new rule converts those intervals to lost without
increasing wrong-target duration. May and seq03 are unchanged. Seq04 metrics are
unchanged; 0.30 s of output already classified lost is now also explicitly
recorded as stale.

Inputs:

- seq01 source bag: `bags/source/official_flights/2026-06-19/seq01_clean_four_person/full_pipeline/2026-06-19__12-45-45__video__2026-06-19__official__seq01__clean_four_person__yolov8s_bytetrack_tim_mars`
- May reference bag: `bags/reference/tim_good/2026-05-14__hard_reentry__bytetrack__tim_mars_v4_margin010__target_1`
- seq03 source bag: `bags/source/official_flights/2026-06-19/seq03_crossing_ambiguity/full_pipeline/2026-06-19__12-57-48__video__2026-06-19__official__seq03__four_person_crossing_ambiguity__yolov8s_bytetrack_tim_mars`
- seq04 source bag: `bags/source/official_flights/2026-06-19/seq04_occlusion_no_exit/full_pipeline/2026-06-19__13-01-36__video__2026-06-19__official__seq04__four_person_occlusion_no_exit__yolov8s_bytetrack_tim_mars`
- annotations: `docs/data/annotations/june_hard_sequences/seq01_bytetrack.csv`,
  `docs/data/annotations/may_hard_reentry/bytetrack_hard_reentry.csv`,
  `docs/data/annotations/june_hard_sequences/seq03_bytetrack.csv`, and
  `docs/data/annotations/june_hard_sequences/seq04_bytetrack.csv`.

The comparison completed with return code zero for all eight evaluator runs and
left the committed repository clean.
