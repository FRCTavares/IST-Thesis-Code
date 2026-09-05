# models/

Neural-network weight files used by the perception and appearance paths.

```
models/
  hef/    Hailo-8 compiled detector graphs (.hef)
  reid/   appearance / re-identification models
```

This file is an inventory only. It does not change what is tracked. Its purpose
is to make a later tracked-vs-untracked decision safe: every entry records what
the file is, what depends on it, and whether its origin is known.

## Current tracked state

- `models/hef/*.hef` — **tracked** (16 files, added together in `a7e5aa45`,
  2026-04-27). Not matched by `.gitignore`.
- `models/reid/mars-small128.pb` — **tracked** (force-added in `91a97fa6`,
  2026-04-26). `.gitignore` line `models/reid/*.pb` would otherwise ignore it.
- `models/reid/repvgg_a0_person_reid_512.hef` — **not tracked** (ignored by
  `models/reid/*.hef`). Present on the Pi only.

No model file has recorded acquisition or compilation provenance in this
repository. Where origin is listed as *unknown / requires provenance recovery*,
the family and role are established from code and commit history but the exact
source artefact, conversion, and Hailo Dataflow Compiler settings are not.

## Detector models — `models/hef/`

Hailo-8 compiled graphs. Detector inference size is 640x640 in every current
runtime and experiment. Consumed by `perception_pipeline_node` /
`perception_camera_node` (`hailo_hef_path` parameter) and listed for the
dashboard model-switch API in
`ros2_ws/src/thesis_bringup/thesis_bringup/dashboard/dashboard_models.py`.

