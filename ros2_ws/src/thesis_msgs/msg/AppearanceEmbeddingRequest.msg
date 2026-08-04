# Causal request identifier. Unique for one TIM-MARS process lifetime.
uint64 request_id

# Complete backend and embedding-space contract.
string backend_name
string embedding_space
uint32 backend_dimension
uint32 backend_input_height
uint32 backend_input_width
uint32 backend_input_channels
string backend_input_layout
string backend_input_dtype
string backend_raw_output_dtype
string backend_embedding_dtype
bool backend_l2_normalized

# Host monotonic timestamp domain.
int64 submitted_ns
int64 deadline_ns

# Source observation metadata.
uint64 source_frame_id
int64 track_timestamp_ns
int64 source_image_timestamp_ns
uint64 source_image_seq

# Identity and lifecycle provenance.
uint64 frame_generation
uint64 candidate_index
uint64 track_id
uint64 track_generation

# Source bounding box in x_min, y_min, x_max, y_max order.
float64[4] source_bbox_xyxy

# Owned contiguous BGR crop.
# The only accepted encoding for this contract is "bgr8".
uint32 crop_height
uint32 crop_width
uint32 crop_step
string crop_encoding
uint8[] crop_data
