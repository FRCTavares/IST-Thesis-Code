# Manual review v2 corrected results, hard re-entry sequence

## Context

A clean visual review was performed on six switch events from the hard re-entry sequence using bag-rendered clips generated directly from the MCAP bag. These clips included:

- `/camera/image_raw`
- `/tracks`
- `/target`
- `/target_memory`

The rendered review clips used the following colour convention:

- green: TIM `/target_memory`
- red: raw `/target`
- yellow: raw and TIM overlap
- grey: other tracks

This replaced the earlier mixed review based on exported overlay videos and partial raw clips. The MCAP bag was treated as the timing source of truth.

## Reviewed switch events

| Event | Frame | Time [s] | Visual decision | Correct visual ID | Interpretation |
|---:|---:|---:|---|---:|---|
| 01 | 623 | 72.56 | stay | 1 | TIM switches wrongly to the checkered-shirt distractor. |
| 02 | 693 | 81.20 | stay | 96 | TIM is already wrong and stays on the checkered-shirt distractor. |
| 03 | 710 | 83.67 | stay | 113 | TIM is already wrong and stays on the checkered-shirt distractor. |
| 04 | 840 | 101.13 | switch | 142 | TIM switches correctly back to the black-shirt selected target. |
| 05 | 904 | 111.75 | stay | 161 | TIM starts correct, then switches wrongly to the checkered-shirt distractor. |
| 06 | 927 | 116.11 | switch | 161 | TIM switches correctly back to the black-shirt selected target. |

The reviewed visual target identity sequence is:

    1 -> 96 -> 113 -> 142 -> 161

## Files created

Clean manual review file:

    reports/tim_v2q_remaining_switch_inspection/manual_switch_review_v2_clean.csv

Corrected annotation:

    docs/annotations/2026-05-14__hard_reentry_ocsort_tim_on_target1/target_correctness_annotations_manual_review_v2.csv

## Bag-level raw vs TIM evaluation

Command:

    python3 tools/analysis/evaluate_tim_target_correctness.py \
      artifacts/bags/eval_matrix/2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw__tracker_ocsort__tim_on__target_1 \
      --annotations docs/annotations/2026-05-14__hard_reentry_ocsort_tim_on_target1/target_correctness_annotations_manual_review_v2.csv \
      --out-dir reports/tim_v2q_manual_review_v2_eval/raw_vs_tim \
      --step-s 0.05

Result:

| Stream | Correct [s] | Wrong [s] | Lost [s] | Correct ratio | Wrong ratio | Lost ratio |
|---|---:|---:|---:|---:|---:|---:|
| Raw `/target` | 66.450 | 39.600 | 22.000 | 0.519 | 0.309 | 0.172 |
| TIM `/target_memory` | 91.350 | 35.550 | 1.150 | 0.713 | 0.278 | 0.009 |

Compared with raw `/target`, TIM gives:

- +24.900 s correct target duration
- -4.050 s wrong target duration
- -20.850 s lost target duration

## TIM-V2Q timeline evaluation

The V2Q policies were evaluated as exported timelines against the same manual review v2 annotation.

| Case | Stream | Correct [s] | Wrong [s] | Lost [s] | Correct ratio | Wrong ratio | Lost ratio |
|---|---|---:|---:|---:|---:|---:|---:|
| Pure V2Q margin 0.08 | raw_selected | 89.790 | 35.991 | 0.000 | 0.714 | 0.286 | 0.000 |
| Pure V2Q margin 0.08 | v2q_selected | 107.991 | 17.790 | 0.000 | 0.859 | 0.141 | 0.000 |
| Stable V2Q best previous sweep | raw_selected | 89.790 | 35.991 | 0.000 | 0.714 | 0.286 | 0.000 |
| Stable V2Q best previous sweep | v2q_selected | 108.458 | 17.323 | 0.000 | 0.862 | 0.138 | 0.000 |

Compared with raw selected timeline:

- pure V2Q increases correct duration by 18.201 s and reduces wrong duration by 18.201 s
- stable V2Q increases correct duration by 18.668 s and reduces wrong duration by 18.668 s

Compared with pure V2Q, the stable V2Q policy gives a small additional improvement:

- +0.467 s correct duration
- -0.467 s wrong duration

## Interpretation

The manual review v2 correction changes the hard re-entry result into a coherent thesis-grade finding.

First, the bag-level TIM output is clearly better than raw `/target`. It greatly reduces lost-target duration and also reduces wrong-target duration.

Second, the offline TIM-V2Q policy produces a much stronger wrong-target reduction than the raw selected timeline. This supports the value of appearance-assisted identity transfer in the hard re-entry case.

Third, the stable V2Q policy is not a large breakthrough over pure V2Q on this sequence, but it is slightly better under the corrected annotation. This means the stabilisation logic is not harmful here, but the main gain comes from the MARS-assisted V2Q identity transfer itself.

## Thesis consequence

The key result is not simply that TIM keeps producing a target for longer. The stronger claim is:

    Under manually reviewed target-correctness annotations, TIM reduces lost-target duration, and the TIM-V2Q appearance-assisted timeline substantially reduces wrong-target duration during hard re-entry.

This supports the thesis direction:

- V0/TIM memory improves continuity and reduces target loss.
- V2Q appearance assistance improves identity correctness during difficult re-entry.
- Evaluation must report correct, wrong, and lost target duration separately.
