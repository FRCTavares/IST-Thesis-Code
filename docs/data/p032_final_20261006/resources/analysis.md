# Issue #32 Final Resource Analysis

- Schema: `p032_final_resource_analysis_v1`
- Observed span: 1260.001 s
- Warm-up excluded from steady state: 60.000 s
- Architecture groups included: detector, tracker, tim, controller
- Missing requested groups: none

## Architecture total

| Metric | Population | n | Mean | Std | p50 | p90 | p95 | p99 | Max |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| CPU (%) | all | 1258 | 268.343 | 10.306 | 269.952 | 279.974 | 282.970 | 286.968 | 296.769 |
| CPU (%) | steady_state | 1199 | 268.377 | 10.296 | 269.949 | 280.260 | 282.970 | 286.968 | 296.769 |
| RSS (KiB) | all | 1259 | 1346260.486 | 7330.453 | 1344852.000 | 1358616.000 | 1358792.000 | 1358953.040 | 1359120.000 |
| RSS (KiB) | steady_state | 1199 | 1346868.831 | 6972.397 | 1345096.000 | 1358616.800 | 1358792.400 | 1358960.080 | 1359120.000 |

## Hardware health

| Metric | Population | n | Mean | Std | p50 | p90 | p95 | p99 | Max |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Temperature (C) | all | 250 | 69.413 | 0.887 | 69.700 | 70.300 | 70.800 | 70.800 | 71.400 |
| Temperature (C) | steady_state | 239 | 69.486 | 0.829 | 69.700 | 70.300 | 70.800 | 70.800 | 71.400 |
| ARM frequency (Hz) | all | 250 | 2400027507.712 | 5704.055 | 2400027136.000 | 2400033792.000 | 2400037120.000 | 2400037120.000 | 2400037120.000 |
| ARM frequency (Hz) | steady_state | 239 | 2400027480.904 | 5617.184 | 2400027136.000 | 2400033792.000 | 2400037120.000 | 2400037120.000 | 2400037120.000 |
| Available memory (KiB) | all | 250 | 5903673.392 | 12469.372 | 5906124.000 | 5916261.600 | 5917782.600 | 5923873.440 | 5924540.000 |
| Available memory (KiB) | steady_state | 239 | 5903415.632 | 12690.841 | 5905792.000 | 5916546.400 | 5917912.400 | 5923889.280 | 5924540.000 |

## Integrity / boundaries

- Non-zero throttle samples, all: 250
- Non-zero throttle samples, steady state: 239
- Core voltage is telemetry, not electrical power.
- This analyser does not rewrite historical sampler output.
