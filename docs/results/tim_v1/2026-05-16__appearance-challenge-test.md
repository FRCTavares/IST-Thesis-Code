# Appearance Challenge Gate Test

Bag:

2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw

Run:

OC-SORT TIM-on target 1, challenge-enabled replay.

## Result

The experimental appearance challenge gate did not activate.

Observed:

- appearance_challenge_uncertain: 0 rows
- appearance_raw nonzero rows: 1423 / 2804
- appearance_gate_passed rows: 11

The highest appearance_raw rows were mostly associated with the currently locked target ID, not with a challenger.

## Interpretation

The appearance challenge gate was structurally added, but this configuration did not reduce wrong-target risk because it did not trigger on the observed replay.

The likely reason is that the current appearance memory often agrees with the currently locked ID. During wrong-target intervals, this can happen if TIM has already learned or reinforced the distractor while in LOCKED state.

## Next improvement

The next improvement should prevent appearance memory drift after risky ID switches.

Candidate rule:

- after any ID change or REACQUIRED transition, freeze appearance memory updates for N frames,
- only resume appearance updates after the target has remained stable and unambiguous.

This should reduce the risk of learning the distractor after a wrong reacquisition.
