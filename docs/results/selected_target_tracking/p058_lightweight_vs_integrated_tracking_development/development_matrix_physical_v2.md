# Issue #58 — Physical-v2 development architecture matrix

## Status

Development-only evidence currently covers `dev_may_hard_reentry`, the
frozen June Seq03 crossing-ambiguity validation, and the frozen June Seq04
occlusion/physical-absence validation.

These results are not held-out evidence and must not be used as the final Issue
#58 generalisation result. No thresholds or architecture settings were retuned
after observing the Seq03 or Seq04 physical-v2 outcomes.

The May matrix uses an evaluated duration of `67.864909774 s`. The Seq03 matrix
uses an evaluated duration of `83.867251154 s`, including a common
`0.100453371 s` physical-reference gap that is excluded from the correct /
wrong / lost identity buckets. Seq04 uses an evaluated duration of
`86.500955726 s`, including `72.500041772 s` of physically scored target-present
time, `13.900030159 s` of explicit physical target absence, and a common
`0.100883795 s` physical-reference gap.

## Architecture matrix

| Architecture | Correct target | Wrong person | Identity unresolved | Lost / suppressed |
| --- | ---: | ---: | ---: | ---: |
| ByteTrack raw | 38.530771128 s (56.78%) | 7.595021755 s (11.19%) | 0 s | 21.739116891 s (32.03%) |
| Simple Target-ReID, threshold 0.90 | 23.152773497 s (34.12%) | 0 s (0.00%) | 0 s | 44.712136277 s (65.88%) |
| ByteTrack + canonical TIM-MARS | 62.594003990 s (92.23%) | 0.033394241 s (0.05%) | 0 s | 5.237511543 s (7.72%) |
| DeepSORT raw | 51.356019855 s (75.67%) | 0.033394241 s (0.05%) | 0 s | 16.475495678 s (24.28%) |

Target-absence duration and target-absence-with-output duration are both zero for
this development sequence, so this sequence alone does not test open-set
target-absence publication safety.

## Key development deltas

Relative to raw ByteTrack, canonical TIM-MARS:

- increases correct-target output by `24.063232862 s`;
- reduces wrong-person output by `7.561627514 s`;
- reduces lost/suppressed duration by `16.501605348 s`.

Relative to integrated DeepSORT, canonical TIM-MARS:

- has the same physical-v2 wrong-person duration to evaluator precision:
  `0.033394241 s`;
- increases correct-target output by `11.237984135 s`;
- reduces lost/suppressed duration by `11.237984135 s`.

Relative to the calibrated simple Target-ReID baseline, canonical TIM-MARS:

- accepts `0.033394241 s` more wrong-person output;
- increases correct-target output by `39.441230493 s`;
- reduces lost/suppressed duration by `39.474624734 s`.

The simple Target-ReID baseline therefore demonstrates that a fixed appearance
threshold can eliminate wrong-person publication on this sequence, but only at
a major availability cost. The TIM-MARS result shows substantially higher
controller-facing availability while maintaining wrong-person duration at the
same measured level as DeepSORT.

## Provenance

Physical reference:

- file:
  `docs/data/physical_target_references/dev_may_hard_reentry.json`
- SHA-256:
  `45d620d97e6488fb174e4ce66c49403079e084bc577d6d621c8365265f0d238c`

Appearance model:

- file: `models/reid/mars-small128.pb`
- SHA-256:
  `e96f3cc09dbce76e2f6aeff09c8f2502916b4745f21e27911ee50d102a4a75f1`

ByteTrack raw:

- controller-facing topic: `/target`
- preserved in the same deterministic replay used for the canonical TIM-MARS cell:
  `bags/replay/p021_motion_stage_a_ab92139b/baseline/may_hard_reentry`
- this replay yields `38.530771128 / 7.595021755 / 21.739116891 s` correct / wrong / lost under physical-v2
- the original historical source-bag `/target` stream gives a slightly different selection-timing result and is intentionally not used in this controlled matrix

Canonical TIM-MARS:

- config:
  `ros2_ws/src/thesis_bringup/config/tim_mars_canonical.yaml`
- SHA-256:
  `e9dc78c8e60d5c108e608a449803832738e39867ddd708a4d6855bbb782fe931`
- deterministic replay:
  `bags/replay/p021_motion_stage_a_ab92139b/baseline/may_hard_reentry`
- selected tracker ID: `1`
- image topic: `/camera/image_raw`
- track topic: `/tracks`
- image geometry: `640 x 640`

DeepSORT:

