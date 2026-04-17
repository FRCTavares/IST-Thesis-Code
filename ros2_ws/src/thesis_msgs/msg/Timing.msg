uint32 seq
uint32 frame_id

# Source/camera metadata
# Preserved source timestamp from image header (if available, else 0).
int64 src_stamp_ns
# Time (monotonic) when inference_client image callback observed this frame.
int64 t_cam_msg_seen_ns
uint32 image_width
uint32 image_height
string image_encoding

# Host-side timestamps (monotonic)
int64 t_pre_start_ns
int64 t_pre_end_ns
int64 t_zmq_send_start_ns
int64 t_zmq_send_end_ns
int64 t_zmq_recv_start_ns
int64 t_zmq_recv_end_ns
int64 t_decode_start_ns
int64 t_decode_end_ns
int64 t_det_pub_start_ns
int64 t_det_pub_end_ns

# Container-side timestamps (monotonic, forwarded by inference reply)
int64 t_req_recv_ns
int64 t_frame_unpack_start_ns
int64 t_frame_unpack_end_ns
int64 t_infer_start_ns
int64 t_infer_end_ns
int64 t_post_start_ns
int64 t_post_end_ns
int64 t_reply_send_ns

# Tracker/target callback timestamps (monotonic)
int64 t_track_cb_start_ns
int64 t_track_cb_end_ns
int64 t_target_cb_start_ns
int64 t_target_cb_end_ns

# Derived stage metrics (milliseconds)
# Host-side callback wait and preprocessing (same host monotonic clock domain).
float32 ros_wait_ms
float32 pre_ms
float32 ros_to_np_ms
float32 resize_ms
float32 color_ms
float32 pack_ms
# Legacy ZMQ transport stages (cross-process in legacy mode).
float32 zmq_req_send_ms
float32 zmq_wait_reply_ms
float32 zmq_roundtrip_ms
float32 decode_ms
float32 det_pub_ms
# Container processing stages (container monotonic clock domain).
float32 container_unpack_ms
float32 container_queue_ms
float32 infer_ms
float32 post_ms
# Tracker/target callback stages (host monotonic clock domain).
float32 track_ms
float32 target_ms
# End-to-end host measurement from camera callback seen -> detection publish end.
# This is not directly comparable to src_stamp_ns without clock synchronization.
float32 e2e_det_ms
float32 e2e_target_ms
# Valid only when src_stamp_ns is comparable to host monotonic timestamps.
float32 sensor_to_target_ms

# Detection publish cadence interval measured in host monotonic domain.
# This is the canonical cadence metric for latency/freshness analysis.
float32 pub_dt_ms

# Backward-compatible legacy fields (read-only compatibility).
# Detailed removal plan is documented in tools/timing_contract.py.
# Deprecated: use src_stamp_ns.
int64  pts_ns
# Deprecated: use t_zmq_send_start_ns.
int64  t_pub_ns
# Deprecated: use e2e_det_ms.
float32 lat_ms
# Deprecated ambiguous names removed by explicit mapping:
# recv_ms -> zmq_roundtrip_ms, json_ms -> decode_ms.
float32 recv_ms
float32 json_ms
# Deprecated: use explicit stage metrics (pre_ms + container_queue_ms + infer_ms + post_ms + det_pub_ms).
float32 loop_ms