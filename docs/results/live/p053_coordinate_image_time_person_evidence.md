# P0.26 physical-person coordinate/image-time evidence

Date: 22 July 2026

Issue: [#53](https://github.com/FRCTavares/IST-Thesis-Code/issues/53)

## Result

PASS. A control-disabled Raspberry Pi 5 run recorded a physical person through
the integrated Hailo detector, DeepSORT, TIM-MARS, the live dashboard, and the
saved-bag overlay renderer. Detector, tracker, TIM appearance crop, live target,
dashboard, and saved-overlay coordinates all referred to the same source-frame
person.

## Provenance

- repository commit at capture: `13ec3af067bb4f98150a73ac87fee80a561b366b`
- coordinate/image-time implementation: `cfe85cbc`
- earlier no-person reboot evidence: `9be637ce`
- command:

  ```bash
  LIVE_STACK_VERBOSE=1 ./tools/start_live_stack.sh \
    --record \
    --tag p026_coordinate_contract_person \
    --tracker deepsort \
    --no-control \
    --dash 10
  ```

- retained bag:
  `/home/francisco/Desktop/Thesis-Code/bags/live_camera/2026-07-22__17-33-42__video__p026_coordinate_contract_person`
- runtime logs:
  `/home/francisco/Desktop/Thesis-Code/ros2_ws/log/live_stack/2026-07-22__17-33-42`
- source/inference contract:
  `tim_mars_source_pixels_resize_v1;source=640x480;inference=640x640;scale=1,1.33333333;pad=0,0`
- frozen metadata: integrated camera, Hailo `yolov6n`, DeepSORT,
  `control_enabled=0`, runtime reconfiguration disabled

## Recorded evidence

`ros2 bag info` reported:

- duration: `579.331644024 s`
- size: `2.1 GiB`
- messages: `99,660`
- `/camera/dashboard`: 2,361
- `/detections`: 17,234
- `/tracks`: 10,539
- `/target_memory_mars`: 10,424
- `/target_memory_mars/status`: 10,424
- `/timing`: 17,221
- `/timing_tracker`: 10,539
- `/timing_target`: 10,459

The recorder requested `/control_ref/cmd_vel`, but the topic had no messages
because the run used `--no-control`. Shutdown was clean, the runtime-log error
scan was empty, and no stack process remained.

## Same-person coordinate and appearance checks

A synchronized live sample for selected target 13 showed:

- detector source-frame box: centre `(412.750, 252.656)`, size
  `211.126 x 363.518`, confidence `0.8797`
- DeepSORT source-frame box: centre `(288.493, 253.070)`, size
  `239.585 x 377.597`, confidence `0.8870`
- locked TIM target source-frame box: centre `(334.510, 284.186)`, size
  `166.012 x 316.336`, confidence `0.8972`, quality `0.9511`
- TIM state: `LOCKED`, `visible=true`, `target_track_id=13`,
  `candidate_track_id=13`, freshness `fresh`
- causal image attachment: selected image and track timestamps differed by
  `97.541307 ms`; the selected image was not from the future
- TIM appearance crop for track 13: `169.962 x 318.390 px`, clipping fraction
  `0.0`, encoding eligible, memory-update eligible, no rejection reasons
- appearance status: one valid feature, lineage trusted, crop/image age
  `97.541307 ms`, skip reason `ok`

All boxes were inside the canonical 640x480 source frame. The modest box-size
differences are expected between detector, filtered tracker state, and TIM target
state; their centres and visible extents remained on the same person.

## Visual checks

### Live dashboard

The repository frontend was run temporarily on the operator Mac because the Pi
does not currently have npm installed. It consumed the Pi's live WebSocket, API,
and MJPEG stream without altering the runtime. The captured dashboard frame
showed the physical person with an aligned `TIM TARGET 23` box and simultaneously
reported `TARGET 23`, `Track 23 ACTIVE`, raw target 23, and TIM target 23.

The screenshot is retained beside the bag as
`p053_live_dashboard_target23.png`; it is deliberately not committed because it
contains an identifiable participant. The dashboard's stale tracker-selector
label is a separate UI configuration-reporting defect already owned by Issue
#55; the frozen run metadata and launch output confirm that this evidence run
used DeepSORT.

### Saved-bag overlay

Renderer command:

```bash
python3 tools/bag/render_bag_overlay_video.py "$BAG" \
  --output "$BAG/p053_person_overlay.mp4" \
  --target-topic /target_memory_mars \
  --draw-detections \
  --max-frames 850
```

The renderer wrote 850 frames at 640x480. Frames retained as
`p053_overlay_94s.jpg`, `p053_overlay_96s.jpg`, `p053_overlay_100s.jpg`,
`p053_overlay_105s.jpg`, and `p053_overlay_110s.jpg` show the yellow
`TARGET 13` box aligned to the same physical person while the HUD reports
`target_id=13` and `visible=1`. The full retained artifact is
`p053_person_overlay.mp4`.

## Software validation inherited by this evidence run

The evidence run used the already committed and clean software contract. Its
focused coordinate/causality/overlay tests, tracker suite, bringup suite, tools
suite, two-package build, and `git diff --check` had passed before capture. The
current aggregate bringup result after the subsequent freshness work is 205
passed, 1 skipped, and 3 expected failures.

## Conclusion

The remaining physical-person integration and visual acceptance gates in Issue
#53 are satisfied. The versioned source-pixel coordinate contract and causal
image selection are fit to unblock the flight-readiness work in Issue #50.