- config:
  `ros2_ws/src/thesis_bringup/config/tracker_deepsort.yaml`
- SHA-256:
  `d586e2e04c283313606cb366b64c0e7bad19692207f185d7dd9b89c89e33efb0`
- deterministic tracker replay:
  `bags/replay/p058_lightweight_vs_integrated_6231fdc1_2026_08_08/tracker_bags/dev_may_hard_reentry/deepsort`
- source:
  `bags/reference/tim_good/2026-05-14__hard_reentry__bytetrack__tim_mars_v4_margin010__target_1`
- replay command uses `tracker_deepsort.yaml` and the same
  `mars-small128.pb` appearance model.

Simple Target-ReID:

- calibrated threshold: `0.90`
- calibration contract:
  `docs/results/selected_target_tracking/p058_lightweight_vs_integrated_tracking_development/target_reid_baseline_physical_v2.md`

## Additional frozen development validation: June Seq03 crossing

June Seq03 uses the newly promoted physical-v2 reference for the exact canonical
raw capture `2026-06-19__12-55-58`. The detector evidence was regenerated once
from that raw capture and frozen before tracker fan-out. The common input contains
exactly 1,931 source images and 1,931 YOLOv8s detection messages with one-to-one
equality of all image and detection header timestamps.

ByteTrack, SORT, and DeepSORT were then regenerated deterministically from that
same image/detection stream. Their selected bootstrap tracks were independently
checked against the physical target and passed with initial physical-target IoU
of `0.924555`, `0.865869`, and `0.875631`, respectively. DeepSORT consumed the
same-timestamp source image on all 1,931 frames (`0 ms` image age), so its result
is not attributable to a stale appearance-image stream.

The simple Target-ReID threshold remained frozen at `0.90` from May development
calibration. Canonical TIM-MARS also remained unchanged. No Seq03 tuning was
performed.

| Architecture | Correct target | Wrong person | Identity unresolved | Lost / suppressed |
| --- | ---: | ---: | ---: | ---: |
| ByteTrack raw | 33.831624313 s (40.34%) | 0.100206111 s (0.12%) | 0 s | 49.834967359 s (59.42%) |
| SORT raw | 27.432422908 s (32.71%) | 0 s (0.00%) | 0 s | 56.334374875 s (67.17%) |
| Simple Target-ReID, threshold 0.90 | 13.962779010 s (16.65%) | 0 s (0.00%) | 0 s | 69.804018773 s (83.23%) |
| ByteTrack + canonical TIM-MARS | 22.532686264 s (26.87%) | 0 s (0.00%) | 0 s | 61.234111519 s (73.01%) |
| DeepSORT raw | 27.547623858 s (32.85%) | 35.350991550 s (42.15%) | 0 s | 20.868182375 s (24.88%) |

All five cells reconcile exactly over `83.867251154 s`. Each has
`0.100453371 s` reference-gap duration and zero target-absent duration, so Seq03
does not test open-set target-absence publication safety.

Relative to raw ByteTrack, canonical TIM-MARS on Seq03:

- reduces wrong-person output by `0.100206111 s`, to zero;
- reduces correct-target output by `11.298938049 s`;
- increases lost/suppressed duration by `11.399144160 s`.

Relative to the frozen simple Target-ReID baseline, canonical TIM-MARS:

- has the same zero measured wrong-person duration;
- increases correct-target output by `8.569907254 s`;
- reduces lost/suppressed duration by `8.569907254 s`.

Relative to integrated DeepSORT, canonical TIM-MARS:

- reduces wrong-person output by `35.350991550 s`;
- has `5.014937594 s` less correct-target output;
- increases lost/suppressed duration by `40.365929144 s`.

The Seq03 result therefore does not support a blanket availability advantage for
TIM-MARS over raw ByteTrack. Instead, it demonstrates the intended asymmetric
safety trade-off: TIM-MARS suppresses the small residual ByteTrack wrong-person
publication at a material availability cost, while retaining substantially more
correct-target availability than the conservative fixed-template Target-ReID
baseline. On this controlled crossing sequence, integrated DeepSORT exhibits a
large physical wrong-person failure despite identical detector evidence,
same-capture imagery, correct target bootstrap, and zero appearance-image age.

Seq03 provenance:

- physical reference:
  `docs/data/physical_target_references/seq03_crossing.json`
  (SHA-256 `9e03fedc8076638bfb300cf131672aef38927252c09ac48174fa79bd2aa17f71`);
