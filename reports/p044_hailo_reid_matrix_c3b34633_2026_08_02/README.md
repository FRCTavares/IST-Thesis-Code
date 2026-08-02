# P044 Three-Repetition Hailo ReID Matrix

## Status

Accepted three-repetition paired hardware evidence for Issue #44 at
commit `c3b346330b4f67894ac07d69f2ea4dff3d7ed333`.

This accepts the repeatability, causal accounting, executor bounds,
shared-Hailo serialization, and process hygiene of the experiment. It
does not yet approve the architecture for final runtime integration.

## Experimental conditions

Each repetition replayed the same hard-reentry bag twice:

1. Reference: direct Hailo detector with RepVGG execution and TIM
   asynchronous transport disabled.
2. Treatment: identical detector and replay with the bounded RepVGG
   executor and TIM causal transport enabled.

CPU MARS remained authoritative using `all_candidates` at 250 ms.
RepVGG ranking, memory, cache, and target decisions remained disabled.

## Aggregate accounting

| Metric | Value |
|---|---:|
| Repetitions | 3 |
| Constructed requests | 1113 |
| Published requests | 1113 |
| Executor submissions | 766 |
| Executor successes | 766 |
| TIM accepted results | 763 |
| Expired in flight | 350 |
| Final in flight | 0 |
| Request-side losses | 347 |
| Result-side losses | 3 |
| Backend failures | 0 |

Every repetition closed its causal ledger.

## Detector contention

| Metric | Reference | Treatment | Delta |
|---|---:|---:|---:|
| Mean inference | 6.026 ms | 9.670 ms | +3.645 ms |
| P95 inference | 6.226 ms | 13.301 ms | +7.075 ms |

The mean detector inference time increased by
60.49%. The p95 increased by
113.65%.

The mean delta ranged from 3.602 to
3.694 ms across repetitions. The p95 delta ranged
from 6.913 to 7.251 ms.

The shared Hailo engine remained serialized at one active call and the
executor queue reached a maximum depth of two.

## Transport delivery

| Metric | Mean | Minimum | Maximum |
|---|---:|---:|---:|
| Request delivery to executor | 68.82% | 64.69% | 71.70% |
| Result delivery to TIM | 99.62% | 99.25% | 100.00% |

The low request delivery is a material limitation. Deadline expiry now
makes loss safe and observable, but does not make it free. The next
architecture step must either:

- justify this as intentional latest-data shedding under a bounded
  asynchronous policy; or
- compare a different transport/QoS or admission policy and determine
  whether delivery can improve without worsening detector contention.

## Remaining Issue #44 evidence

The following remain outstanding:

- selective versus forced-frequent Hailo load;
- CPU displacement and resource measurements;
- quantised ranking and decision equivalence;
- target-safety and availability validation;
- sustained onboard behaviour;
- a justified request-delivery policy.

Raw bags, JSONL events, runtime logs, and resource samples remain local
ignored evidence at:

- `reports/p044_hailo_reid_pair_c3b34633_2026_08_02_hard_reentry_matrix_r3`
- `bags/replay/p044_hailo_reid_pair_c3b34633_2026_08_02_hard_reentry_matrix_r3`
- `ros2_ws/log/p044_hailo_reid_pair_c3b34633_2026_08_02_hard_reentry_matrix_r3`
