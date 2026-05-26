# Hard re-entry comparison: DeepSORT MARS vs OCSORT + TIM

## Dataset

Dataset:

- `2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw`

Main scenario:

- Two-person hard crossing and re-entry.
- Selected target: black-shirt person.
- Main distractor: checkered-shirt person.

## Compared methods

| Method | Tracker | Output stream | Annotation |
|---|---|---|---|
| Raw OCSORT | OCSORT | `/target` | OCSORT manual review v2 |
| OCSORT + TIM | OCSORT | `/target_memory` | OCSORT manual review v2 |
| Raw DeepSORT MARS | DeepSORT + MARS ReID | `/target` | DeepSORT manual v1 |

## Results

| Method | Correct duration [s] | Wrong duration [s] | Lost duration [s] | Correct ratio | Wrong ratio | Lost ratio |
|---|---:|---:|---:|---:|---:|---:|
| Raw OCSORT `/target` | 66.400 | 40.450 | 21.200 | 0.519 | 0.316 | 0.166 |
| OCSORT + TIM `/target_memory` | 91.350 | 35.550 | 1.150 | 0.713 | 0.278 | 0.009 |
| Raw DeepSORT MARS `/target` | 87.600 | 9.150 | 31.350 | 0.684 | 0.071 | 0.245 |

## Interpretation

DeepSORT MARS is not perfectly identity-stable on the hard re-entry sequence, but it is much safer than OCSORT + TIM in terms of wrong-target duration.

OCSORT + TIM achieves the highest correct ratio in this comparison, but it still produces a high wrong-target ratio. This is not acceptable for selected-target following, because wrong target is worse than no target.

The main requirement for TIM Final is therefore not simply to increase valid output duration. The priority is to reduce wrong-target duration while keeping correct target duration close to DeepSORT MARS.

## Thesis implication

This comparison supports the final direction:

- DeepSORT MARS is a strong appearance-based baseline.
- It is heavier and slower, but safer against wrong target output.
- TIM Final should aim to approach DeepSORT-level selected-target correctness using a lightweight selected-target memory mechanism rather than full multi-object ReID.

The key target for TIM Final is:

- preserve or improve the 0.713 correct ratio of OCSORT + TIM,
- reduce the 0.278 wrong ratio towards the DeepSORT MARS value of 0.071,
- keep latency and runtime cost closer to OCSORT/TIM than to DeepSORT MARS.