- frozen common image/detection input SHA-256:
  `fe5dc3b01e8bf31fee5a73aacffa0cf91d1bc7c7151130b83b3600451cd449b2`;
- deterministic ByteTrack replay SHA-256:
  `619a99183181826dfaa278691db0c5f7523b5b32b34b18fd2dc574b392717c77`;
- deterministic SORT replay SHA-256:
  `c2eaaa4c6bbb1816909adcdb96b8649e23d2fecd371eda19538e4a7d15115dc7`;
- deterministic DeepSORT replay SHA-256:
  `bb65f7e160215d0ff1bfff682680a4013d24a3a387d32c335dba786f832d3a73`;
- frozen Target-ReID replay SHA-256:
  `e0bca9c5aee11f91b04c14399633632b8c10071a80b33f7abee7c0879a7f8681`;
- canonical TIM-MARS replay SHA-256:
  `69f0260c7a53604047258020b5eb5c5bb7363c6bb767dd6cbe7e4972e009ef59`;
- canonical TIM-MARS config SHA-256:
  `e9dc78c8e60d5c108e608a449803832738e39867ddd708a4d6855bbb782fe931`;
- MARS model SHA-256:
  `e96f3cc09dbce76e2f6aeff09c8f2502916b4745f21e27911ee50d102a4a75f1`.

## Additional frozen development validation: June Seq04 physical absence

June Seq04 adds the first Issue #58 development comparison with explicit,
human-reviewed physical target absence. The frozen physical-v2 reference covers
the exact canonical `2026-06-19__12-59-53` capture with 2,047 per-frame samples:
1,717 `present_scored` frames and 330 explicit `absent` frames. The target is
absent during frames 1382--1571 and 1682--1821.

The common detector evidence was frozen before architecture comparison. Raw
ByteTrack, SORT, DeepSORT, the simple Target-ReID baseline, and canonical
ByteTrack + TIM-MARS were evaluated against the same identity-independent
physical-v2 reference. The Target-ReID acceptance threshold remained frozen at
`0.90`; canonical TIM-MARS was unchanged. No Seq04 tuning was performed.

| Architecture                       |          Correct target |            Wrong person | Identity unresolved |       Lost / suppressed | Target absent with output |
| ---------------------------------- | ----------------------: | ----------------------: | ------------------: | ----------------------: | ------------------------: |
| ByteTrack raw                      | 26.567002669 s (36.64%) | 37.500838682 s (51.73%) |                 0 s |   8.432200421 s (11.63%) | 13.100381659 s |
| SORT raw                           | 14.833643862 s (20.46%) |             0 s (0.00%) |                 0 s | 57.666397910 s (79.54%) | 0 s |
| Simple Target-ReID, threshold 0.90 |   1.166866685 s (1.61%) |             0 s (0.00%) |                 0 s | 71.333175087 s (98.39%) | 0 s |
| ByteTrack + canonical TIM-MARS     | 35.068442774 s (48.37%) |             0 s (0.00%) |                 0 s | 37.431598998 s (51.63%) | 0 s |
| DeepSORT raw                       | 36.833999479 s (50.81%) |             0 s (0.00%) |                 0 s | 35.666042293 s (49.19%) | 0 s |

Percentages in the correct / wrong / lost columns use the common
`72.500041772 s` physically scored target-present duration as denominator.
Target-absent-with-output is reported separately over the
`13.900030159 s` explicit absence duration.

The Seq04 result shows a different trade-off from Seq03. Relative to raw
ByteTrack, canonical TIM-MARS:

- eliminates `37.500838682 s` of wrong-person output;
- eliminates all `13.100381659 s` of target-absent false publication;
- increases correct-target output by `8.501440105 s`;
- increases lost/suppressed duration by `28.999398577 s`.

Relative to the frozen simple Target-ReID baseline, canonical TIM-MARS:

- preserves the same zero wrong-person and zero target-absence-output result;
- increases correct-target output by `33.901576089 s`;
- reduces lost/suppressed duration by `33.901576089 s`.

Relative to integrated DeepSORT, canonical TIM-MARS:

- has the same zero measured wrong-person and zero target-absence-output duration;
- has `1.765556705 s` less correct-target output;
- has `1.765556705 s` more lost/suppressed duration.

Therefore Seq04 does **not** support an availability claim that TIM-MARS
outperforms DeepSORT. DeepSORT has the highest correct-target duration among the
zero-wrong architectures on this sequence. The stronger controller-facing result
is instead the change relative to the underlying ByteTrack tracker: TIM-MARS
converts prolonged wrong-person publication and open-set false publication into
conservative suppression while retaining substantial correct-target
availability.

