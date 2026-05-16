# Appearance Cooldown Correctness Result

Bag:

2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw

Comparison:

- baseline OC-SORT TIM-on target 1
- cooldown OC-SORT TIM-on target 1 r4
- cooldown setting: TIM_APPEARANCE_UPDATE_COOLDOWN_FRAMES=30

## Correctness comparison

| Metric | Baseline TIM | Cooldown TIM |
|---|---:|---:|
| Correct ratio | 0.680 | 0.608 |
| Wrong ratio | 0.310 | 0.285 |
| Lost ratio | 0.009 | 0.107 |

## Interpretation

The appearance update cooldown reduced wrong-target ratio slightly, from 0.310 to 0.285.

However, this came at the cost of increased lost-target ratio, from 0.009 to 0.107, and a reduced correct ratio, from 0.680 to 0.608.

This indicates that cooldown acts as a safety mechanism: it makes TIM more conservative and slightly reduces wrong-target output, but it does not solve selected-target recovery.

## Conclusion

Cooldown alone is not the final TIM improvement.

The next improvement should combine cooldown with candidate-hypothesis competition or stronger appearance comparison, so that TIM avoids learning the distractor while still recovering the true selected target.
