# Daily Log — 2026-02-22 — Host SORT Tracker

## Goal
- Keep the Pi perception pipeline stable and reproducible.
- Build the host-side tracking layer and validate ID stability in real time.
- Add basic health telemetry (Pi CPU temperature) for flight-readiness.

**Done today (fill):** Service stable + host SORT baseline + runtime notes: `___`

---

## Context

| Key | Value |
|-----|-------|
| Hardware | Raspberry Pi 5 + AI HAT+ (Hailo) + Pixhawk 4 (ArduPilot) + F9P GNSS *(camera not connected)* |
| Host OS | Ubuntu 24.04, ROS 2 Jazzy, Docker |
| Repo / compose | `~/pi-ai-kit-ubuntu` → `docker-compose.yaml` |
| Container | `pi-ai-kit-ubuntu-hailo-ubuntu-pi-1` |
| Network mode | `host` — client connects to `127.0.0.1:5555` |
| Test input | `/root/hailo-rpi5-examples/resources/example_640.mp4` |
| ZMQ topic | `b"dets"` |
| Payload | `seq`, `frame_id`, `pts_ns`, `t_pub`, `dets[]` (normalised xywh) |

---

## Work Done

### A) Service boundary robustness (container)
- Fixed `HAILO_LOOP_VIDEO` being forced to `0` by `run_detection_zmq.sh`.
- Cleaned `run_detection_zmq.sh` so it actually executes the intended command (removed unreachable lines after `exec`).
- Fixed script formatting issues (shebang / line endings problems during edits).
- Confirmed ZMQ publisher is live with a raw SUB test (`recv_multipart` returns `topic=b"dets"` and non-empty payload).

### B) Host client (ZMQ) reliability
- Implemented "drain-to-latest" receive pattern to avoid backlog without using `CONFLATE` (which caused SUB timeouts on this setup).
- Added receive timeout handling and rate-limited timeout logs.
- Added sliding-window latency stats (deque, last ~10s) to avoid averages being dominated by early spikes.

### C) Tracking layer progression
- Implemented baseline IoU tracker, then replaced with SORT (Kalman + assignment).
- Upgraded SORT association from greedy IoU to Hungarian assignment (SciPy if available, greedy fallback otherwise).
- Added centre-distance gating in the cost matrix to reduce matching compute in crowded frames.
- Exposed `tracker.last_match_ms` and printed it for runtime visibility.

### D) Telemetry
- Added Pi CPU temperature read via sysfs in host client.
- Reduced telemetry frequency (2s) to lower overhead during runtime tests.

---

## Results

### Current observed behaviour (host client)
- Typical receive rate: ~30 Hz, but intermittent dips to ~20–25 Hz.
- Typical pub→sub latency: ~3–5 ms average (sliding window), with occasional spikes (max ~25–45 ms).
- Hungarian assignment cost: typically ~0.08–0.30 ms, so matching is not the cause of rate dips.
- Baseline run used: `--iou 0.18 --max_age 4 --min_hits 3 --min_score 0.35 --print_every 60`

### Fields to record for the day
- RX rate: `~19.9 / ~28–29 / ~30.6 Hz` (min/avg/max over run)
- Pub→sub latency: `~0.35 / ~3.5–4.5 / ~43.1 ms` (min/avg/max over sliding window)
- Tracker:
  - mean `tracks` vs `dets`: ~1.1× (typically dets = tracks or +1 to +2)
  - stability notes (rough): Mostly stable IDs, occasional track inflation when dets spike (busy frames), recovers quickly.
- Matcher runtime:
  - `match_ms` avg/max: `~0.18 ms / ~1.33 ms` (typical 0.08–0.30 ms)
- Thermals:
  - Pi temp range: `~48.5 °C` to `~53.5 °C`
- Stall attribution (from `pts_dt_ms`): `unclear (not measured yet)`

---

## Blockers / Issues
- `CONFLATE` on SUB caused receive timeouts in this environment, replaced with drain-to-latest.
- Intermittent host-side rate dips still present (not explained by matcher cost).
- AI HAT+ device stats (`hailodevicestats`) not supported, temperature is Pi-only for now.

---

## Next Actions

### Immediate (runtime diagnosis)
- [ ] Add `pts_dt_ms(avg/max)` from successive `pts_ns` to separate server vs client stalls.
- [ ] Add `gc.disable()` in `main()` **and** reduce telemetry to 5s in the same run; compare Hz dips and max latency.
- [ ] Re-run baseline for 3 min with both changes active.
- [ ] If dips persist: add per-stage timing (`recv`, `json`, `track`, `loop`) p95.

### Pipeline progression
- Lock "stable host baseline" params:
  - `iou ~0.18`, `max_age 4`, `min_hits 3`, `min_score 0.35`.
- Add JSONL record mode:
  - raw messages + derived tracks for replay and offline debugging.
- Start ByteTrack integration after SORT baseline is stable and measured.

---

## Key Commands

```bash
# Container: run service (looping for service-style testing)
export HAILO_VIDEO_SINK=fakesink
export HAILO_LOOP_VIDEO=1
cd /root/thesis_service
./run_detection_zmq.sh

# Host: confirm publisher + port
ss -ltnp | grep 5555 || true

# Host: raw receive sanity check
python3 - <<'PY'
import zmq, json
ctx = zmq.Context.instance()
s = ctx.socket(zmq.SUB)
s.setsockopt(zmq.SUBSCRIBE, b"dets")
s.connect("tcp://127.0.0.1:5555")
topic, payload = s.recv_multipart()
msg = json.loads(payload.decode())
print("OK topic:", topic, "frame_id:", msg.get("frame_id"), "n_dets:", len(msg.get("dets", [])))
PY

# Host: run client tester baseline
./client_tester.py --addr tcp://127.0.0.1:5555 --topic dets --w 640 --h 640 \
  --iou 0.18 --max_age 4 --min_hits 3 --min_score 0.35 --print_every 60
```

---

## Environment Snapshot

| Component | Version / Value |
|-----------|----------------|
| Kernel | `6.8.0-1047-raspi` |
| Hailo driver | `hailo_pci 4.20.0` |
| Hailo firmware | `hailo8_fw 4.20.0` |
| HailoRT (container) | `4.20.0` |
| tappas-core (container) | `3.31.0+1-1` |
| Apps Infra | `25.7.0` |
| Container name | `pi-ai-kit-ubuntu-hailo-ubuntu-pi-1` |
| Network mode | `host` (client: `127.0.0.1:5555`) |
| Service output | ZMQ dets JSON payload |
| Tracking | SORT (Kalman + Hungarian IoU matching with gating) |
| ZMQ backlog control | drain-to-latest (no `CONFLATE`) |
