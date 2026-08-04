# P044 Live ReID Fault Acceptance

## Execution

- Execution commit: `7283a97363436f35baf3e01752b81e36e94c2af3`
- Source bag: `bags/reference/tim_good/2026-05-14__hard_reentry__bytetrack__tim_mars_v4_margin010__target_1`
- Playback rate: `1.0`
- Repetitions: 3
- Hardware runs: 12
- CPU request policy: `ambiguity_guarded`
- CPU request interval: 250 ms
- TIM asynchronous deadline: 500 ms
- Delayed-result injection: 1000 ms

## Aggregate results

| Condition | Requests | Relayed results | TIM accepted | TIM expired | Backend failures rejected | Late results rejected |
|---|---:|---:|---:|---:|---:|---:|
| Pass-through | 582 | 568 | 566 | 16 | 0 | 0 |
| Suppressed result | 582 | 0 | 0 | 582 | 0 | 0 |
| Backend failure | 584 | 558 | 0 | 26 | 558 | 0 |
| Delayed result | 583 | 567 | 0 | 583 | 0 | 552 |

All 12 runs completed with:

- zero real Hailo executor failures;
- zero relay malformed-input or publication errors;
- zero abandoned delayed results;
- drained executor queues and in-flight work;
- zero remaining TIM in-flight work;
- no error-pattern matches in runtime logs.

## Interpretation

The pass-through condition retained normal observational RepVGG results. Result
suppression caused all outstanding TIM requests to expire. Injected backend
failures were rejected explicitly, while results delayed beyond the 500 ms TIM
deadline expired first and were subsequently rejected as unknown or no longer
in flight.

This validates repeatable live fail-closed behaviour for the observational
RepVGG transport on the tested hard-reentry sequence. CPU MARS remained
authoritative. RepVGG ranking, memory, cache, and target-decision integration
remained disabled.

This evidence does not prove authoritative RepVGG decision safety,
cross-sequence generality, or sustained onboard reliability.

## Artifact policy

Only this compact report is tracked. Raw JSONL events, resource samples,
evidence bags, and runtime logs remain ignored local artifacts at:

- `reports/p044_live_reid_fault_7283a973_2026_08_04_hard_reentry_fault_acceptance_r3`
- `bags/replay/p044_live_reid_fault_7283a973_2026_08_04_hard_reentry_fault_acceptance_r3`
- `ros2_ws/log/p044_live_reid_fault_7283a973_2026_08_04_hard_reentry_fault_acceptance_r3`
