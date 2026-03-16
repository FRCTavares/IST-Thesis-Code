# Upgrade Suggestions

## Objective
Improve robustness, repeatability, and thesis evidence quality while keeping the current lean live stack operational.

## Priority Plan

### P0 (Do Next)

1. Add preflight checks into startup script
- Verify required ROS packages before launch (`web_video_server`, `thesis_*` nodes).
- Verify container is reachable and `detection_zmq.py` starts cleanly.
- Verify camera device availability (`/dev/video0`, `/dev/media0`, `/dev/v4l-subdev2`).
- Fail early with clear messages.

2. Add health summary after startup
- Print one-line status for each service: camera, inference, tracker, selector, bridge, web video.
- Include live checks for ports 5556, 8080, and 8765.
- Include one-shot topic checks for `/camera/image_raw`, `/detections`, `/timing`, `/target`.

3. Make startup script idempotent and safe for reruns
- Detect already-running stack and ask whether to replace it.
- Ensure stale PID cleanup is scoped to this stack only.
- Add lock file to avoid accidental double starts from two terminals.

4. Add dashboard-side connectivity diagnostics
- Add endpoint to show websocket connected/disconnected state.
- Display if video stream URL is reachable.
- Show last telemetry update time and stale warning.

### P1 (This Week)

5. Create a single launch file for full live stack
- New launch in thesis_bringup for camera + inference + tracker + selector + bridge + web video.
- Keep script as operational wrapper, but use launch file as source of truth.

6. Add topic/service readiness wait nodes
- Replace blind sleeps in startup with real readiness checks.
- Start dependent nodes only when prerequisites are active.

7. Harden dashboard bridge node
- Add optional reconnect backoff logging.
- Add payload schema version field.
- Add counters: connected clients, dropped sends, publish frequency.

8. Improve camera pipeline configurability
- Expose operation presets (e.g., `lab`, `outdoor`, `low_light`) for width/height/fps/dashboard size.
- Add explicit option to disable in-node dashboard publish if using separate resize node.

### P2 (After Stability)

9. Add automated smoke test command
- One command that runs stack for 60 seconds and checks:
  - `/camera/image_raw` > 20 Hz
  - `/detections` > 10 Hz
  - `/timing` present and valid
  - web video port open
  - dashboard bridge port open
- Save result to `reports/system/smoke/`.

10. Add regression snapshots for thesis evidence
- Weekly fixed-duration runs with same config.
- Save summary table with p50/p95/p99 for `lat_ms`, `loop_ms`, and detection rate.
- Auto-append to a single longitudinal markdown report.

11. Add structured logging format
- Standard key-value logs for all nodes (`node=`, `event=`, `rate=`, `lat_ms=`).
- Easier parsing into reports.

12. Add recovery strategy for partial failures
- If one node crashes, either auto-restart only that node or cleanly stop all with reason.
- Log restart attempts and last error to run directory.

## Code-Level Suggestions

### Dashboard Bridge
- Keep `_ws_clients` naming (already fixed) to avoid rclpy internals collision.
- Add explicit max payload rate cap and message coalescing under high load.
- Consider sending integer IDs and compact float precision for smaller payloads.

### Inference Client
- If service returns an error JSON, log explicit reason and increment counter.
- Add optional `warn_on_zero_detections_every_n` for field diagnostics.
- Consider optional dynamic resize mode (skip resize if camera already at infer resolution).

### Detection Service
- Add startup log line with effective env config.
- Add heartbeat log every N seconds with processed FPS and queue behavior.
- Add clear response schema (`ok`, `error`, `detections`) consistently in all paths.

## Operations and Documentation

1. Make RUNBOOK the canonical operator path
- Keep one-command startup first.
- Keep manual multi-terminal sequence as fallback.

2. Add a Field Quick Card
- A very short one-page checklist for on-site use:
  - start command
  - expected URLs
  - stop command
  - 5 common failures and fixes

3. Add post-run checklist to script output
- Suggest exact commands to verify bag, copy logs, and annotate notes.

## Metrics to Track Weekly

- Startup success rate (% clean starts without manual intervention)
- Time-to-first-detection (seconds)
- Detection throughput average and p95
- End-to-end latency p50/p95/p99
- Dashboard availability (video + telemetry)
- Number of manual restarts per session

## Suggested Immediate Next 3 Actions

1. Add preflight and startup health summary to `tools/start_live_stack.sh`.
2. Add full live-stack launch file in `thesis_bringup` and keep script as operator wrapper.
3. Add a 60-second automated smoke test and save markdown results to `reports/system/smoke/`.
