# Flight TIM Checklist

Date: 2026-05-20

## Flight-safe default

Use the normal live launcher:

    cd "$THESIS_ROOT"
    ./tools/start_live_stack.sh --profile daily

Default live behaviour must stay conservative.

TIM-V2E learned embedding is offline-only and must not be loaded during flight unless explicitly implemented and enabled later.

## Before flight

Check repo state:

    git status --short

Expected:

- clean working tree,
- no generated datasets/videos/checkpoints staged.

Check live stack help:

    ./tools/start_live_stack.sh --help | head -n 80

Check camera/perception topics after startup:

    source /opt/ros/jazzy/setup.bash
    source "$THESIS_ROOT/ros2_ws/install/setup.bash"
    ros2 topic list | rg '/camera/image_raw|/camera/dashboard|/detections|/tracks|/target|/target_memory'

## During flight

Use only:

- raw `/target` for baseline comparison,
- `/target_memory` for TIM output,
- `/target_memory/status` for diagnostics.

Do not run training, sweeps, or embedding dataset scripts during flight.

## After flight

Record:

- bag name,
- tracker,
- TIM flags,
- camera mode,
- detector model,
- target selection time/id,
- notes on occlusion/crossing/re-entry.

Then run offline evaluation separately.

## TIM-V2E status

Current TIM-V2E learned appearance is offline-only.

Best offline candidate:

- Tiny16 hybrid embedding,
- runtime top-2 margin gate,
- missing/low similarity suppression,
- confirmed high-similarity reacquisition.

Do not enable live until:

1. runtime implementation exists behind explicit flags,
2. default behaviour remains unchanged,
3. crop extraction and callback latency are measured,
4. held-out bag evaluation is complete.
