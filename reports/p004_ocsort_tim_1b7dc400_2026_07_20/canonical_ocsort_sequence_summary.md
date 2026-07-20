# P0.4 Clean Canonical OC-SORT Sequence Evidence

- TIM replay commit: `1b7dc4002c19e5235703913826e174df1025f1d0`
- Tracker freeze commit: `305578f322df539f7d457de1f3cc7ddf27969734`
- Canonical config SHA-256: `16f21b2032135858d2ea7d5d8081536eb24204a3ef0f12efb05a628d626a0655`
- MARS model SHA-256: `e96f3cc09dbce76e2f6aeff09c8f2502916b4745f21e27911ee50d102a4a75f1`
- Replay metadata schema: `3`
- Resolved-runtime schema: `2`
- Semantic-digest schema: `tim_mars_replay_generated_fields_v2`

## Raw versus TIM results

| Sequence | Raw C/W/L | TIM C/W/L | Correct delta | Wrong delta | Lost delta |
|---|---:|---:|---:|---:|---:|
| Seq03 crossing ambiguity | 0.340 / 0.001 / 0.659 | 0.850 / 0.015 / 0.135 | +48.831 s | +1.350 s | -50.181 s |
| Seq04 occlusion/no-exit | 0.644 / 0.002 / 0.354 | 0.702 / 0.003 / 0.295 | +3.297 s | +0.050 s | -3.347 s |

## Safety decision

Seq03 exceeds the wrong-target safety tolerance. Seq04 lies exactly at the one-step tolerance boundary. The canonical preset is therefore not promoted as universally safe.

Both repetitions match in generated semantic messages, topic counts, aggregate evaluation, event-level evaluation, and resolved runtime after normalising the output path.

Large replay bags remain ignored under:

- `bags/replay/p004_ocsort_tim_1b7dc400_2026_07_20/`
