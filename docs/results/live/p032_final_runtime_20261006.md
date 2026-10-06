# #32 final mounted runtime and resource characterisation — 6 October 2026

Last reviewed: 2026-10-06

Run `2026-10-06__14-52-31` / `p032_final_mounted_vga`, retained bag `bags/live_camera/2026-10-06__14-52-31__video__p032_final_mounted_vga` on the Pi. Template left untouched: `docs/results/live/templates/p032_final_runtime.md`. Raw outputs, statistics and scripts: `docs/data/p032_final_20261006/`.

## 1. Scope and provenance

| Item | Value |
| --- | --- |
| Scenario | Pi mounted as in flight, camera and Hailo live, Pixhawk connected, **aircraft disarmed and stationary**, one operator in view and moving, controller commanding to MAVROS but not actuating |
| Controller | **Baseline** (recovery disabled), the policy retained by #50: `yaw_kp=0.60`, `max_yaw_z=0.20`, `max_delta_yaw_z=0.03`, `invert_yaw=true` |
| Command | `./tools/start_live_stack.sh --res vga --field-record --control-mavros --tag p032_final_mounted_vga`; measurement `tools/issues/p032/measure_p032_live_resources.py --architecture-groups detector,tracker,tim,controller --duration-s 1260 --warm-up-s 60` |
| Software | commit `00c120e9054b37658ebf91effd5890bde1786428`, clean tree; canonical TIM-MARS; detector YOLOv8s HEF `69540ff8…c17ec43b` (direct Hailo); appearance model `mars-small128.pb` `e96f3cc0…d5f1`; ByteTrack |
| Platform | Raspberry Pi with Hailo, 8 GB RAM, Ubuntu 24.04.4, kernel `6.8.0-1065-raspi`, ROS Jazzy, HailoRT CLI 4.23.0; flight software reported by MAVROS `040603ff` |
| Target | track ID 4 (the operator), selected at 13:54:13 UTC; no authority change during the run (two authority events: startup, selection) |
| Window | 60 s warm-up + 1200 s active = 1260.0 s, 13:54:16 → 14:15:16 UTC; trial closed 14:17:21 UTC; bag duration 1456.5 s |

## 2. Results

Receive-time statistics inside the bounded window (`p032_bounded_window_stats.json`); resource figures from the sampler analysis. "Post-warm-up" excludes the first 60 s.

| Metric | Full bounded 1260 s | Post-warm-up 1200 s |
| --- | --- | --- |
| Detector cadence (`/timing`) | 27.82 Hz; gap p50/p95/p99/max 34.4 / 52.8 / 69.6 / **413.7** ms | 27.81 Hz; 34.5 / 52.7 / 69.5 / 413.7 ms |
| Detector latency `e2e_det` p50/p95/p99/max | 34.6 / 66.7 / 79.7 / 136.8 ms | 34.6 / 66.9 / 79.5 / 136.8 ms |
| Tracker cadence and gaps | 27.81 Hz; 34.6 / 55.6 / 71.0 / 109.5 ms | 27.80 Hz; 34.7 / 55.6 / 70.9 / 109.5 ms |
| Tracker latency `track_ms` | 6.9 / 14.1 / 20.2 / 56.1 ms | 6.9 / 14.1 / 20.2 / 56.1 ms |
| **Validated-target cadence** (`/timing_target`) | **27.81 Hz**; gap 27.3 / 120.8 / 140.6 / 328.8 ms | 27.80 Hz; 27.3 / 120.8 / 140.8 / 328.8 ms |
| **Camera-to-validated-target latency** p50/p95/p99/max | 70.0 / **142.2** / 168.6 / 350.7 ms | 70.2 / **142.4** / 169.1 / 350.7 ms |
| Controller command cadence (`/control_ref/cmd_vel`) | 29.99 Hz; gap 33.4 / 40.0 / 45.0 / 80.5 ms | 29.99 Hz; same |
| Controller mode over the whole diagnostics span (1455.7 s) | NORMAL_FOLLOW 1286.1 s (88.4 %), HOVER 169.6 s | n/a |
| Selective ReID (whole bag, 1454 s) | 5,144 backend calls (3.54 /s), 5,152 embeddings requested and returned valid; backend wall mean 84.8 ms, p95 103.5, p99 125.1, max 290.1 ms | n/a |
| Appearance cache (whole bag) | 35,515 lookups: 35,310 hits (**99.4 %**), 201 misses, 4 expired, 0 invalidated; accounting identities pass | n/a |
| Core CPU, detector + tracker + TIM + controller | mean 268.3 % of 400 % (p95 283.0, max 296.8) | mean 268.4 % (p95 283.0, p99 287.0) |
| Core RSS (sum) | mean 1,346,260 KiB (max 1,359,120) | mean 1,346,869 KiB (p95 1,358,792) |
| By group, post-warm-up (CPU % / RSS KiB) | detector 47.0 / 223,392 · tracker **180.0** / 142,600 · TIM 30.1 / 873,121 · controller 11.3 / 107,756 | same |
| System memory available | mean 5,903,673 KiB (min 5,844,620) of 8,127,684 | mean 5,903,416 KiB |
| Temperature | 67.0–71.4 °C, mean 69.4 | mean 69.5, p95 70.8 |
| ARM clock | 2.400 GHz throughout (min 2,400,017,408 Hz) | same |
| Throttle state | constant `0x80000` in all 251 samples | same |
| Hailo contention/utilisation | **unavailable** (no direct reproducible measurement) | unavailable |
| Electrical power | **unavailable**; core voltage 0.895 V is telemetry, not power | unavailable |
| Recorder transport | **observed zero** loss; separate visual file finalised gracefully | n/a |