### Physical-return recovery

Seq04 contains two explicit physical-return opportunities. Recovery was evaluated
using the same physical-v2 Stage-A identity attribution and output-freshness
contract as the duration evaluation. A stable recovery follows the existing
Issue #26 convention of requiring `0.25 s` of continuously correct output; this
stability duration is only a persistence convention and does not redefine
physical-v2 correctness.

The physical target returns at:

- return 1: `66.000222738 s`, with the opportunity ending at the next physical
  absence at `70.866680698 s`;
- return 2: `76.666741991 s`, with observation ending at the sequence boundary
  `86.500955726 s`.

| Architecture | Return 1 | Return 2 | Stable successes |
|---|---|---|---:|
| ByteTrack raw | failure before next absence; no correct output; `4.166819295 s` wrong-person before cutoff | no correct recovery observed before sequence end; right-censored; `2.699997183 s` wrong-person before cutoff | 0/2 |
| SORT raw | failure before next absence; no correct output | no correct recovery observed before sequence end; right-censored | 0/2 |
| DeepSORT raw | failure before next absence; no correct output | no correct recovery observed before sequence end; right-censored | 0/2 |
| Simple Target-ReID, threshold 0.90 | failure before next absence; no correct output | no correct recovery observed before sequence end; right-censored | 0/2 |
| ByteTrack + canonical TIM-MARS | failure before next absence; no correct output | no correct recovery observed before sequence end; right-censored | 0/2 |

No architecture produced even a transient physically correct output after either
return, so there is no finite first-correct or stable-reacquisition latency to
report. In particular, the second opportunity must not be labelled a definitive
failure: observation terminates at the sequence boundary and is therefore
right-censored.

The recovery comparison also exposes the asymmetric safety behavior. ByteTrack
continues publishing a physically wrong person for substantial portions of both
post-return windows. SORT, DeepSORT, Target-ReID and TIM-MARS instead remain
LOST/suppressed for the physically scored intervals. Thus Seq04 provides useful
open-set rejection evidence, but it provides no positive reacquisition-success
evidence for any architecture.

Seq04 provenance:

- physical reference:
  `docs/data/physical_target_references/seq04_occlusion_no_exit.json`
  (SHA-256 `a99fb5ea98c3f1442c6a90851235f51d773e509ea7be5e7c058bad8d2a0c886b`);
- frozen common detector/input lineage:
  `bags/replay/p058_seq04_physical_v2_common_input_2026_08_28`;
- canonical ByteTrack + TIM-MARS replay:
  `bags/replay/p058_seq04_physical_v2_tim_mars_2026_08_28`;
- SORT physical-target derivative:
  `bags/replay/p058_seq04_physical_v2_sort_fixed_id5_2026_08_29`;
- DeepSORT physical-target derivative:
  `bags/replay/p058_seq04_physical_v2_deepsort_fixed_id5_2026_08_29`;
- frozen Target-ReID replay:
  `bags/replay/p058_seq04_physical_v2_target_reid_2026_08_29`;
- Target-ReID replay MCAP SHA-256:
  `073e8bc0e40102ea3b4f48769e9a26d549454ac078cf53cf8d81719868529a23`;
- Target-ReID provenance sidecar SHA-256:
  `df95d488502ed9856e458374a798024c80ab3911f5a9e83ddf2a83d25d098c13`;
- canonical TIM-MARS config SHA-256:
  `e9dc78c8e60d5c108e608a449803832738e39867ddd708a4d6855bbb782fe931`;
- MARS model SHA-256:
  `e96f3cc09dbce76e2f6aeff09c8f2502916b4745f21e27911ee50d102a4a75f1`.

## Minimal appearance-free tracker arm: SORT

The frozen Issue #58 SORT calibration search contained 29 configurations,
including the canonical baseline and one-dimensional perturbations frozen
before physical-v2 outcome review. Re-evaluating those same 29 existing
SORT+TIM replay outputs against the corrected May physical-person reference
does not produce a promotable configuration.

Raw SORT under physical-v2 gives:

- correct-target output: `29.398778016 s`;
- wrong-person output: `0.049512077 s`;
- lost/suppressed: `38.416619681 s`;
- target-absent-with-output: `0 s`.

The pre-existing asymmetric safety gate therefore permits at most
`0.099512077 s` wrong-person output and `0.05 s`
target-absent-with-output. None of the 29 frozen SORT+TIM configurations
passes that gate. The lowest-wrong candidate is
`confirmation_time_higher_3`, with `0.694389678 s` wrong-person output,
which exceeds the allowed wrong-person ceiling by `0.594877601 s`.

