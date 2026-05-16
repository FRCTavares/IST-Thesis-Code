# Appearance Update Cooldown Test

Bag:

2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw

Run:

OC-SORT TIM-on target 1 with TIM_APPEARANCE_UPDATE_COOLDOWN_FRAMES=30.

## Result

The appearance update cooldown activated.

Observed from /target_memory/status and analyser export:

- appearance_update_cooldown_remaining was present.
- max cooldown value: 29
- nonzero cooldown rows: 179
- cooldown column count: 946 rows

Validity comparison must not be treated as final correctness because replay IDs changed between runs. The cooldown feature is therefore validated as a mechanism, but its effect on wrong-target ratio still requires annotation on the exact cooldown eval bag.

## Interpretation

The cooldown prevents immediate appearance memory updates after risky ID switches / reacquisition. This is intended to reduce the risk of learning the distractor after a wrong reacquisition.

Next step:

- freeze the cooldown eval bag,
- render overlays,
- annotate target correctness on that exact bag,
- compare wrong-target duration against the baseline eval bag.
