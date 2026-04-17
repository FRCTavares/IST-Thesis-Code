# Timing Summary: phase2_contract_example

## Per-field stats (/timing)

| field | n | mean | p50 | p95 | p99 | min | max |
|---|---:|---:|---:|---:|---:|---:|---:|
| pre_ms | 600 | 5.300 | 5.000 | 8.000 | 9.000 | 3.000 | 11.000 |
| container_queue_ms | 600 | 20.400 | 18.000 | 40.000 | 50.000 | 2.000 | 58.000 |
| zmq_roundtrip_ms | 600 | 10.200 | 9.000 | 18.000 | 22.000 | 4.000 | 25.000 |
| infer_ms | 600 | 13.600 | 13.000 | 18.000 | 21.000 | 8.000 | 23.000 |
| e2e_det_ms | 600 | 82.000 | 79.000 | 112.000 | 130.000 | 54.000 | 146.000 |
| pub_dt_ms | 600 | 101.000 | 100.000 | 124.000 | 136.000 | 83.000 | 142.000 |

## Tracker runtime
track_ms

## Target end-to-end runtime
e2e_target_ms
