# Daily Log — 2026-04-29 (Day 29)

## TL;DR

- Verified live stack; recorded bags and rendered overlays.
- ID stability fails in live tests; tracker-only benchmarks show trackers work under perfect detections.
- VisDrone2019-MOT-val integrated and exported to MOT format for repeatable evaluation.
- Full detector × threshold × tracker sweep completed; `yolov6n + ByteTrack` is the best strict-latency candidate.

## Goal

Move from manual live observations to repeatable, dataset-driven validation for detector + tracker combinations. Focus:

- confirm live ID instability reproducibility
- isolate tracker-only behaviour from detector errors
- produce a repeatable MOT evaluation harness
- identify a practical detector+tracker baseline under onboard latency constraints

## Context (carry-over)

- Live overlay rendering, control commands (`ids`, `target`, `clear-target`) functional
- Implementations: SORT, OC-SORT, ByteTrack, DeepSORT aligned for comparison
- Existing practical live baseline: `yolov6n + ocsort`

## Live validation

### Smoke test

Command run:

```bash
./tools/start_live_stack.sh --profile daily --record-video --bag-tag day29_fresh_smoke
```

Outcome:

- Stack started; `/tracks` published; `ids`, `target 1`, `clear-target` worked.
- Video bag recorded and overlay rendered at 720p.

Artifacts:

- Bag: bags/live_camera/2026-04-29__10-17-39__video__day29_fresh_smoke
- Overlay video: reports/videos/day29_fresh_smoke_720p.mp4

### Single-person recorded tests

Recorded bags:

- bags/live_camera/2026-04-29__10-26-03__video__clean_walk_yolov6n_ocsort
- bags/live_camera/2026-04-29__10-28-08__video__single_person_occlusion_yolov6n_ocsort
- bags/live_camera/2026-04-29__10-30-08__video__fov_exit_reentry_yolov6n_ocsort

Rendered overlays:

- reports/videos/2026-04-29__10-26-03__video__clean_walk_yolov6n_ocsort__overlay_720p.mp4
- reports/videos/2026-04-29__10-28-08__video__single_person_occlusion_yolov6n_ocsort__overlay_720p.mp4
- reports/videos/2026-04-29__10-30-08__video__fov_exit_reentry_yolov6n_ocsort__overlay_720p.mp4

Findings:

- Clean walk: target ID changed repeatedly (IDs 1→5).
- Short occlusion: sometimes recovered; long occlusion caused ID changes.
- FOV exit/re-entry: target not reacquired with same ID.

Conclusion:

- Live ID stability is insufficient; behaviour suggests detector instability (flicker, missed small/occluded detections) is the dominant cause.

## VisDrone dataset — setup and inspection

Dataset: VisDrone2019-MOT-val
Layout (local):

- datasets/external/visdrone2019-mot/raw/
- datasets/external/visdrone2019-mot/extracted/
- datasets/processed/visdrone2019-mot/

Scripts added:

- `tools/datasets/inspect_visdrone_mot.py` — dataset inspection report
- `tools/datasets/render_visdrone_gt_preview.py` — GT preview rendering
- `tools/datasets/export_visdrone_person_mot.py` — export to MOT format
- `tools/datasets/evaluate_mot_predictions.py` — lightweight MOT evaluator

Key inspection metrics:
- Sequences: 7

- Total images: 2,846
- Valid person rows: 49,848
- Valid person IDs: 333

Note: VisDrone contains many small and occluded people — good stress-test for UAV-style live tracking.

## Ground-truth sanity checks

- GT preview images written to `reports/dataset_checks/visdrone_gt_preview/` and visually validated.
- Exported MOT data: `datasets/processed/visdrone2019-mot/person_val_mot/`.
- Sanity evaluator: perfect-GT vs itself produced MOTA/IDF1 = 100%.

## Tracker-only benchmark (GT detections)

Script: `tools/experiments/run_visdrone_gt_tracker_matrix.py`
Purpose: evaluate tracker association and lifecycle under perfect detections to isolate tracker logic.

Summary (selected):

- OC-SORT live: MOTA 95.87%, IDF1 89.72%, ID switches 265
- ByteTrack default: MOTA 96.42%, IDF1 88.11%, ID switches 474
- SORT live: weaker identity continuity (MOTA 85.58%) but fastest runtime

