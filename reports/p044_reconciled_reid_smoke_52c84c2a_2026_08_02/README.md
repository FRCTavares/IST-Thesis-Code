# P044 Reconciled Hailo ReID Smoke Evidence

## Status

Accepted one-repetition hardware smoke for Issue #44 at commit
`52c84c2a8258d32127c124d39317b7af2f5ddf04`.

The paired run compared the direct-Hailo detector reference against
the same detector and replay with the optional RepVGG executor and
TIM causal transport enabled.

CPU MARS remained authoritative with `all_candidates` scheduling at
250 ms. RepVGG ranking, memory, cache, and target-decision integration
remained disabled.

## Source

- Source bag: `bags/reference/tim_good/2026-05-14__hard_reentry__bytetrack__tim_mars_v4_margin010__target_1`
- Selected target: `1`
- Replay rate: `1.0`
- Repetitions: `1`
- Raw runtime report: `reports/p044_hailo_reid_pair_52c84c2a_2026_08_02_hard_reentry_smoke_reconciled_r1`
- Raw evidence bags: `bags/replay/p044_hailo_reid_pair_52c84c2a_2026_08_02_hard_reentry_smoke_reconciled_r1`
- Raw runtime logs: `ros2_ws/log/p044_hailo_reid_pair_52c84c2a_2026_08_02_hard_reentry_smoke_reconciled_r1`

The raw artifacts remain ignored local runtime evidence. This tracked
package contains compact summaries and provenance for the accepted
smoke.

## Causal transport accounting

| Metric | Value |
|---|---:|
| Constructed requests | 370 |
| Published requests | 370 |
| Executor submissions | 267 |
| Executor successes | 267 |
| TIM accepted results | 264 |
| Expired in flight | 106 |
| Final in flight | 0 |
| Request-side transport losses | 103 |
| Result-side transport losses | 3 |
| Request delivery to executor | 72.16% |
| Result delivery to TIM | 98.88% |

Accounting closes exactly:

    264 accepted + 106 expired = 370 constructed

No backend failure, executor rejection, malformed result, publication
error, or unresolved in-flight request remained.

## Detector contention

| Metric | Reference | Treatment | Delta |
|---|---:|---:|---:|
| Mean inference | 6.114 ms | 9.632 ms | +3.518 ms |
| P95 inference | 6.575 ms | 13.304 ms | +6.729 ms |

The shared Hailo engine remained serialized with one active call. The
executor queue reached a maximum depth of two.

## ReID latency

| Metric | Mean | P95 | Maximum |
|---|---:|---:|---:|
| Queue delay | 4.580 ms | 11.411 ms | 15.762 ms |
| Worker | 6.449 ms | 9.684 ms | 22.507 ms |
| End to end | 11.029 ms | 13.309 ms | 38.268 ms |

## Acceptance

The smoke passed paired collection, causal deadline reconciliation,
closed request accounting, executor and engine bounds, process cleanup,
Hailo release, repository cleanliness, and root-log hygiene.

This is smoke-level acceptance only. The repeated hardware matrix,
ranking equivalence, safety validation, and sustained onboard evidence
remain outstanding.
