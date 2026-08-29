# Issue #64 Gate-2 physical-evaluation preparation

Status: superseded by the completed controlled result in
`p064_gate2_resolution_evaluation.md`

Date: 27 August 2026

## Frozen scientific decision rule

Gate 2 compares native 1280x720 appearance pixels with a deterministic 640x360
complete-frame downsample from the same R3 source timeline. Detector evidence,
ByteTrack candidates, timestamps, scene, FOV, selected physical target,
evaluation window, physical reference, CPU MARS model, and canonical TIM-MARS
parameters are held fixed.

The primary evaluator fields are the v2 mutually exclusive duration buckets:
`correct_target_output_duration_s`, `wrong_person_output_duration_s`,
`identity_unresolved_duration_s`, and `lost_or_suppressed_duration_s` while
the target is present, plus the safety subset
`target_absent_with_output_duration_s`. Define target-present duration as the
sum of the first four buckets; do not include absent, reference-unavailable, or
reference-gap duration in that denominator.

Native HD is eligible only if it does not increase wrong-person duration or
absent-with-output duration beyond the evaluator's 1e-6 s reconciliation
tolerance. Subject to that safety gate, HD is materially better if either:

1. correct-target fraction increases by at least 0.05, or
   lost-or-suppressed fraction decreases by at least 0.05, using the frozen
   target-present denominator; or
2. the human-annotated hard exit/re-entry event becomes a correct reacquisition
   within 1.0 s without a safety regression.

Localization and cosine-similarity measurements are secondary. This rule was
recorded before either comparative TIM output was generated or inspected.

## Canonical R3 master and interval

Source bag:

`bags/source_video/2026-08-27__16-34-50__source__p064_gate2_hd_master_r3__image_raw_detections`

Source MCAP SHA-256:

`5580e25f4fef27d3d01c47cfd1e176c56b43449831b62285b6eae2a33aaed34b`

The bag contains 923 native 1280x720 `/camera/image_raw` messages and 928
live-Hailo `/detections` messages. Detection metadata declares
`source=1280x720;inference=640x640`. The earliest positive source-header
timestamp is the first detection at `1787844897072285865 ns`.

The predeclared usable window is exactly
`[3.000000000, 30.900267443] s` relative to that origin:

- absolute lower boundary: `1787844900072285865 ns`;
- final detection/right boundary: `1787844927972553308 ns`;
- first retained source image: `1787844900105460962 ns`
  (`3.033175097 s`, original source-image index 85);
- last retained source image: `1787844927972553308 ns`
  (`30.900267443 s`, original index 921);
- 837 retained detections and 837 exactly timestamp-matched images;
- maximum retained image/detection gap: `34.105559 ms`;
- zero gaps greater than or equal to 67 ms;
- the sole post-window image is original index 922 at `30.933606996 s`,
  33.339553 ms after the final detection, and is excluded.

The 33.175097 ms between the exact 3.0 s boundary and the first available
retained image is an honest reference gap, not fabricated geometry.

## Frozen ByteTrack evidence

Frozen bag:

`bags/replay/p064_gate2_hd_master_r3__bytetrack_frozen`

- canonical config:
  `ros2_ws/src/thesis_bringup/config/tracker_bytetrack.yaml`;
- config SHA-256:
  `e0e5c7c80a2f2b74cb6640e2ea90d9651c33f193c34365dc0d5a7ac9badaa906`;
- 928 detection, track, and target messages;
- generated tracker semantic SHA-256:
  `68b7b81d39d3445effcb50de43f768d613235bd20c0047c4194566fc1627276d`;
- frozen candidate-stream SHA-256:
  `23e7388edd50e341ef325efef30de45a70cb59701bfab9d1a726f868edfd32d9`;
- output MCAP SHA-256:
  `5d109e4af441dfcc27d667b98aac6d46d81a0c5ba277f0a7593e288f1fad98bf`.

The autonomous review output initially selected transport ID 1. An ID-labelled
contact sheet shows ID 1 following the striped-shirt woman and another ID
following the man carrying the laptop, but the capture provenance does not
state which physical person Francisco predeclared as target. Therefore ID 1 is
not accepted as physical identity. The `/tracks` freeze is valid and final;
the single selected-track-ID decision remains for Francisco. Future TIM replay
must use `--raw-target-mode selected_id` with the human-confirmed transport ID.

## Appearance-only conditions

Batch provenance:

`bags/replay/p064_gate2_hd_master_r3_appearance/p064_appearance_variants.json`

SHA-256:
`d47f57ef38c775433d0202e843112e840cf9451e4d0a7350e0d47f3114eccaa6`.

