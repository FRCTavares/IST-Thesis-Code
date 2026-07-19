# P0.18 Canonical Four-Tracker TIM Matrix

- Repository commit: `36ecd17da9a66c4b95f82234960d831fb4f5ba44`
- Canonical config SHA-256: `16f21b2032135858d2ea7d5d8081536eb24204a3ef0f12efb05a628d626a0655`
- MARS model SHA-256: `e96f3cc09dbce76e2f6aeff09c8f2502916b4745f21e27911ee50d102a4a75f1`
- Evaluator timebase: image header
- Evaluator step: `0.05 s`
- Safety tolerance: `0.05 s`

## Raw versus TIM results

| Tracker | Raw correct | Raw wrong | Raw lost | TIM correct | TIM wrong | TIM lost | Wrong delta [s] | Absence-output delta [s] | Unsafe |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| bytetrack | 0.514 | 0.000 | 0.486 | 0.920 | 0.010 | 0.069 | 0.700 | 0.000 | yes |
| sort | 0.442 | 0.000 | 0.558 | 0.786 | 0.080 | 0.134 | 5.300 | 0.150 | yes |
| ocsort | 0.509 | 0.000 | 0.491 | 0.936 | 0.000 | 0.064 | 0.000 | 0.200 | yes |
| deepsort | 0.366 | 0.001 | 0.633 | 0.755 | 0.225 | 0.020 | 15.203 | 0.000 | yes |

## Safety decision

The single canonical preset is rejected for safety promotion on this hard-reentry sequence. Unsafe degradation remains above the 0.05-second tolerance for ByteTrack, SORT, OC-SORT, and DeepSORT.

A single preset is safety-valid only if TIM does not increase wrong-target duration or target-absence valid-output duration by more than one evaluator step (0.05 seconds) for any tracker.

The report field `passed=true` means that all evidence-integrity checks passed. It does not mean that the preset passed safety promotion.

## Tracker-specific degradation

- **bytetrack**: wrong-target +0.700 s.
- **sort**: wrong-target +5.300 s; target-absence valid-output +0.150 s.
- **ocsort**: target-absence valid-output +0.200 s.
- **deepsort**: wrong-target +15.203 s.

## Scientific interpretation

The one-preset motion-only modularity claim is not supported on this sequence because ByteTrack, SORT, and OC-SORT each show unsafe degradation. The DeepSORT result also supports keeping appearance-based association outside the current safe layering claim.

## Comparison qualification

Raw-versus-TIM comparisons are valid within each tracker. Direct absolute comparisons between trackers are qualified because each tracker autonomously initialized its own physical target.

## Limitations

- This is one hard-reentry sequence and does not replace the required OC-SORT crossing and occlusion evaluation.
- Each tracker autonomously initialized its own physical target, so absolute cross-tracker performance is not a controlled comparison.
- The safety decision uses within-tracker raw-versus-TIM deltas.

## Evidence integrity

All provenance, input-hash, configuration, model, topic-count, annotation, metadata-fingerprint, and semantic-digest checks passed.

Detailed unsafe windows are preserved in `unsafe_window_diagnostic.json`.