**Throttling investigated.** `0x80000` is the sticky "soft temperature limit has occurred since boot" bit. It was already set in the first sample of the run and is also set outside the run. All "currently throttled" bits (0x1, 0x2, 0x4, 0x8) are clear in every sample, and the ARM clock never left 2.4 GHz, so no active throttling or frequency capping was observed. The temperature was stable (std 0.8 °C) and reached 71.4 °C at most.

## 3. Acceptance, requirement by requirement

| Requirement | Result |
| --- | --- |
| Complete 20-minute active interval | **met**: 1260.0 s observed, 60.0 s warm-up excluded |
| No `/mavros/state` sample in the trial reporting disconnected or armed | **met**: 1,388 in-trial samples, 0 armed, 0 disconnected (77 outside the trial, also none) |
| Validated-target rate at least 10 Hz (15 Hz desired) | **met**: 27.8 Hz |
| p95 camera-to-validated-target at most 200 ms | **met**: 142.2 ms (p99 168.6 ms, max 350.7 ms) |
| No unexplained resource-root loss | **met**: sampler integrity pass, 0 sample errors, process-tree gaps at most 1.0 s, hardware gaps at most 5.13 s for a 5 s interval |
| Zero unacceptable recorder transport loss | **met**: observed zero |
| Investigate any throttling | **done**, see above |
| Hailo utilisation and electrical power | reported **unavailable** |
| `verify_field_run.sh ... --control-trial --disarmed-runtime-characterization` | **FAILED, run kept**: see below |

**The failed verification check.** The evidence package verifier and the disarmed-scope check pass (`complete_runtime_evidence`, no problems). The wrapper exits non-zero because `assess_bag_topics.py` fails its command/diagnostic and command/MAVROS-mirror pairing: 2 of 43,662 `/control_ref/cmd_vel` messages have no matching diagnostic or mirror message, while all 43,660 pairs match with 0 value mismatches. The two messages are the first two in the bag (13:53:06.623 and .637 UTC, both all-zero commands), 67 s before target selection and outside the trial interval. The assessor tolerates exactly one leading zero sample; this run had two. The same check also failed on the 2 October compute-only run (11 unpaired), so it is a controller start-up race, not a new defect. The check was not altered and the run was not repeated.

## 4. What this supports and what it does not

Permitted claim: on the Raspberry Pi with Hailo at VGA, the retained baseline controller sustained a validated-target output of 27.8 Hz with p95 142 ms camera-to-validated-target latency, using about 2.7 of 4 CPU cores and 1.35 GB for the four measured process groups, at about 70 °C with no active throttling, over a complete 60 s + 1200 s interval with the aircraft disarmed and stationary.

Withheld or qualified:

- **One scene, one person.** The 99.4 % appearance-cache hit rate and 3.5 backend calls per second reflect a single visible person. Crowded or distractor scenes cost more (earlier matched replays: p95 about 190–205 ms in crowded VisDrone scenes).
- **Not a flight condition.** The aircraft was disarmed and stationary: no vibration, airflow, battery draw or actuation, so the thermal and power picture is that of a ground bench with the Pi mounted. Controller commands were produced but not executed.
- **Bounded-window versus whole-bag figures.** Latency, cadence and resources are bounded-window; the ReID workload and controller mode occupancy cover the whole bag (1454–1456 s).
- **Detector stall.** One detector inter-arrival gap of 413.7 ms and a target-output gap of 328.8 ms occurred in the window; the validated-target gap distribution is bursty (p95 120.8 ms against p50 27.3 ms), consistent with the roughly 85 ms synchronous appearance call; the timing analyser reports gap_count 0 and dropped_samples 0.
- **Tracker group CPU.** The tracker process group averaged 180 % CPU although `track_ms` p95 is only 14 ms (about 0.2 core at the 7.4 ms mean and 0.4 core at p95, at 28 Hz), and replay measurements gave about 0.03 CPU-s per frame. The cause is not diagnosed here (the group's two members are the `ros2 run` launcher and the node); it is the largest CPU consumer and a candidate for efficiency work.
- **Hailo utilisation and electrical power** are unmeasured, not zero.
- **Recorder and UI overhead** were present (field profile, structured MCAP plus MJPEG recorder, dashboard bridge) but sit outside the four-group core sum; no browser dashboard session was attached.

## 5. Hand-off

Insert into Report #22 and Code #39 as the final runtime table, with the qualifications above. This closes the measurement requirement of #32 for the baseline controller; the failed wrapper check and the unmeasured Hailo and power quantities stay disclosed limitations.
