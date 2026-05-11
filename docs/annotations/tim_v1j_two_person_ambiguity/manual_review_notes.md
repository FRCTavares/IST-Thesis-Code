# Manual Review Notes - TIM-V1J Two-Person Ambiguity

Bag:

artifacts/bags/live_camera/2026-05-11__10-44-58__video__tim_v1j_two_person_ambiguity

Reports:

reports/tim_v0/2026-05-11__10-44-58__video__tim_v1j_two_person_ambiguity
reports/tim_v1_appearance/2026-05-11__10-44-58__video__tim_v1j_two_person_ambiguity

## Raw /target review

| Interval [s] | Manual label | Notes |
|---:|---|---|
| 5.26-39.80 | correct | Selected target is correct. |
| 39.80-40.87 | lost | Target person ID switched to 4 and raw target stopped targeting the selected person. |
| 40.87-62.28 | lost | Raw target did not reacquire the original selected person. |
| 62.28-62.75 | lost | Target left frame and ID switched again. |
| 62.75-end | lost_or_wrong_uncertain | No correct target selected. Needs exact lost vs wrong classification if used for final table. |

## TIM /target_memory review

| Interval [s] | Manual label | Notes |
|---:|---|---|
| 5.26-39.80 | correct | TIM target is correct. |
| 39.80-40.87 | correct | TIM still targets the selected person while transitioning, although tracker ID changes from 1 to 4. |
| 40.87-62.28 | correct | TIM reacquires the original selected person under a different tracker ID. |
| 62.28-62.75 | lost | Target leaves frame, TIM loses target. |
| 62.75-end | failed | TIM switches to ID 8 and does not recover the original selected person. Needs exact lost vs wrong classification if used for final table. |

## Main interpretation

Raw /target fails at the first tracker ID switch.

TIM /target_memory survives the first ID switch and continues following the correct person, even though the tracker ID changes.

TIM later fails after a harder disappearance/re-entry event, switching to ID 8 and not recovering the original selected person.

This is useful thesis evidence because it shows both an improvement case and a remaining limitation.
