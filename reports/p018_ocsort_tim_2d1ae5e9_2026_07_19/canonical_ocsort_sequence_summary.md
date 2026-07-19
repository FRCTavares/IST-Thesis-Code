# P0.18 Canonical OC-SORT Sequence Evidence

- Tracker freeze commit: `305578f322df539f7d457de1f3cc7ddf27969734`
- TIM replay commit: `2d1ae5e9126daa9d52d2d5430b23186edfdb2833`
- Event evaluator commit: `4d7a601c33d9bece8cbd834c062d0857b8860638`
- Canonical config SHA-256: `16f21b2032135858d2ea7d5d8081536eb24204a3ef0f12efb05a628d626a0655`
- MARS model SHA-256: `e96f3cc09dbce76e2f6aeff09c8f2502916b4745f21e27911ee50d102a4a75f1`
- Evaluator timebase: first-image header timestamp
- Evaluator step and safety tolerance: `0.05 s`

## Raw versus TIM results

| Sequence | Raw C/W/L | TIM C/W/L | Correct delta [s] | Wrong delta [s] | Lost delta [s] | Absence-output delta [s] |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| seq03 — Crossing ambiguity | 0.340 / 0.001 / 0.659 | 0.850 / 0.015 / 0.135 | +48.831 | +1.350 | -50.181 | +0.000 |
| seq04 — Occlusion/no-exit | 0.644 / 0.002 / 0.354 | 0.702 / 0.003 / 0.295 | +3.297 | +0.050 | -3.347 | +0.000 |

## Safety decision

The canonical preset fails safety promotion across the required OC-SORT sequence pair.

- Seq03 increases wrong-target output by `1.350 s`, well above the `0.05 s` tolerance.
- Seq04 increases wrong-target output by `0.050 s`, exactly the evaluator-step tolerance boundary.
- Neither sequence increases target-absence valid output.

The single-preset motion-only modularity claim is therefore rejected. Architectural compatibility does not establish safety portability.

## Event-level localisation

Seq03 wrong-target increase:

- clean visible: `+0.750 s`;
- ID-switch fragmentation: `+0.150 s`;
- occlusion ambiguity: `+0.450 s`.

Seq04 wrong-target change:

- clean visible: `+0.000 s`;
- ID-switch fragmentation: `+0.150 s`;
- occlusion ambiguity: `-0.100 s`;
- overall: `+0.050 s`.

## Repeatability and integrity

- Both repetitions of each sequence have identical generated TIM semantic digests.
- Both repetitions of each sequence have identical authoritative evaluation CSVs.
- Both repetitions have clean recorded repository provenance.
- Canonical configuration, model, runtime, topic contract, and generated topic counts match.
- Corrected event-level aggregates match the authoritative evaluator within `0.004 s`.

Large ROS bags remain ignored under:

- `bags/replay/p018_ocsort_tim_2d1ae5e9_2026_07_19/`

This tracked package preserves compact evaluation and provenance evidence only.
