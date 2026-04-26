# Daily Log - 2026-04-26 (Day 26) - Detector Model Sweep

## Context

- Goal: validate the newly added HEF detectors in the live single-process stack and collect first-pass timing evidence for later detector comparison.
- Stack was restarted after rebuilding `thesis_bringup` so the updated dashboard model registry and `/api/models` endpoint were active in the live runtime.
- Sweep was run through the live control API with the stack restored to `yolov6n` at the end.

## What Was Validated

- `GET /api/models` returned the full supported model list from the live dashboard bridge.
- Live model switching worked through `POST /api/model`.
- The following models were switched successfully and collected with `tools/collect_live_timing_stats.py`:
  - `yolov6n`
  - `yolov8s`
  - `yolov8m`
  - `yolov8x`
  - `yolov10b`
  - `yolov10x`
  - `yolov11l`
  - `yolov11x`
  - `yolo26m`
  - `damoyolo_tinynasl35_m`
- Unknown model names were rejected correctly with `400 unsupported model`.

## Output Location

- Sweep directory:
  - `reports/timing/model_sweep_20260426_121644/`

## First-Pass Comparison Summary

| Model | /timing Hz | infer_ms p95 | e2e_det_ms p95 | det/msg mean | Health |
|---|---:|---:|---:|---:|---:|
| `yolov6n` | 16.199 | 14.778 | 21.366 | 1.000 | 92.9 |
| `yolov8s` | 15.357 | 18.948 | 25.232 | 1.000 | 91.3 |
| `yolov8m` | 15.129 | 40.937 | 51.050 | 1.000 | 92.3 |
| `yolov10b` | 11.398 | 54.046 | 63.339 | 1.000 | 87.5 |
| `yolov11l` | 11.990 | 61.901 | 70.281 | 1.111 | 87.6 |
| `damoyolo_tinynasl35_m` | 13.458 | 45.678 | 79.096 | 36.050 | 86.2 |
| `yolo26m` | 11.319 | 48.908 | 88.254 | 54.333 | 75.4 |
| `yolov8x` | 9.254 | 88.234 | 167.757 | 1.000 | 60.4 |
| `yolov10x` | 10.201 | 87.515 | 166.966 | 1.000 | 57.3 |
| `yolov11x` | 9.097 | 100.523 | 187.479 | 1.000 | 56.6 |

## Immediate Read

- Best latency and throughput baseline remains `yolov6n`.
- Best near-baseline alternative is `yolov8s`.
- `yolov8m` remains viable if accuracy gain justifies the latency increase.
- `yolov10b` and `yolov11l` are plausible mid-tier candidates for later quality-vs-latency comparison.
- `yolov8x`, `yolov10x`, and `yolov11x` look too heavy for the current live stack configuration.

## Important Caveat On `yolo26m` And `damoyolo_tinynasl35_m`

- The runtime already applies a `person` label filter in the direct HEF path.
- Despite that, `yolo26m` produced `54.333` detections per message on average and `damoyolo_tinynasl35_m` produced `36.050`.
- That means at least one of these is true:
  - the models are generating many detections that still map to class `person`
  - the output tensor layout/class mapping for these HEFs is different from the decoder assumption used by the current direct backend
- Because of that, these two models are not yet apples-to-apples with the cleaner person-only YOLO runs.

## Follow-Up Investigation Result

- Root cause confirmed by inspecting HEF output metadata:
  - `yolov6n_hailo8.hef` exposes a postprocessed NMS output:
    - `yolov6n/yolox_nms_postprocess shape=(80, 5, 100)`
  - `yolo26m.hef` exposes raw feature-map heads instead of decoded NMS output:
    - `conv71 (80, 80, 4)`
    - `conv87 (40, 40, 4)`
    - `conv101 (20, 20, 4)`
    - `conv74 (80, 80, 80)`
    - `conv90 (40, 40, 80)`
    - `conv104 (20, 20, 80)`
  - `damoyolo_tinynasL35_M.hef` also exposes raw feature-map heads:
    - `conv83 (80, 80, 68)` / `conv84 (80, 80, 81)`
    - `conv97 (40, 40, 68)` / `conv98 (40, 40, 81)`
    - `conv110 (20, 20, 68)` / `conv111 (20, 20, 81)`
- Conclusion:
  - current direct backend decoder assumes class-grouped NMS-style outputs and is not a valid decoder for these two HEFs
  - person filtering is already on, but it cannot fix a decoder/output-format mismatch
- Immediate action taken:
  - mark `yolo26m` and `damoyolo_tinynasl35_m` as not switchable in the dashboard model registry until a model-specific decode/postprocess path exists

## Next Decision

- Use `yolov6n`, `yolov8s`, `yolov8m`, `yolov10b`, and `yolov11l` as the first clean comparison set.
- Treat `yolo26m` and `damoyolo_tinynasl35_m` as requiring decoder/output-format investigation before they can be compared fairly.
