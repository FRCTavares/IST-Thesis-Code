# Issue #58 — Physical-v2 development architecture matrix

## Status

Development-only evidence on `dev_may_hard_reentry`.

This matrix is not held-out evidence and must not be used as the final Issue #58
generalisation result.

All cells use the same physical-target v2 reference and the same evaluated
duration of `67.864909774 s`.

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
Target-ReID. Issue #58 still requires the remaining architecture cells and
held-out physical-reference evaluation before any final comparative claim is
frozen.
