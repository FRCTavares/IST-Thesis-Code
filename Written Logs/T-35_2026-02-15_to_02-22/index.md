# T-35 (2026-02-17 to 2026-02-23)

## Outcome (one paragraph)
Hailo inference service was brought up and validated end-to-end on RPi 5.
ZMQ pub/sub transport contract (topic `b"dets"`, port 5555, CONFLATE=1,
`recv_multipart()`) was established. Host-side SORT tracker integrated and
tested; parameters frozen (`iou=0.18`, `max_age=4`, `min_hits=3`,
`min_score=0.35`). ROS 2 Jazzy environment confirmed; initial ROS 2 plan drafted
for T-34.

## Daily logs
- 2026-02-20: [Hailo setup ZMQ skeleton](daily/2026-02-20__hailo-setup-zmq-skeleton.md)
- 2026-02-21: [Hailo ZMQ detections](daily/2026-02-21__hailo-zmq-dets.md)
- 2026-02-22: [Host SORT tracker](daily/2026-02-22__host-sort-tracker.md)
- 2026-02-23: [Stall conflate wall-Hz ROS2 plan](daily/2026-02-23__stall-conflate-wallhz-ros2-plan.md)

## Key artefacts
- HEF: `resources/hefs/yolov6n_hailo8.hef`
- Postprocess SO: `/usr/lib/aarch64-linux-gnu/hailo/tappas/post_processes/libyolo_hailortpp_post.so`
- ZMQ detection schema: `detection_zmq.py`
- SORT tracker: `host_client/sort_tracker.py`

## Decisions locked this week
- Inference isolation: Docker container (`pi-ai-kit-ubuntu-hailo-ubuntu-pi-1`), host networking
- ZMQ transport: PUB/SUB, port 5555, `CONFLATE=1`, `recv_multipart()`, topic `b"dets"`
- SORT params frozen: `iou=0.18`, `max_age=4`, `min_hits=3`, `min_score=0.35`
- HailoRT version locked: 4.20.0-1; tappas-core: 3.31.0+1-1; DKMS driver: hailo_pci 4.20.0

## Next week focus
- [x] Build `thesis_msgs`, `inference_client_node`, `tracker_node`, `target_selector_node`
- [x] First end-to-end ROS 2 slice running
- [x] Record MCAP bags and run timing analysis
