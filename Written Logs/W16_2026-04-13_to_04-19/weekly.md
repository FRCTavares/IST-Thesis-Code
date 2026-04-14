# Weekly Plan — W16 (2026-04-13 to 2026-04-19)

## Week Objective

Reduce the single-process perception 30 Hz gap by attacking pre-infer queue wait first, while keeping evidence quality high and workload comparability explicit.

## Priority Stack

1. Instrument and expose hidden pre-infer wait in standard timing artefacts.
2. Decouple image callback and inference wait with freshness-first async processing.
3. Run controlled queue-depth (1 vs 2) and pre-hailonet videoconvert (on vs off) comparisons.
4. Accept only variants that improve queue wait without reducing throughput or collapsing detection workload.
5. Freeze a stable baseline and carry it into the next optimization cycle.

## Success Criteria

- [ ] `/timing.container_queue_ms` is present in canonical reports for all new runs.
- [ ] Paired comparisons use matched workload gates (`detections_per_msg.mean`, `zero_ratio`).
- [ ] No selected variant regresses `/timing` Hz versus active baseline.
- [ ] Keep/drop decisions are recorded with numeric evidence.
