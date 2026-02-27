# Artefacts — W08 (2026-02-17 to 2026-02-23)

## Code (paths only)
- `infer_service/detection_zmq.py`
- `infer_service/zmq_pub.py`
- `host_client/sort_tracker.py`
- `host_client/client_tester.py`

## Key configs / paths
- HEF: `/root/thesis_service/resources/hefs/yolov6n_hailo8.hef`
- Postprocess SO: `/usr/lib/aarch64-linux-gnu/hailo/tappas/post_processes/libyolo_hailortpp_post.so`
- Container name: `pi-ai-kit-ubuntu-hailo-ubuntu-pi-1`
- ZMQ port: `5555`, topic: `b"dets"`, `CONFLATE=1`

## Repro commands (copy-paste)
```bash
# Start inference service (inside container)
cd /root/thesis_service
python3 infer_service/detection_zmq.py

# Test from host
python3 host_client/client_tester.py
```
