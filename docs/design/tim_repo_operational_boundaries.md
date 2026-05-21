# TIM Repository Operational Boundaries

Date: 2026-05-20

## Purpose

Separate flight-safe runtime paths from offline research/experiment paths.

The goal is to keep the repository easy to use during flights while still allowing TIM-V2 research development.

## Flight-safe path

The flight-safe path is the only path that should be used during live drone operation unless explicitly testing a new feature.

Primary launcher:

- `tools/start_live_stack.sh`

Core live modules:

- `ros2_ws/src/thesis_bringup/thesis_bringup/target_memory.py`
- `ros2_ws/src/thesis_bringup/thesis_bringup/nodes/target_memory_node.py`
- `ros2_ws/src/thesis_tracker/`
- `ros2_ws/src/thesis_msgs/`

Live defaults must remain conservative:

- TIM-V2K disabled unless explicitly enabled.
- TIM-V2E learned embedding disabled unless explicitly enabled.
- Raw `/target` and TIM `/target_memory` outputs must stay distinguishable.
- No generated experiment checkpoints should be loaded by default.

## Offline research path

The offline path contains scripts for:

- bag replay analysis,
- target correctness evaluation,
- TIM policy simulation,
- embedding dataset building,
- embedding training,
- overlay video/frame rendering,
- result reports.

Offline-only tools include:

- `tools/analysis/evaluate_tim_identity_descriptor.py`
- `tools/analysis/build_tim_embedding_dataset.py`
- `tools/analysis/train_tim_embedding_tiny.py`
- `tools/analysis/train_tim_embedding_triplet.py`
- `tools/analysis/train_tim_embedding_hybrid.py`
- `tools/analysis/simulate_tim_v2e_learned_suppression.py`
- `tools/analysis/benchmark_tim_embedding_latency.py`
- `tools/bag/render_tim_policy_overlay_video.py`
- `tools/bag/export_tim_policy_overlay_frames.py`

These scripts must not be treated as live flight code.

## Generated artifacts

The following are generated and should not be committed unless explicitly curated:

- `datasets/tim_embedding/`
- `datasets/tim_embedding_filtered/`
- `reports/tim_v2_embedding/**/*.pt`
- `models/tim_embedding/**/*.pt`
- `reports/tim_v2_embedding/videos/`
- temporary sweep folders under `reports/tim_v2_embedding/`

## Current TIM-V2E status

TIM-V2E is offline-only.

Best current candidate:

- Tiny16 hybrid embedding,
- runtime top-2 margin gate,
- missing/low similarity suppression,
- confirmed high-similarity reacquisition.

Current best offline policy parameters:

- margin gate threshold: 0.10
- selected low-similarity threshold: 0.0
- candidate high-similarity threshold: 0.3
- reacquire confirmation frames: 3
- max similarity time delta: 0.10 s

Do not integrate live until:

1. policy is converted from annotation/timeline simulation to real TIM state gates,
2. more bags are tested,
3. crop extraction and end-to-end TIM callback latency are measured,
4. optional enable/disable launch parameters are added,
5. default live behaviour remains unchanged.

## Cleanup principle

Keep three levels:

1. Live code: minimal, documented, safe.
2. Offline tools: reproducible scripts with clear names.
3. Generated artifacts: ignored unless promoted into curated result documents.

No script should be deleted until its result has either been documented or marked obsolete.
