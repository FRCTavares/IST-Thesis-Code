# P0.4 Clean Canonical Four-Tracker TIM Matrix

- Repository commit: `1b7dc4002c19e5235703913826e174df1025f1d0`
- Canonical config SHA-256: `16f21b2032135858d2ea7d5d8081536eb24204a3ef0f12efb05a628d626a0655`
- MARS model SHA-256: `e96f3cc09dbce76e2f6aeff09c8f2502916b4745f21e27911ee50d102a4a75f1`
- Replay metadata schema: `3`
- Resolved-runtime schema: `2`
- Semantic-digest schema: `tim_mars_replay_generated_fields_v2`
- Evaluator timebase and step: image header, `0.05 s`

## Raw versus TIM results

| Tracker | Raw C/W/L | TIM C/W/L | Wrong delta | Absence-output delta | Verdict |
|---|---:|---:|---:|---:|---|
| ByteTrack | 0.514 / 0.000 / 0.486 | 0.920 / 0.010 / 0.069 | +0.700 s | +0.000 s | Reject |
| SORT | 0.442 / 0.000 / 0.558 | 0.786 / 0.080 / 0.134 | +5.300 s | +0.150 s | Reject |
| OC-SORT | 0.509 / 0.000 / 0.491 | 0.936 / 0.000 / 0.064 | +0.000 s | +0.200 s | Reject |
| DeepSORT | 0.366 / 0.001 / 0.633 | 0.755 / 0.225 / 0.020 | +15.203 s | +0.000 s | Reject |

## Scientific decision

The single canonical preset is not safety-portable across the evaluated tracker pairings. Evidence integrity passed, but unsafe degradation blocks promotion.

Stored v1 and v2 semantic digests are not directly comparable. The cross-schema audit recomputed both old and new bags under v2 and found identical aggregate digests and per-message records.

Large replay bags remain ignored under:

- `bags/replay/p004_tim_matrix_1b7dc400_2026_07_20/`
