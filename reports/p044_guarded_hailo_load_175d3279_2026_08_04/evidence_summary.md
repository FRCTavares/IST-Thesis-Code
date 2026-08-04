# Issue #44 guarded Hailo load evidence

- Source commit: `175d3279ab12dc1a108d4ad8ff08cbfd09ab4a2b`
- Conditions: detector-only reference, all-candidate Hailo, guarded Hailo
- Repetitions: 3
- Completed runs: 9
- CPU MARS authoritative: yes
- RepVGG target-decision integration: disabled
- Canonical policy changed: no

## Guarded versus all-candidate Hailo

| Metric | All candidates | Guarded | Change |
|---|---:|---:|---:|
| Constructed requests | 1110 | 582 | -47.57% |
| Expired in flight | 348 | 18 | -94.83% |
| Request delivery | 68.74% | 97.59% | +28.86 pp |
| Result delivery | 99.87% | 99.30% | -0.57 pp |
| TIM mean CPU | 44.20% | 26.03% | -18.16 pp |
| TIM mean RSS | 732209.93 KiB | 716334.36 KiB | -15875.57 KiB |
| Detector mean inference | — | — | -0.134 ms |
| Detector p95 inference | — | — | -0.122 ms |

No executor failures were recorded, final in-flight work was zero,
and Hailo execution remained serialized.

## Interpretation boundary

This evidence validates guarded request-load reduction, transport pressure,
queue drainage, resource displacement and detector contention under the
current observational RepVGG path.

It does not validate RepVGG ranking equivalence, target-decision
equivalence, BEST_EFFORT reliability, failure-injection fallback safety,
or sustained onboard operation. Canonical YAML remains `all_candidates`.
