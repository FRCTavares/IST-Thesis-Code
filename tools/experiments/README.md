# tools/experiments

Last reviewed: 2026-10-13

## Purpose

Resource and hardware samplers used to measure a running stack. The replay,
ablation, sensitivity and capture runners that used to live here belonged to
the thesis evaluation and are at Git tag `archive/thesis-final-20261013`.

## Contents

| Path | Role | Why it exists |
| --- | --- | --- |
| `sample_process_groups.py` | Sampler | Samples Linux process-group CPU/RSS as JSONL (`p044_process_group_sample_v1`). |
| `sample_hardware_health.py` | Sampler | Samples temperature, ARM frequency, throttling, available memory and core voltage (`p044_hardware_health_sample_v1`). |

## Rules

- Samplers only observe; they never start, stop or signal ROS nodes.
- Metric definitions are in `docs/RUNTIME_METRICS.md`.