Both conditions contain all 923 positive-header source images and share exact
timestamp SHA-256
`96f3785974c798379f48d8a35f09457beb0256ddfac5e93526a8513be50c03f8`.
No detector was rerun.

| condition | path | class | image-stream SHA-256 | MCAP SHA-256 |
| --- | --- | --- | --- | --- |
| native 1280x720 | `bags/replay/p064_gate2_hd_master_r3_appearance/1280x720` | same_size | `b0ad9f693544660fe40f95f9261b89878823337f406817f5b724cca45a8aa5c8` | `3b191796b287d18b2bdafb3592e655b6fb7f34be4a12e95ea071ea862c7b9236` |
| control 640x360 | `bags/replay/p064_gate2_hd_master_r3_appearance/640x360` | downsample, INTER_AREA | `2c71b4ddba2a280d312c17407041f4b8228f3ce0fb8ea728041f6983ca53176d` | `1c300a69fcdf314cf248d630ea817ad4dea026e9f53fee6796401469577d8cbd` |

Both preserve complete 16:9 FOV with no crop, padding, letterbox, or upsampling.

## CVAT package

Pi workspace:

`artifacts/reports/p064_gate2_hd_master_r3_cvat/`

Transfer archive:

`p064_gate2_hd_master_r3_cvat_images.zip`

- 837 lossless native 1280x720 PNGs;
- filenames `frame_000000.png` through `frame_000836.png`;
- manifest preserves original image indices 85 through 921;
- archive SHA-256:
  `5ef0a238b52ddc0294db9efe937f36f366809a04dd5391e179271e8d32ce123e`;
- manifest SHA-256:
  `afa136a6a9d6ca2dfbe3adee28bb5569bff3fd54cee03fef24fc96b058a61c65`;
- one label, `person`;
- immutable select attribute `physical_ref`;
- allowed roles exactly `target`, `phys_d001`;
- no seed annotations;
- expected export: CVAT for images 1.1.

The CVAT bridge now accepts an optional exact source-header origin and nonzero
evaluation window in a preparation config. Existing whole-bag Seq01/May
behavior is unchanged. The R3 conversion config intentionally has no semantic
intervals and fails closed until Francisco completes human review, including
the target-absent interval.

## Deferred deterministic TIM commands

Do not execute these until Francisco confirms which displayed person/transport
track is the predeclared target and returns the completed CVAT export. Replace
`<CONFIRMED_TARGET_TRACK_ID>` with that human-confirmed transport ID.

Native HD:

    python3 tools/experiments/run_deterministic_tim_replay.py \
      bags/replay/p064_gate2_hd_master_r3__bytetrack_frozen \
      bags/replay/p064_gate2_hd_master_r3__tim_native_1280x720 \
      --config ros2_ws/src/thesis_bringup/config/tim_mars_canonical.yaml \
      --model models/reid/mars-small128.pb \
      --selected-track-id <CONFIRMED_TARGET_TRACK_ID> \
      --raw-target-mode selected_id \
      --image-topic /camera/image_raw \
      --tracks-topic /tracks \
      --appearance-bag bags/replay/p064_gate2_hd_master_r3_appearance/1280x720 \
      --appearance-image-topic /camera/image_raw \
      --expected-candidate-stream-sha256 23e7388edd50e341ef325efef30de45a70cb59701bfab9d1a726f868edfd32d9 \
      --image-width 1280 --image-height 720 \
      --compact-output

Aspect-matched low-resolution control:

    python3 tools/experiments/run_deterministic_tim_replay.py \
      bags/replay/p064_gate2_hd_master_r3__bytetrack_frozen \
      bags/replay/p064_gate2_hd_master_r3__tim_control_640x360 \
      --config ros2_ws/src/thesis_bringup/config/tim_mars_canonical.yaml \
      --model models/reid/mars-small128.pb \
      --selected-track-id <CONFIRMED_TARGET_TRACK_ID> \
      --raw-target-mode selected_id \
      --image-topic /camera/image_raw \
      --tracks-topic /tracks \
      --appearance-bag bags/replay/p064_gate2_hd_master_r3_appearance/640x360 \
      --appearance-image-topic /camera/image_raw \
      --expected-candidate-stream-sha256 23e7388edd50e341ef325efef30de45a70cb59701bfab9d1a726f868edfd32d9 \
      --image-width 1280 --image-height 720 \
      --compact-output

The 1280x720 values are the master coordinate system for both runs. Only the
appearance bag differs; the existing attachment code maps master boxes into the
actual 640x360 appearance image.

## Corrected export resolution

Francisco corrected frames 0--7 and returned a second CVAT export. Full
validation then passed with complete target and distractor coverage on all 837
frames. The authoritative outcome and provenance are recorded in
`docs/results/selected_target_tracking/p064_gate2_resolution_evaluation.md`.
