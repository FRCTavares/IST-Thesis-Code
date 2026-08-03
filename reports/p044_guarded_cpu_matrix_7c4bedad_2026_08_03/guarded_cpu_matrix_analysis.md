# Issue #44 guarded CPU policy matrix

- Tag: `p044_guarded_cpu_matrix_7c4bedad_2026_08_03_r1`
- Git commit: `7c4bedad7216d0bea5b5c3bae4c97ffa53134735`
- Correctness stream: `tim_target_memory`
- Reference: `all_candidates` at 250 ms
- Candidate: `ambiguity_guarded` at 250 ms
- CPU safety gate: PASS

## Per-sequence comparison

| Sequence | Reference correct | Guarded correct | Correct delta | Wrong delta | Lost delta | Crop reduction | Backend-wall reduction | Safety |
|---|---:|---:|---:|---:|---:|---:|---:|:---:|
| `may_hard_reentry` | 0.922 | 0.920 | -0.20 pp | +0.00 pp | +0.30 pp | 47.15% | 46.12% | PASS |
| `seq01_clean` | 0.868 | 0.868 | +0.00 pp | +0.00 pp | +0.00 pp | 72.32% | 65.78% | PASS |
| `seq03_crossing` | 0.832 | 0.840 | +0.80 pp | +0.00 pp | -0.80 pp | 40.97% | 34.52% | PASS |
| `seq04_occlusion` | 0.663 | 0.663 | +0.00 pp | +0.00 pp | +0.00 pp | 39.80% | 44.47% | PASS |

## Aggregate comparison

| Metric | Result |
|---|---:|
| Correct-target ratio delta | +0.18 pp |
| Wrong-target ratio delta | +0.00 pp |
| Lost-target ratio delta | -0.18 pp |
| Requested-crop reduction | 55.16% |
| Steady backend-wall reduction | 51.03% |
| Backend-call reduction | -0.75% |

## Decision

ambiguity_guarded passes the current four-sequence CPU correctness gate at 250 ms and can advance to the selective-Hailo validation stage. This does not change the canonical all_candidates policy or validate RepVGG ranking, memory, target decisions, BEST_EFFORT transport, or sustained onboard operation.

The canonical YAML remains `all_candidates`. This evidence covers only synchronous CPU MARS candidate selection at the existing 250 ms interval.
