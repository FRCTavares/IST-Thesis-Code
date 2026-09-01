uint32 seq
uint32 frame_id

# Source/camera metadata.
# src_stamp_ns is copied from the source image header. It must not be
# subtracted from host-monotonic timestamps unless clock comparability
# has been established for that run.
int64 src_stamp_ns

# Host-monotonic time when the perception image callback observed the frame.
int64 t_cam_msg_seen_ns

uint32 image_width
uint32 image_height
string image_encoding

# Direct-Hailo detector timestamps, all in the host-monotonic clock domain.
int64 t_pre_start_ns
int64 t_pre_end_ns
int64 t_infer_start_ns
int64 t_infer_end_ns
int64 t_post_start_ns
int64 t_post_end_ns
int64 t_det_pub_start_ns
int64 t_det_pub_end_ns

# Tracker timestamps, host-monotonic.
int64 t_track_cb_start_ns
int64 t_track_cb_end_ns

# Validated TIM-MARS target timestamps, host-monotonic.
int64 t_target_cb_start_ns
int64 t_target_process_end_ns
int64 t_target_pub_end_ns

# Detector stage metrics, milliseconds.
# Camera callback observed -> preprocessing begins.
float32 ros_wait_ms

# Detector preprocessing duration.
float32 pre_ms

# Diagnostic preprocessing decomposition.
float32 ros_to_np_ms
float32 resize_ms
float32 color_ms

# Preprocessing complete -> direct Hailo inference begins.
# This captures in-process scheduling / queue / backpressure before inference.
float32 pre_infer_wait_ms

# Direct Hailo detector execution and downstream detector stages.
float32 infer_ms
float32 post_ms
float32 det_pub_ms

# Tracker backend update() compute only.
float32 track_ms

# TIM-MARS selected-target processing only:
# target callback start -> validated decision processing complete.
float32 tim_mars_processing_ms

# Camera callback observed -> detections publication call complete.
float32 e2e_det_ms

# Camera callback observed -> validated /target_memory_mars publication call complete.
# Populated only by TIM-MARS when causal camera timing reached the track message.
float32 e2e_validated_target_ms

# Interval between consecutive detection publication completions.
float32 pub_dt_ms
