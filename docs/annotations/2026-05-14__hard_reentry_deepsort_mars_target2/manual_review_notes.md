# DeepSORT MARS manual identity review

## Dataset

Dataset:

- `2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw`

DeepSORT bag reviewed:

- `artifacts/bags/eval_matrix/2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw__tracker_deepsort__tim_off__target_largest`

## Visual target definition

- Selected target: black-shirt person.
- Main distractor: checkered-shirt person.

## Existing OCSORT/TIM hard-crossing review

01: visible_target=yes, visual_decision=stay, correct_visual_id=1. The original selected target appears to remain the black-shirt person. TIM switches to the checkered-shirt person around the event, so the TIM switch is visually wrong. Raw/previous target remains closer to the correct visual target.

02: visible_target=yes, visual_decision=stay, correct_visual_id=96. The clip starts with TIM already on the wrong checkered-shirt person. The original selected target is the black-shirt person on the right and remains visible. TIM stays wrong through the event instead of returning to the black-shirt target.

03: visible_target=yes, visual_decision=stay, correct_visual_id=113. The original selected target is the black-shirt person. TIM is already on the wrong checkered-shirt person at the start and remains wrong through the event. The black-shirt target remains visible and is labelled trk 113 near the end of the clip.

04: visible_target=yes, visual_decision=switch, correct_visual_id=142. The clip starts with TIM still wrong on the checkered-shirt person. During the clip, TIM switches back to the original black-shirt target, now labelled ID 142. This switch is visually correct.

05: visible_target=yes, visual_decision=stay, correct_visual_id=161. The clip starts with TIM correctly on the black-shirt selected target. During the clip, the correct target changes to ID 161, while TIM switches away to the checkered-shirt person. This TIM switch is visually wrong.

06: visible_target=yes, visual_decision=switch, correct_visual_id=161. The clip starts with TIM wrong on the checkered-shirt person while the black-shirt selected target is visible nearby. TIM then switches back to the black-shirt target, labelled ID 161. This correction is visually correct.

## DeepSORT MARS manual review

01: ID 1 is the checkered-shirt distractor. ID 2 is the selected black-shirt target.

02: ID 2 remains the selected black-shirt target. ID 1 remains the checkered-shirt distractor.

03: At the start around 87.21 s, ID 2 is the selected black-shirt target and ID 1 is the checkered distractor. By around 105.99 s, they have switched: ID 1 is now the selected black-shirt target and ID 2 is the checkered distractor.

04: At around 104.67 s, black-shirt target is ID 1 and checkered distractor is ID 2. By around 112.81 s, it switches again: black-shirt target becomes ID 2 and checkered distractor becomes ID 1.

05: At around 110.14 s, black-shirt target is ID 1 and checkered distractor is ID 2. Around 113.41 s, the IDs switch: black-shirt target becomes ID 2 and checkered distractor becomes ID 1. It then stays that way through around 118.86 s.

06: Black-shirt target is ID 2 throughout. At first the checkered distractor has no stable ID, then it receives ID 1 and stays ID 1 until the end.

## Interpretation

DeepSORT MARS is not perfectly identity-stable on this hard crossing sequence. The selected black-shirt target is mostly ID 2, but DeepSORT swaps IDs with the checkered-shirt distractor during the hardest crossing and re-entry interval.

Therefore, the OCSORT annotation cannot be reused for DeepSORT. DeepSORT requires its own manual target-ID annotation.
