# TIM-V0 Bag Analysis

- Bag: `/home/francisco/Desktop/Thesis-Code/artifacts/bags/live_camera/2026-05-05__09-55-39__video__tim_v0_occlusion_01`
- Raw `/target` samples: 393
- TIM `/target_memory` samples: 400
- TIM status samples: 400

## Validity

- Raw valid samples: 248/393
- TIM valid samples: 163/400

## Post-selection validity

- Post-selection window starts at t=21.76s
- Raw valid samples after TIM selection: 162/168
- TIM valid samples after TIM selection: 162/168

## State counts

- NO_TARGET: 231
- LOCKED: 162
- UNCERTAIN: 6
- REACQUIRED: 1

## Control mode counts

- NO_CONTROL: 231
- NORMAL: 162
- YAW_ONLY: 6
- CONFIRM: 1

## Reacquisition

- Reacquisition samples/events observed: 1
  - t=33.82s state=REACQUIRED target_track_id=1 q=0.779 reason=reacquired_candidate

## State transitions

- t=21.76s: NO_TARGET -> LOCKED
- t=33.39s: LOCKED -> UNCERTAIN
- t=33.82s: UNCERTAIN -> REACQUIRED
- t=33.95s: REACQUIRED -> LOCKED

## TIM latency

- mean: 0.1174 ms
- p50: 0.0636 ms
- p95: 0.2046 ms
- p99: 0.8148 ms
- max: 6.6742 ms

## Interpretation template

TIM-V0 adds a selected-target memory layer above tracker outputs. In normal tracking it should match the raw selected target with negligible latency. During temporary loss it exposes UNCERTAIN/LOST states and conservative control modes. When the tracker reassigns the person to a new track ID, TIM can transition through REACQUIRED and continue publishing the selected target, while a raw ID-based selector may remain invalid.