Conclusion:

- Trackers (especially OC-SORT) perform well with perfect detections; therefore detector failures drive much of the live instability.

## Hailo detector integration & detector+tracker benchmarks

Scripts added:

- `tools/experiments/smoke_hailo_direct_visdrone.py` — Hailo inference sanity
- `tools/experiments/render_hailo_visdrone_preview.py` — detector preview
- `tools/experiments/run_visdrone_detector_tracker_matrix.py` — detector+tracker sweep

Detector preview:

- `models/hef/yolov6n.hef` loads and produces person boxes; mapping confirmed.
- Many small/occluded people are missed — recall is the bottleneck.

Example results (first detector-output benchmark, threshold 0.25):

- `yolov6n + OC-SORT live`: MOTA 13.89%, IDF1 17.37%, FN 40,732
- `yolov6n + ByteTrack default`: MOTA 12.47%, IDF1 19.13%, FN 42,709

Runtime: Hailo `yolov6n` inference mean ~5.4–7.2 ms; p95 ~5.5–12.9 ms.

Conclusion:

- Detector false negatives dominate tracking errors; ByteTrack reduces ID switches/fragments relative to OC-SORT when using detector outputs.

## Full VisDrone detector × threshold × tracker sweep

Configuration:

- Detectors: all `models/hef/*.hef` (16 models)
- Thresholds: 0.10, 0.15, 0.20, 0.25, 0.35
- Trackers: `sort_live`, `ocsort_live`, `ocsort_benchmark`, `bytetrack_default`
- Combinations: 16 × 5 × 4 = 320

Outputs: `reports/tracking/visdrone_full_detector_sweep_20260429_131518/summary.csv`

Selected findings:

- Best raw IDF1: `yolov8x` (IDF1 32.15%) but inference too slow for onboard control — full row below.
- Best strict-latency candidate among the exposed Hailo detections: `yolov6n + bytetrack_default`, Python threshold 0.10, with IDF1 19.33%, MOTA 12.76%, inference mean 6.72 ms, inference p95 max 14.68 ms, tracking mean 4.12 ms, and tracking p95 max 46.89 ms.

Raw best result (full row):

| Model | Threshold | Tracker | IDF1 | MOTA | FP | FN | IDSW | Frag | Infer mean | Infer p95 max | Track mean | Track p95 max |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| yolov8x | 0.10 | ocsort_benchmark | 32.15% | 20.80% | 2407 | 36788 | 285 | 947 | 77.28 ms | 83.85 ms | 14.69 ms | 138.81 ms |

Strict practical (latency-feasible) candidate (tested, postprocessed outputs):

| Model | Threshold | Tracker | IDF1 | MOTA | FP | FN | IDSW | Frag | Infer mean | Infer p95 max | Track mean | Track p95 max |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| yolov6n | 0.10 | bytetrack_default | 19.33% | 12.76% | 920 | 42477 | 90 | 330 | 6.72 ms | 14.68 ms | 4.12 ms | 46.89 ms |

Interpretation:

- Larger detectors raise IDF1 but violate latency constraints; under strict latency budgets `yolov6n + ByteTrack` (on the tested, postprocessed Hailo outputs) is a practical choice.
- Important caveat: Several detector-threshold rows were identical across thresholds, especially from 0.10 to 0.25. This suggests that the Hailo HEF/postprocess path is already applying an internal confidence threshold before detections reach the Python score filter. Therefore, the current sweep is a Python-side threshold sweep over already postprocessed detections, not necessarily a true raw detector-confidence sweep.

## Conclusions

- Live ID instability is primarily driven by detector miss/flicker and score/lifecycle thresholds, not tracker association alone.
- OC-SORT is strongest under perfect detections; ByteTrack is more robust when detector recall is limited.
- For strict onboard latency, `yolov6n + ByteTrack` is the best current practical baseline among the tested postprocessed Hailo outputs. However, true ByteTrack behaviour still requires exposing lower-confidence detections from the Hailo postprocess path.

## Next actions

1. Expose detector score threshold separately from tracker `min_score` (implementation task).
2. Re-run live with `yolov6n + ByteTrack` and detector threshold 0.10 to verify live ID stability.
3. Investigate HEF/postprocess to ensure low-score detections are not being filtered prematurely.

