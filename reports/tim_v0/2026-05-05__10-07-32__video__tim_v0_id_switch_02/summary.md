# TIM-V0 Bag Analysis

- Bag: `/home/francisco/Desktop/Thesis-Code/artifacts/bags/live_camera/2026-05-05__10-07-32__video__tim_v0_id_switch_02`
- Raw `/target` samples: 308
- TIM `/target_memory` samples: 239
- TIM status samples: 239

## Validity

- Raw valid samples: 92/308
- TIM valid samples: 91/239

## Post-selection validity

- Post-selection window starts at t=10.79s
- Raw valid samples after TIM selection: 90/187
- TIM valid samples after TIM selection: 90/187

## State counts

- NO_TARGET: 51
- LOCKED: 90
- UNCERTAIN: 12
- LOST: 85
- REACQUIRED: 1

## Control mode counts

- NO_CONTROL: 51
- NORMAL: 90
- YAW_ONLY: 12
- HOVER: 85
- CONFIRM: 1

## Reacquisition

- Reacquisition samples/events observed: 1
  - t=17.26s state=REACQUIRED target_track_id=1 q=0.693 reason=reacquired_candidate

## State transitions

- t=10.79s: NO_TARGET -> LOCKED
- t=15.64s: LOCKED -> UNCERTAIN
- t=16.68s: UNCERTAIN -> LOST
- t=17.26s: LOST -> REACQUIRED
- t=17.35s: REACQUIRED -> LOCKED
- t=20.30s: LOCKED -> UNCERTAIN
- t=20.91s: UNCERTAIN -> LOST

## TIM latency

- mean: 0.1772 ms
- p50: 0.0986 ms
- p95: 0.2684 ms
- p99: 3.7459 ms
- max: 5.1569 ms

## Interpretation template

TIM-V0 adds a selected-target memory layer above tracker outputs. In normal tracking it should match the raw selected target with negligible latency. During temporary loss it exposes UNCERTAIN/LOST states and conservative control modes. When the tracker reassigns the person to a new track ID, TIM can transition through REACQUIRED and continue publishing the selected target, while a raw ID-based selector may remain invalid.