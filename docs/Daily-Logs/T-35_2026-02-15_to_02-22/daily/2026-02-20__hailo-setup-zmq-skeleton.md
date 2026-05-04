# Daily Log — 2026-02-20

## Goal

Lock down a stable Hailo setup on Pi 5 (Ubuntu 24.04) and start a Pi detection service boundary skeleton using an MP4 (no camera yet).

---

## Context

| Key | Value |
|-----|-------|
| Hardware | Raspberry Pi 5 + AI HAT+ (Hailo) + Pixhawk 4 (ArduPilot) + F9P GNSS *(camera not connected)* |
| Host OS | Ubuntu 24.04, ROS 2 Jazzy, Docker |
| Repo / compose | `~/pi-ai-kit-ubuntu` → `docker-compose.yaml` |
| Container | `pi-ai-kit-ubuntu-hailo-ubuntu-pi-1` |
| Network mode | `host` — `ports:` ignored; client connects to `127.0.0.1:5555` |
| Test input | `/usr/local/hailo/resources/videos/example_640.mp4` |

---

## Work Done

**Host setup**
- Installed missing kernel headers; built and installed `hailo_pci` driver (4.20.0).
- Downloaded and set firmware symlink to 4.20.0.
- Verified `/dev/hailo0` present (`crw-rw---- root hailo`); `dmesg` confirms driver 4.20.0.
- Fixed `apt update` (disabled broken VSCode repo key) and Docker conflicts (containerd).

**Container and baseline inference**
- Ran `hailo-rpi5-examples` install: created venv, installed infra deps, downloaded resources.
- Benchmarked `detection_simple` on MP4 with `timeout 10s` fixed-duration runs.
- Confirmed `hailortcli scan` shows device inside container.

**Service boundary skeleton**
- Installed `python3-zmq` inside container and on host.
- Created `/root/thesis_service/infer_server.py` to PUB detections on port 5555.
- Fixed `ModuleNotFoundError: No module named 'basic_pipelines'` — must `cd /root/hailo-rpi5-examples && source ./setup_env.sh` before any pipeline call.

---

## Results

- Hailo device recognised on host and inside container; inference runs on MP4.
- Observed on `example_640.mp4` (`timeout 10s`, `--disable-sync`, `--frame-rate 30`):

  | Model | Input | Avg FPS |
  |-------|-------|---------|
  | `yolov6n.hef` | 640 | ~17.2 |
  | `yolov8m.hef` | 640 | ~16.6 |

- EOS rewind artefacts appear without `timeout` — use it for benchmarking.
- Do not Ctrl+Z a running pipeline (holds the Hailo device).

---

## Blockers / Issues

- Service boundary **not yet verified end-to-end**: `infer_server.py` created but publishing not confirmed; `client_tester.py` not yet created.
- Server must bind to `0.0.0.0:5555`; client subscribes to `127.0.0.1:5555`.
- Camera integration postponed (CSI ribbon cable not yet delivered).

---

## Next Actions

- Container: confirm `infer_server.py` runs and publishes messages.
- Host: create and run `client_tester.py`; verify RX rate and pub→sub latency.
- Host: confirm port 5555 is listening while server runs (`ss -ltnp | grep 5555`).
- Host: remove accidental `docker-compose.yml`; use `docker compose -f docker-compose.yaml` consistently.

---

## Key Commands

```bash
# Host: fix compose file and start container
cd ~/pi-ai-kit-ubuntu
rm -f docker-compose.yml
docker compose -f docker-compose.yaml up -d hailo-ubuntu-pi
docker compose -f docker-compose.yaml exec hailo-ubuntu-pi bash

# Container: baseline inference benchmark
cd /root/hailo-rpi5-examples && source ./setup_env.sh
timeout 10s python3 -m basic_pipelines.detection_simple \
  --input /usr/local/hailo/resources/videos/example_640.mp4 \
  --hef-path /usr/local/hailo/resources/models/hailo8/yolov6n.hef \
  --show-fps --disable-sync --frame-rate 30

# Container: service skeleton checks
chmod +x /root/thesis_service/infer_server.py
python3 -m py_compile /root/thesis_service/infer_server.py && echo OK
python3 -u /root/thesis_service/infer_server.py

# Host: port check
ss -ltnp | grep 5555 || true
```

---

## Environment Snapshot

| Component | Version / Value |
|-----------|----------------|
| Kernel | `6.8.0-1047-raspi` |
| Hailo driver | `hailo_pci 4.20.0` |
| Hailo firmware | `hailo8_fw 4.20.0` (symlink set) |
| HailoRT (container) | `4.20.0` |
| tappas-core (container) | `3.31.0+1-1` |
| Container name | `pi-ai-kit-ubuntu-hailo-ubuntu-pi-1` |
| Network mode | `host` (`ports:` ignored; client → `127.0.0.1:5555`) |
| Host device | `/dev/hailo0` → `crw-rw---- root hailo` |
| HEFs benchmarked | `yolov6n.hef`, `yolov8m.hef` |
| HEFs available | `yolov8m_pose.hef` |
| Key inference params | `640×640`, `--disable-sync`, `--frame-rate 30`, `timeout 10s` |
