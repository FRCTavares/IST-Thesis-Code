# Daily Log — 2026-02-21

## Goal

Stabilise the end-to-end Pi detection service boundary on Pi 5, running the real Hailo GStreamer pipeline on an MP4 and streaming results over ZMQ to the host client, with reproducible commands and timestamped messages.

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

---

## Work Done

**Pipeline and outputs**
- Detections extracted and published: `hailo.get_roi_from_buffer` + `HAILO_DETECTION` now populates `dets` with `{label, score, x, y, w, h}` (normalised).
- Verified end-to-end on host: non-empty detections received (`n_dets=11`, `label='person'`, score ~0.90+).

**Reproducibility and service behaviour**
- Fixed apps-infra default resource paths via symlinks under `/usr/local/hailo/resources/...` pointing to `/root/hailo-rpi5-examples/resources/`.
- Service-style MP4 runs: patched apps-infra EOS handler to support `HAILO_LOOP_VIDEO=0` (clean exit, no rewind spam).
- Deterministic cadence: `batch_size=1` set in `detection_pipeline_simple.py` (confirmed in printed pipeline).
- Import cleanup: `detection_zmq.py` uses `from zmq_pub import ZmqPublisher`.
- Patched files:
  - `.../core/gstreamer/gstreamer_app.py` — `on_eos()` supports `HAILO_LOOP_VIDEO=0`
  - `.../apps/detection_simple/detection_pipeline_simple.py` — `batch_size=1`

---

## Results

- Pi detection service boundary fully functional: real Hailo pipeline → ZMQ → host, with real detections.
- Payload fields: `seq`, `frame_id`, `pts_ns`, `t_pub`, `dets`.
- `dets` schema: list of `{label:str, score:float, x:float, y:float, w:float, h:float}` in normalised coordinates.
- Clean single-pass MP4 execution with `HAILO_LOOP_VIDEO=0`.
- Observed on `example_640.mp4`: ~145–150 FPS unthrottled (`fakesink`), ~30 Hz with framerate caps. Pub→sub latency ~0.5–2 ms.

---

## Blockers / Issues

- `hailodevicestats` unsupported on AI HAT+ (power measurement opcode missing).
- Temperature monitoring not implemented yet.

---

## Next Actions

- Host: add tracker stub (IoU matching), then SORT or ByteTrack.
- Host: convert normalised bboxes to pixel coords (640×640).
- Host: clean Ctrl-C + latency stats (`t_rx`, `pub_to_sub_ms`).
- Device: temperature monitoring via sysfs or `hailortcli`.

---

## Key Commands

```bash
# Run service (container)
export HAILO_VIDEO_SINK=fakesink
export HAILO_LOOP_VIDEO=0
cd /root/thesis_service
./run_detection_zmq.sh

# Host one-shot validation
python3 - <<'PY'
import zmq, json
ctx = zmq.Context.instance()
s = ctx.socket(zmq.SUB)
s.setsockopt(zmq.SUBSCRIBE, b"dets")
s.connect("tcp://127.0.0.1:5555")
topic, payload = s.recv_multipart()
msg = json.loads(payload.decode())
print("n_dets:", len(msg.get("dets", [])))
print("sample:", msg.get("dets", [])[:2])
PY

# Confirm batch size
python3 /root/thesis_service/detection_zmq.py | grep -o "batch-size=[0-9]*" | head -n 1
```

---

## Appendix — Setup Commands (one-time)

```bash
# Fix hailonet SONAME mismatch
ln -sf /lib/libhailort.so.4.20.0 /lib/libhailort.so.4.17.0 && ldconfig

# Install TAPPAS core
apt-get install -y pkg-config hailo-tappas-core

# Download HEFs
cd /root/hailo-rpi5-examples && ./download_resources.sh --all

# Symlink YOLO postprocess lib
mkdir -p /usr/local/hailo/resources/so
ln -sf /usr/lib/aarch64-linux-gnu/hailo/tappas/post_processes/libyolo_hailortpp_post.so \
  /usr/local/hailo/resources/so/libyolo_hailortpp_postprocess.so && ldconfig

# Symlink apps-infra default resource paths
mkdir -p /usr/local/hailo/resources/models/hailo8 /usr/local/hailo/resources/videos
ln -sf /root/hailo-rpi5-examples/resources/yolov6n.hef \
  /usr/local/hailo/resources/models/hailo8/yolov6n.hef
ln -sf /root/hailo-rpi5-examples/resources/example_640.mp4 \
  /usr/local/hailo/resources/videos/example_640.mp4

# Create /root/.env as root
tee /root/.env >/dev/null <<'ENV'
hailort_version=4.20.0
tappas_version=3.31.0
model_zoo_version=v2.14.0
host_arch=rpi
hailo_arch=hailo8
server_url=http://dev-public.hailo.ai/2025_01
tappas_variant=tappas-core
resources_path=/root/hailo-rpi5-examples/resources
virtual_env_name=venv_hailo_rpi_examples
tappas_postproc_path=/usr/lib/aarch64-linux-gnu/hailo/tappas/post_processes
ENV
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
| Hailo Apps Infra | `25.7.0` |
| HEFs location | `/root/hailo-rpi5-examples/resources/*.hef` |
| Postprocess libs | `/usr/lib/.../hailo/tappas/post_processes/` |
| Postprocess symlink | `libyolo_hailortpp_postprocess.so` → `libyolo_hailortpp_post.so` |
| Container name | `pi-ai-kit-ubuntu-hailo-ubuntu-pi-1` |
| Network mode | `host` (client: `127.0.0.1:5555`) |
| ZMQ topic | `b"dets"` |
| Payload fields | `seq`, `t_pub`, `pts_ns`, `frame_id`, `dets` |
| `HAILO_LOOP_VIDEO=0` | Supported via apps-infra patch (clean EOS exit) |
| Inference batch size | `1` (patched `detection_pipeline_simple.py`) |
