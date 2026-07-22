# P0.23 Retained-Run Provenance Template

Copy this file into the retained evidence report directory for each ground or
flight run.

## Identification

- Run ID:
- Date and local time:
- Scenario:
- Operator:
- Spotter:
- Flight or ground:
- Result: pass / reject / aborted

## Repository

- Git commit:
- Branch:
- `origin/main` commit:
- Working tree clean: yes / no
- Root runtime-noise check:
- Canonical configuration path:
- Canonical configuration SHA-256:
- Runtime overrides:

## Components

- Camera:
- Capture resolution and rate:
- Detector:
- HEF path and SHA-256:
- Tracker:
- Tracker parameters:
- TIM implementation:
- MARS model path and SHA-256:
- Control configuration:
- MAVROS configuration:

## Hardware and software

- Raspberry Pi model:
- Operating system:
- Kernel:
- ROS distribution:
- Hailo hardware:
- Hailo driver:
- HailoRT:
- Pixhawk:
- ArduPilot:
- Camera:
- Power source:
- Storage free before run:

## Commands

### Build

- Exact command:

### Launch and recording

- Exact command:

### Target selection

- Selected target ID:
- Selection command:

### Stop or abort

- Exact command or physical action:
- Abort reason, when applicable:

## Recorded evidence

- Main bag:
- Raw/source bag:
- MAVROS bag:
- Report directory:
- Log directory:
- Recording duration:
- Topics:
- Metadata SHA-256:

## Observations

- Detection rate:
- Track rate:
- TIM output rate:
- Control-reference rate:
- Latency:
- CPU:
- Memory:
- Maximum temperature:
- Throttling:
- TIM state transitions:
- Wrong-target observations:
- Stale or invalid target response:
- Control saturation:
- Control slew:
- MAVROS connection:
- Pilot/manual takeover:

## Decision

- Retain or delete:
- Justification:
- Known limitations:
- Suitable only as qualitative systems evidence:
- Related Issue #30 action:
- Related Issue #32 action:
