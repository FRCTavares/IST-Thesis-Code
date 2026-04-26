# Weekly Summary — T-35 (2026-02-17 to 2026-02-23)

## Goals for the week
- [x] Stand up Hailo inference service on RPi 5
- [x] Establish ZMQ transport contract
- [x] Integrate host-side SORT tracker
- [x] Draft ROS 2 architecture plan for T-34

## What shipped (bulletproof facts)
- Hailo inference service running in Docker container with DKMS driver locked to 4.20.0.
- ZMQ PUB/SUB protocol established: `recv_multipart()`, topic `b"dets"`, `CONFLATE=1`, port 5555.
- Host SORT tracker integrated (`sort_tracker.py`); parameters frozen.
- Identified and fixed ZMQ stall (CONFLATE flag) and wall-clock Hz discrepancy.
- ROS 2 Jazzy environment confirmed; T-34 node architecture planned.

## Numbers
- Inference: sustained ~30 Hz on yolov6n_hailo8.hef (pre-camera, test video)
- SORT: `iou=0.18`, `max_age=4`, `min_hits=3`, `min_score=0.35` (frozen)

## Issues / risks
- Hailo DKMS driver must stay at 4.20.0; kernel updates will break it — pin kernel.
- tappas postprocess SO path changed between versions — document exact path.

## Next week plan
- [x] Build full ROS 2 slice (thesis_msgs → inference_client → tracker → target_selector)
- [x] Record MCAP bags
- [x] Generate timing baseline

## Links
- Week index: `index.md`
- Artefacts: `artefacts.md`
