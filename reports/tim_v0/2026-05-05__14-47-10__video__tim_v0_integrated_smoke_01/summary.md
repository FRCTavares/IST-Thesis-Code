# TIM-V0 Bag Analysis

- Bag: `/home/francisco/Desktop/Thesis-Code/artifacts/bags/live_camera/2026-05-05__14-47-10__video__tim_v0_integrated_smoke_01`
- Raw `/target` samples: 242
- TIM `/target_memory` samples: 240
- TIM status samples: 240

## Validity

- Raw valid samples: 143/242
- TIM valid samples: 140/240

## Post-selection validity

- Post-selection window starts at t=10.82s
- Raw valid samples after TIM selection: 142/145
- TIM valid samples after TIM selection: 139/142

## State counts

- NO_TARGET: 97
- LOCKED: 139
- UNCERTAIN: 3
- REACQUIRED: 1

## Control mode counts

- NO_CONTROL: 97
- NORMAL: 139
- YAW_ONLY: 3
- CONFIRM: 1

## Reacquisition

- Reacquisition samples/events observed: 1
  - t=16.35s state=REACQUIRED target_track_id=1 q=0.658 reason=reacquired_candidate

## State transitions

- t=10.82s: NO_TARGET -> LOCKED
- t=16.05s: LOCKED -> UNCERTAIN
- t=16.35s: UNCERTAIN -> REACQUIRED
- t=16.43s: REACQUIRED -> LOCKED

## TIM latency

- mean: 0.1063 ms
- p50: 0.0895 ms
- p95: 0.1897 ms
- p99: 0.5236 ms
- max: 2.9828 ms

## Interpretation template

TIM-V0 adds a selected-target memory layer above tracker outputs. In normal tracking it should match the raw selected target with negligible latency. During temporary loss it exposes UNCERTAIN/LOST states and conservative control modes. When the tracker reassigns the person to a new track ID, TIM can transition through REACQUIRED and continue publishing the selected target, while a raw ID-based selector may remain invalid.