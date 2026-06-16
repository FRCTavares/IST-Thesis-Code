# TIM-MARS remaining validation plan

Date: 2026-06-06

## Purpose

The current TIM-MARS paper draft is strongest on the hard re-entry sequence. Two remaining weaknesses should be addressed before treating the paper as technically mature:

1. the main selected-target result is based on one hard re-entry stress sequence;
2. the current runtime table is a post-detection replay benchmark and excludes Hailo inference.

## Priority 1: Full Hailo-enabled runtime feasibility run

### Objective

Run the complete onboard perception pipeline on the Raspberry Pi 5 + Hailo platform with ByteTrack + TIM-MARS enabled.

### Required active components

- camera capture or recorded camera source;
- Hailo inference container/service;
- ROS inference client;
- tracker node using ByteTrack;
- TIM-MARS target memory node;
- target output recording;
- timing and thermal logging.

### Required topics

Record at minimum:

- `/camera/image_raw`
- `/detections`
- `/tracks`
- `/target`
- `/target_memory_mars`
- `/target_memory_mars/status`
- `/timing`
- `/timing_tracker`
- `/timing_target`
- `/camera/fps`, if available

### Required metrics

Report:

- detections Hz;
- tracks Hz;
- target memory Hz;
- end-to-end latency mean and p95, if available;
- tracker/TIM timing, if available;
- CPU percentage;
- peak RSS;
- Hailo/full pipeline wall time;
- temperature;
- throttling state from `vcgencmd get_throttled`.

### Paper use

Keep the existing post-detection runtime table as the overhead-isolation table. Add a separate full-pipeline feasibility table only if the run is clean.

The paper wording should distinguish:

- post-detection replay runtime: isolates tracker and TIM-MARS overhead;
- full Hailo-enabled runtime: verifies onboard feasibility.

## Priority 2: Additional selected-target sequence validation

### Objective

Add a small validation matrix so the paper is not based only on one hard re-entry sequence.

### Candidate sequence types

- close crossing / ambiguity;
- field-of-view exit and re-entry;
- simple no-crossing sanity case.

### Minimum method comparison

For each extra sequence, evaluate:

- Raw ByteTrack;
- ByteTrack + TIM-MARS.

Optional, if time allows:

- Raw OCSORT;
- OCSORT + TIM-MARS;
- Raw DeepSORT-MARS.

### Required metrics

Use the same selected-target correctness metrics:

- correct-target ratio;
- wrong-target ratio;
- lost-target ratio.

### Paper use

Add a compact additional validation table. Do not present it as a broad benchmark. Present it as stress-sequence evidence for selected-target behaviour.

## Main interpretation to preserve

TIM-MARS is not a new generic multi-object tracker and is not a universal replacement for DeepSORT-MARS. Its role is a control-facing selected-target memory layer. It is most useful when the base tracker has recoverable identity instability and when wrong-target output is considered worse than temporary target loss.
