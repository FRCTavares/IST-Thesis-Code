# Manual Review Notes - Hard Re-entry OC-SORT TIM-on Target 1

Bag:

artifacts/bags/eval_matrix/2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw__tracker_ocsort__tim_on__target_1

Videos:

reports/videos/2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw__tracker_ocsort__tim_on__target_1/raw_target_overlay.mp4

reports/videos/2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw__tracker_ocsort__tim_on__target_1/tim_target_memory_overlay.mp4

## Manual observations

- From 4.81 to 49.61 s, the selected person is ID 1 and the distractor is ID 2. TIM is correct.
- Around 49.61 s, ID 1 crosses in front of ID 2 and TIM briefly stops or changes for less than one second.
- Around 50.01 s, TIM returns to ID 1, which is correct.
- Around 59.40 s, ID 1 is still the selected target and crosses behind ID 2. TIM remains correct.
- Around 69.32 s, the selected target changes to ID 96 after a fake crossing, but TIM switches to the distractor, now ID 1. This is a wrong-target interval.
- Around 101.20 s, TIM switches from the distractor ID 1 back to the selected target, now ID 142. This is a correct recovery.
- Around 110.84 s, TIM switches again from ID 142 to ID 1, which is the distractor. The selected target is now ID 161. This is another wrong-target interval.
- Around 116.31 s, TIM switches to ID 161, which is the selected target. The distractor later becomes ID 173.

## Interpretation

This bag is important because TIM remains mostly valid but is not always correct. It exposes the difference between target validity and selected-person correctness.

The main failure mode is safe reacquisition under close crossings: TIM can switch to a persistent distractor when the selected target changes tracker ID.

This supports the need for safer appearance-gated reacquisition or candidate hypothesis logic.
