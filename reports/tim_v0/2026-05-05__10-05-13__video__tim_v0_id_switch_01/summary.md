# TIM-V0 Bag Analysis

- Bag: `/home/francisco/Desktop/Thesis-Code/artifacts/bags/live_camera/2026-05-05__10-05-13__video__tim_v0_id_switch_01`
- Raw `/target` samples: 316
- TIM `/target_memory` samples: 240
- TIM status samples: 240

## Validity

- Raw valid samples: 209/316
- TIM valid samples: 0/240

## Post-selection validity

- TIM never left NO_TARGET, no fair post-selection window available.

## State counts

- NO_TARGET: 240

## Control mode counts

- NO_CONTROL: 240

## Reacquisition

- Reacquisition samples/events observed: 0

## State transitions


## TIM latency

- mean: 0.0949 ms
- p50: 0.0398 ms
- p95: 0.0988 ms
- p99: 0.7602 ms
- max: 7.0913 ms

## Interpretation template

TIM-V0 adds a selected-target memory layer above tracker outputs. In normal tracking it should match the raw selected target with negligible latency. During temporary loss it exposes UNCERTAIN/LOST states and conservative control modes. When the tracker reassigns the person to a new track ID, TIM can transition through REACQUIRED and continue publishing the selected target, while a raw ID-based selector may remain invalid.