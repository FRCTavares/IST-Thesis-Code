# TIM-V2E Tiny16 CPU Latency Result

Date: 2026-05-20

## Purpose

Measure whether the current Tiny16 hybrid embedding is feasible to run on Raspberry Pi CPU as an event-triggered TIM-V2E appearance cue.

This benchmark measures model forward-pass latency only. It does not include crop extraction or ROS message handling.

## Model

- Tiny16 hybrid embedding
- input: 64x128 RGB crop
- output: 16D L2-normalised embedding
- checkpoint: `reports/tim_v2_embedding/tiny16_hybrid_ce_tri025_tw1s/tim_v2e_tiny_embedding.pt`

## Benchmark setup

Script:

- `tools/analysis/benchmark_tim_embedding_latency.py`

Settings:

- device: CPU
- warmup iterations: 50
- timed iterations: 300
- input shape per crop: 3x128x64
- batch sizes: 1, 2, 4, 8

## Results

| Batch | mean_ms | p50_ms | p95_ms | p99_ms | per_crop_mean_ms | per_crop_p95_ms |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1.901 | 1.876 | 2.126 | 2.313 | 1.901 | 2.126 |
| 2 | 2.329 | 2.325 | 2.378 | 2.455 | 1.164 | 1.189 |
| 4 | 3.423 | 3.413 | 3.475 | 3.631 | 0.856 | 0.869 |
| 8 | 9.695 | 9.659 | 10.080 | 10.181 | 1.212 | 1.260 |

## Interpretation

Tiny16 CPU inference is feasible for event-triggered TIM-V2E use.

The most relevant cases are batch 1 and batch 2:

- batch 1 p95: 2.126 ms
- batch 2 p95: 2.378 ms total

This is small compared with the perception latency budget and does not justify moving Tiny16 to Hailo at this stage.

## Decision

Keep Tiny16 on CPU for now.

Hailo should remain dedicated to detector inference. TIM-V2E appearance should run on CPU only when triggered by ambiguity, loss, or re-entry conditions.

## Remaining work

Before live integration, measure:

1. crop extraction cost,
2. end-to-end TIM appearance callback cost,
3. trigger rate under realistic videos,
4. effect on target output latency p95/p99.