| File | Family | SHA-256 | Bytes | Role | Canonical | Origin |
| --- | --- | --- | ---: | --- | --- | --- |
| `yolov6n.hef` | YOLOv6-nano | `b645f970fb59f809f4a56b6727b8105fc143e75d43b046116311363f877b156d` | 5 773 147 | **canonical live detector default** (`tools/lib/live_defaults.sh`, `perception_pipeline_node` default `hailo_hef_path`); frozen detector for the Issue #64 R3 replay | yes | unknown / requires provenance recovery |
| `yolov8s.hef` | YOLOv8-small | `69540ff855740371d229f4caca1ab908635a72fec55fdc1541e73f2fc17ec43b` | 11 284 359 | detector for the official June 2026 sequences (Seq01–Seq04) and the current recommended live path `YOLOv8s + ByteTrack + TIM-MARS` (Issue #64) | yes | unknown / requires provenance recovery |
| `yolov8n.hef` | YOLOv8-nano | `eebaf6e491f8c182c095d2a2fd38d8fc6efbc55d595be1bbec75338f55751917` | 5 100 930 | detector alternative in the historical May 2026 `detector_eval_matrix` comparison (`docs/data/catalogue/bag_inventory.yaml`) | no | unknown / requires provenance recovery |
| `yolov10n.hef` | YOLOv10-nano | `9c92ae99e76aa16fabe96416cfa1cd478910b95e38cb4b9820b05ba9f3cf9038` | 7 721 797 | detector alternative in the historical May 2026 `detector_eval_matrix` comparison | no | unknown / requires provenance recovery |
| `yolov11n.hef` | YOLOv11-nano | `3a16fb7b03c48e7c0837e914e7d7e712481c60f511ff0de41ffe2c7e71818ca2` | 8 613 623 | detector alternative in the historical May 2026 `detector_eval_matrix` comparison | no | unknown / requires provenance recovery |
| `yolov5m.hef` | YOLOv5-medium | `e4620ae71c179766b3bdbb48022f786d3471f6e96df97a332d051809ad606e72` | 17 104 213 | dashboard model-switch catalogue only; no current experiment or runtime reference | no | unknown / requires provenance recovery |
| `yolov8m.hef` | YOLOv8-medium | `96260316e3074bdedd571f70227f92aa6720d07d2940dcb4f8f09e775d3ff309` | 31 157 648 | dashboard model-switch catalogue only | no | unknown / requires provenance recovery |
| `yolov8l.hef` | YOLOv8-large | `d1f1419c75ae1f10443c41b9d1a5b0217dc911f0a20f65b8dfb9eb9184f6babb` | 44 001 189 | dashboard model-switch catalogue only | no | unknown / requires provenance recovery |
| `yolov8x.hef` | YOLOv8-xlarge | `bb63d5505856f1d24cd632eeec751b447dc4bf9ec6bf0c6fe7d4d5c94fd781f5` | 55 097 282 | dashboard model-switch catalogue only | no | unknown / requires provenance recovery |
| `yolov10s.hef` | YOLOv10-small | `74f3676adbb90769255992ba8a6314ae565d3cffd3079b07784dc5df86cf7c0b` | 12 286 288 | dashboard model-switch catalogue only | no | unknown / requires provenance recovery |
| `yolov10b.hef` | YOLOv10-balanced | `64cfea3f22056c809f6cb3900d90286a41fc9474b947a120942fb0f104d2372a` | 29 804 243 | dashboard model-switch catalogue only | no | unknown / requires provenance recovery |
| `yolov10x.hef` | YOLOv10-xlarge | `be98921507ccb95b99881c294da6007885e2aba0373cfdb78c3d3dc13a797b66` | 34 876 007 | dashboard model-switch catalogue only | no | unknown / requires provenance recovery |
| `yolov11s.hef` | YOLOv11-small | `dea4024a9c9b24efffcb4ec4699e0eac41cd738d17cbe34eca72d85fd41214d5` | 19 579 151 | dashboard model-switch catalogue only | no | unknown / requires provenance recovery |
| `yolov11m.hef` | YOLOv11-medium | `eca5fe9bf35fec3f985f2d27d7773f60095c811c1a524d09812b50912d19d480` | 33 666 660 | dashboard model-switch catalogue only | no | unknown / requires provenance recovery |
| `yolov11l.hef` | YOLOv11-large | `d5b06476ea093a0c4494cc4ee1268d3fcc245103df395179568e78a587475ba6` | 35 397 106 | dashboard model-switch catalogue only | no | unknown / requires provenance recovery |
| `yolov11x.hef` | YOLOv11-xlarge | `2d69229a75c980c5e260f97b646452ffb5ed53367067ffe7df66fef975db946e` | 55 168 333 | dashboard model-switch catalogue only | no | unknown / requires provenance recovery |

The frozen live profile rejects runtime detector switching, so the dashboard
model-switch catalogue is not exercised by the frozen runtime. The eleven
"catalogue only" graphs (~330 MB) have no current experiment, live-default, or
`tools/reproduce_tim_mars.py` reference.

## Appearance / ReID models — `models/reid/`

### `mars-small128.pb` — canonical appearance backend

- Family: DeepSORT MARS-small128 appearance descriptor (frozen TensorFlow
  graph), 128-D L2-normalised embedding. Input size is read from the graph at
  load time.
- SHA-256: `e96f3cc09dbce76e2f6aeff09c8f2502916b4745f21e27911ee50d102a4a75f1`
- Bytes: 11 244 410
- Loaded by `thesis_tracker.backends.deepsort_core_backend.MarsSmall128Extractor`,
  wrapped for TIM-MARS by
  `ros2_ws/src/thesis_bringup/thesis_bringup/tim_mars/mars_reid_backend.py`.
- Used by: the canonical TIM-MARS appearance path (CPU, in process), the
  DeepSORT tracker backend, and every deterministic TIM-MARS replay experiment
  (`tools/experiments/run_deterministic_tim_replay.py --model models/reid/mars-small128.pb`;
  p004, p006b, p007, p014, p015, p017, p018, p028, p044, p058). It is named in
  the `run_provenance.json` of the promoted `docs/results/` packages.
- Canonical: yes. Tracked: yes (force-added).
- Origin: the `mars-small128.pb` frozen graph distributed with the `deep_sort`
  appearance-descriptor work. Exact acquisition not recorded here — *unknown /
  requires provenance recovery*.

### `repvgg_a0_person_reid_512.hef` — Hailo appearance-offload model (experimental)

- Family: RepVGG-A0 person re-identification, Hailo-8 compiled, 512-D
  L2-normalised embedding. Backend descriptor
  (`tim_mars/repvgg_reid_adapter.py`): embedding space
  `repvgg-a0-person-reid-512-v1`, input 256x128x3.
- SHA-256: `f6e172a073896b5ff2640b9f861e804b23c8093102518d2d0aa2d6e40e047a34`
- Bytes: 5 568 005
- Loaded by `perception_pipeline_node` (`reid_hef_path`, default
  `models/reid/repvgg_a0_person_reid_512.hef`, `reid_enabled` default false).
- Used by: the Issue #44 asynchronous Hailo appearance-offload measurements
  (`tools/experiments/run_p044_*`). Not part of the canonical algorithm — the
  cross-process transport (`appearance_async_reid_enabled`) defaults to false and
  CPU MARS remains authoritative for TIM-MARS decisions.
- Canonical: no. Tracked: no (`models/reid/*.hef`). Present only on the Pi.
- Origin: *unknown / requires provenance recovery*.

## No-longer-referenced by current runtime code

None of the tracked files is completely unreferenced: the eleven "catalogue
only" detector graphs are still listed in `dashboard_models.py`. They are,
however, unused by every frozen runtime path and every current experiment.

## Provenance recovery checklist

For each model, the following still needs to be recorded before a
tracked-vs-untracked decision:

1. source weights (upstream repo / release / Hailo Model Zoo entry and version);
2. for HEFs: ONNX/checkpoint used, Hailo Dataflow Compiler version, calibration
   dataset, and quantisation settings;
3. for `mars-small128.pb`: the exact distribution the frozen graph came from;
4. a reproducible acquisition or build command.

## Storage decision — Issue #49 (5 September 2026)

The repository Git object pack remains approximately 4.52 GiB. Issue #49 does
not migrate the tracked model artifacts or rewrite repository history.

The current tracked/untracked state is retained because artifact provenance is
still incomplete. A Git LFS, release-asset, or external artifact-store migration
would require a separate migration plan after provenance recovery, with backup,
collaborator coordination, and preservation of hashes and historical references.

Issue #49 therefore closes the storage decision as: **retain current model
tracking; no history rewrite or artifact migration in this issue**.
