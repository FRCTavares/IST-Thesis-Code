# Issue #44 Hailo ReID Load Matrix

## Scope

This report promotes compact evidence from the three-repetition controlled
hardware matrix at commit `e0c2a52db3f57ba5b8ada75e84500fc2fc4bb155`.

The experiment compares:

| Condition | Hailo ReID | CPU policy | Minimum interval |
|---|---:|---|---:|
| Reference | Disabled | `all_candidates` | 250 ms |
| Selective | Enabled | `all_candidates` | 250 ms |
| Forced frequent | Enabled | `all_candidates` | 0 ms |

The condition called selective is temporally throttled. It is not winner-only
CPU candidate selection.

## Aggregate results

| Metric | Reference | Selective | Forced frequent |
|---|---:|---:|---:|
| Detector mean | 6.069 ms | 9.793 ms | 11.162 ms |
| Detector p95 | 6.398 ms | 13.614 ms | 15.912 ms |
| Perception CPU mean | 9.98% | 11.29% | 11.18% |
| TIM CPU mean | 43.73% | 52.04% | 61.96% |
| Requests constructed | 0 | 1098 | 1468 |
| Results accepted | 0 | 771 | 931 |
| Expired requests | 0 | 327 | 537 |

Temporal throttling reduced request construction by
25.20% relative to forced-frequency execution.
Forced-frequency operation added
1.370
ms mean detector latency,
2.298
ms p95 detector latency, and
9.92
percentage points of TIM CPU relative to the 250 ms condition.

## Accepted gates

All nine runs completed. Detector timing was present, the sampler observed the
actual TIM and perception executables, causal and executor accounting closed,
Hailo remained serialized, executor failures and rejections were zero, all
queues drained, and final in-flight request counts were zero.

Process cleanup, Hailo release, repository cleanliness, and root-log hygiene
also passed.

## Interpretation boundary

This report validates repeated load, resource ownership, asynchronous
accounting, and the value of the 250 ms temporal scheduling limit.

It does not establish a safe CPU winner-selection policy and does not enable
RepVGG ranking, memory, or target-decision integration.

CPU MARS remains authoritative. Issue #44 therefore remains open.

## Files

- `matrix_metadata.json`: controlled experiment definition
- `load_comparison.json`: aggregate three-repetition comparison
- `per_run_metrics.json`: compact metrics for all nine runs
- `acceptance_summary.json`: acceptance gates and interpretation boundary
- `source_manifest.json`: hashes of the source summary files