Accordingly, SORT+TIM is retained as a development negative result rather
than promoted as an architecture cell. This is not a missing experiment:
the minimal appearance-free tracker arm was evaluated using the frozen
configuration search and failed the controller-safety promotion criterion.

## Interpretation boundary

This matrix supports a development-sequence comparison only.

It does not establish that TIM-MARS generally outperforms DeepSORT or simple
Target-ReID. In particular, DeepSORT has slightly higher zero-wrong
correct-target availability than TIM-MARS on Seq04, while Seq03 shows a severe
DeepSORT wrong-person failure. The sequence-specific differences reinforce the
need for the held-out comparison rather than supporting a universal architecture
ranking.

Seq04 now supplies the previously missing development-only open-set
target-absence evidence and physical-return recovery accounting. It does not
supply positive reacquisition-success evidence: none of the five evaluated
architectures physically reacquired the selected target after either Seq04
return.

Issue #58 still requires held-out physical-reference evaluation before any
final comparative claim is frozen. The canonical embedded-cost and timing
development evidence is complete below.

## Canonical embedded-cost development evidence — 31 Aug 2026

This section records the retained development-only onboard cost comparison for
Issue #58. It is not held-out identity evidence and does not replace the
H01--H03 physical-v2 evaluation required for final Issue #58 closure.

### Experimental contract

- Retained matrix:
  `ros2_ws/log/p058_retained_cost_matrix_92d123e3_20260831_130450`
- Git commit: `92d123e3d8e45d6fc3a8c386194d6f0ca85fc181`
- Working tree at execution: clean
- Platform: Raspberry Pi 5, `aarch64`, kernel `6.8.0-1063-raspi`
- ROS: Jazzy
- HailoRT: `4.23.0`
- Detector: direct/in-process Hailo YOLOv8s
- Detector HEF SHA-256:
  `69540ff855740371d229f4caca1ab908635a72fec55fdc1541e73f2fc17ec43b`
- TIM-MARS appearance model: CPU MARS `mars-small128.pb`
- MARS SHA-256:
  `e96f3cc09dbce76e2f6aeff09c8f2502916b4745f21e27911ee50d102a4a75f1`
- Source: June Seq03 four-person crossing/ambiguity raw image bag
- Playback rate: `1.0x`
- Repetitions: three per architecture
- Execution order: rotated across repetitions
- Inter-cell cooldown: 20 s
- Process-group CPU/RSS sampling: 1 s
- Hardware-health sampling: 1 s
- Retained cells: 9/9 successful
- Throttling: zero non-zero throttling samples in every retained cell
- Hardware sampler errors: zero in every retained cell

Process CPU percentage is Linux process CPU usage and can exceed 100% because a
process can consume more than one CPU core.

The primary *architecture-specific* comparison excludes the detector because
the same YOLOv8s detector is common to all three cells. For ByteTrack + TIM-MARS,
architecture CPU and RSS are the sum of the ByteTrack tracker process and the
separate TIM-MARS process. DeepSORT's integrated appearance extraction is
already contained inside the DeepSORT tracker process.

### Retained resource result

| Architecture | Architecture CPU [%] | Mean architecture RSS [MiB] | Full-system CPU [%] | Mean full-system RSS [MiB] | Mean SoC temp. [C] | Highest observed temp. [C] |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ByteTrack raw | 227.2 +/- 0.6 | 134.6 +/- 0.2 | 254.5 +/- 0.6 | 353.1 +/- 0.3 | 60.8 +/- 0.6 | 63.1 |
| ByteTrack + TIM-MARS | 243.3 +/- 10.3 | 919.6 +/- 7.8 | 267.8 +/- 11.9 | 1138.6 +/- 7.9 | 63.1 +/- 0.7 | 67.0 |
| DeepSORT raw | 267.0 +/- 3.0 | 767.2 +/- 1.9 | 291.9 +/- 3.2 | 985.5 +/- 1.8 | 65.0 +/- 0.4 | 69.2 |

Values reported as `mean +/- sample standard deviation` are calculated across
the three retained run-level means.

Relative to DeepSORT raw, ByteTrack + TIM-MARS used approximately `8.9%` less
architecture-specific CPU on this controlled development workload, while using
approximately `19.9%` more mean architecture-specific RSS. When the common
detector is included, the corresponding differences are approximately `8.3%`
less full-perception CPU and `15.5%` more mean full-perception RSS.