## Commits

Committed today:

- `ae713a9` — Add VisDrone MOT dataset export and lightweight evaluator
- `1c86e3c` — Add VisDrone GT tracker matrix benchmark
- `12c0d89` — Add VisDrone Hailo detector-tracker benchmark
- `4083e76` — Add full VisDrone detector sweep launcher

## Objectives For 2026-04-30 (Day 30)

### Priority 1 — Make ByteTrack valid in the live stack

Goal:

- make the live stack able to run the best strict-latency candidate from the VisDrone sweep:
  - `yolov6n`
  - `bytetrack`
  - detector-side confidence as low as possible, target 0.10
  - tracker high/low thresholds configured separately

Tasks:

1. Separate detector filtering from tracker filtering.
	- Detector output threshold must not be tied to tracker `min_score`.
	- ByteTrack must receive low-score detections down to approximately 0.10.
	- Tracker publishing/display filtering can remain separate.

2. Inspect Hailo postprocess thresholding.
	- Identify whether `libyolo_hailortpp_post.so` or the HEF itself applies an internal confidence threshold.
	- Document whether Python-side threshold changes can actually recover low-score detections.
	- If internal threshold cannot be changed immediately, write this as a known limitation.

3. Run live validation:
	- `yolov6n + bytetrack`
	- same single-person tests as Day 29:
	  - clean walk
	  - partial occlusion
	  - FOV exit/re-entry
	- record bags and render overlays.

Acceptance:

- `/detections`, `/tracks`, `/target`, `/timing`, `/timing_tracker` publish normally.
- ByteTrack does not starve from upstream filtering.
- Live target ID stability is compared against Day 29 `yolov6n + ocsort`.

### Priority 2 — Start the custom detector/tracker design

This cannot be delayed further. The project now has enough baseline evidence to justify designing the custom method.

Design starting points (incremental):

1. Custom target identity layer above the tracker.
	- Maintain a selected-target memory independent of raw tracker ID.
	- Use target bbox history, motion prediction, image location, scale, and appearance cue.
	- Reacquire target after short loss even if tracker creates a new ID.

2. Lightweight appearance cue.
	- Start with a target-only embedding or compact descriptor.
	- Use it only during ambiguity, occlusion, or reacquisition.
	- Do not run full ReID for all tracks every frame.

3. Tiny-person handling.
	- Detect when target height is below threshold, for example h < 20 px.
	- Add selective ROI refine only around the predicted target region.
	- Measure trigger rate and added latency.

4. Detector-side improvement plan.
	- Decide whether to:
	  - tune postprocess thresholds;
	  - add a tiny-person refine model;
	  - train a small custom person detector;
	  - or use detector outputs plus target-specific recovery as the first custom contribution.

Day 30 design output:

- one markdown design document: `docs/design/target_identity_memory.md`
- one implementation plan:
  - data structures
  - ROS topics affected
  - update rules
  - failure modes
  - metrics
- one first stub branch or script for target-memory evaluation.

## Technical Decision

The operational baseline should move from:

```text
yolov6n + ocsort

to:

yolov6n + bytetrack
```

for noisy detector-output conditions, provided that low-score detections can actually reach ByteTrack.

Reason:

- OC-SORT is stronger under perfect detections.
- ByteTrack is more robust under noisy detector outputs.
- ByteTrack produced fewer ID switches and fragments in the detector-output sweep.
- The final system depends on detector-limited tracking, not perfect detections.

## Final note

The log is valid, but the key next move is not another large sweep. Tomorrow should be implementation and design:

```text
1. make ByteTrack live-valid;
2. verify low-score detection access;
3. start the target-specific identity memory design.
```

## Artifacts & scripts (quick reference)

- Live recordings: `bags/live_camera/...` (day29 bags)
- Overlay videos: `reports/videos/*overlay_720p.mp4`
- Dataset inspection: `reports/dataset_checks/visdrone_mot_val_inspection.md`
- GT preview: `reports/dataset_checks/visdrone_gt_preview/`
- Exported MOT: `datasets/processed/visdrone2019-mot/person_val_mot/`
- Full sweep summary: `reports/tracking/visdrone_full_detector_sweep_20260429_131518/summary.csv`
- New scripts: `tools/datasets/*`, `tools/experiments/*`