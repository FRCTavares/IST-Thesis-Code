# Manual Review Notes - Hard Re-entry OC-SORT TIM-on Target 1

Bag:

artifacts/bags/eval_matrix/2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw__tracker_ocsort__tim_on__target_1

Videos:

reports/videos/2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw__tracker_ocsort__tim_on__target_1/raw_target_overlay.mp4

reports/videos/2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw__tracker_ocsort__tim_on__target_1/tim_target_memory_overlay.mp4

## Manual interval review

- 0.00-5.00 s: selected person is visible as ID 1, but no target has been selected yet.
- 5.00-68.00 s: selected person is ID 1 and TIM follows ID 1 correctly.
- 68.00-99.00 s: selected person changes to ID 96 and then ID 113, but TIM keeps following ID 1, which is now the distractor. This is a wrong-target interval.
- 99.00-109.00 s: selected person is ID 142 and TIM follows ID 142 correctly.
- 109.00-110.00 s: transition interval between IDs 142 and 161.
- 110.00-115.00 s: selected person is ID 161, but TIM follows distractor ID 1. This is a wrong-target interval.
- 115.00-116.00 s: transition interval before recovery.
- 116.00-end: selected person is ID 161 and TIM follows ID 161 correctly. The distractor later becomes ID 173.

## Interpretation

This bag clearly separates target validity from target correctness.

TIM remains mostly valid, but it still follows the wrong person during close crossing and ID-change intervals. The main wrong-target intervals are 68.00-99.00 s and 110.00-115.00 s.

The failure mode is that the persistent distractor keeps strong geometric continuity, while the selected person changes tracker ID.