Raw ByteTrack remains substantially lighter than either appearance-enabled
architecture, but the frozen May/Seq03/Seq04 physical-v2 development evidence
already shows why raw lightweight tracking alone is not an adequate selected-
person identity solution.

DeepSORT also ran hotter than the other two architectures in this matrix, but
none of the nine retained runs produced a non-zero throttling sample. Therefore
the CPU comparison is not explained by observed thermal throttling.

### Retained timing and causal-throughput result

The nine retained bags were analysed with the canonical schema-v4 offline timing
analyser using the same active-window definition for every architecture:
`pub_dt_ms <= 100 ms`. Values reported as `mean +/- sample standard deviation`
below are calculated across the three retained run-level values.

| Architecture | Tracker timing [Hz] | `track_ms` p50 [ms] | `track_ms` p95 [ms] | `track_ms` p99 [ms] | Validated-target timing [Hz] | Validated-target p95 [ms] | Active detector-to-tracker coverage [%] |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ByteTrack raw | 18.612 +/- 0.403 | 1.201 +/- 0.013 | 6.218 +/- 0.362 | 11.732 +/- 0.850 | NA | NA | 100.000 +/- 0.000 |
| ByteTrack + TIM-MARS | 18.100 +/- 0.351 | 2.019 +/- 0.380 | 22.841 +/- 2.001 | 30.487 +/- 3.321 | 17.561 +/- 0.549 | 181.785 +/- 15.445 | 99.963 +/- 0.064 |
| DeepSORT raw | 9.796 +/- 0.180 | 79.100 +/- 7.181 | 150.816 +/- 3.433 | 167.987 +/- 6.063 | NA | NA | 68.154 +/- 1.087 |

The ByteTrack + TIM-MARS controller-facing validated-target path exceeds the
preferred `15 Hz` rate in all three retained runs and its validated-target p95
latency remains at or below the thesis `200 ms` target in all three runs. The
three run-level validated-target p95 values are `172.949 ms`, `172.788 ms`, and
`199.619 ms`.

DeepSORT's integrated appearance tracker is materially slower on the same
controlled workload: its tracker stage averages `9.796 Hz`, versus
`18.100 Hz` for the ByteTrack tracker when TIM-MARS is enabled. Its tracker p95
compute time is `150.816 +/- 3.433 ms`, compared with
`22.841 +/- 2.001 ms` for the ByteTrack tracker in the TIM-MARS architecture.
Only `68.154 +/- 1.087%` of active detector frame IDs reach the DeepSORT tracker
timing stream, whereas ByteTrack raw and ByteTrack + TIM-MARS retain essentially
complete active detector-to-tracker causal coverage.

This does not turn the raw DeepSORT cell into a controller-facing latency
measurement. DeepSORT raw intentionally has no TIM-MARS selected-target
authority, so its reported rate and latency describe the integrated tracker
stage. Conversely, `e2e_validated_target_ms` for ByteTrack + TIM-MARS is a
controller-facing selected-target authority measurement.

Together with the retained resource evidence, this establishes the development
compute trade-off: raw ByteTrack is cheapest but is insufficient as a
selected-person identity solution in the frozen physical-v2 development
evidence; adding TIM-MARS preserves a controller-usable rate and bounded p95
latency while strongly improving the selected-target safety behaviour; and
integrated DeepSORT is slower at the tracker stage and does not eliminate the
severe Seq03 wrong-person failure. These are development-sequence findings, not
a held-out universal architecture ranking.

Corrected aggregate analysis provenance:

- timing schema: `4`;
- active-gap threshold: `100 ms`;
- aggregate JSON SHA-256:
  `faf56e6c76f742ef37d9f72245d5081f970d21c755f953c7d6bafce04889ab73`;
- aggregate Markdown SHA-256:
  `450dbbc99c2ba49856b9c793c4a46e94158371789cd5ae5d13b9563c92e48851`;
- analysis was derived from the existing nine retained bags; no replay or
  measurement was repeated for the latency-aggregation correction.
### Current Issue #58 status

The development architecture evidence now contains the frozen
safety/availability comparisons plus the retained canonical onboard resource,
timing, causal-coverage, and controller-rate comparison. No additional Issue #58
development architecture experiment is currently required. The remaining final
evidence gate is the held-out H01--H03 physical-v2 evaluation under Issue #27.
Issue #58 therefore remains open, while the active implementation critical path
advances to Issue #74.
