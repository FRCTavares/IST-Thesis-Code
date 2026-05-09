# TIM Field Recording Script - 2026-05-14

## Goal

Record drone-view RGB dataset bags to evaluate whether TIM keeps the selected physical person correct when raw tracker-ID selection becomes unstable.

Metrics:

- correct target duration
- wrong target duration
- lost duration
- reacquisition time
- TIM latency

---

## Standard Command

Start one bag per scenario:

./tools/start_live_stack.sh --profile daily --record-dataset --bag-tag <tag>

In live prompt:

ids
target <id>
stop

After each important bag:

BAG="$(ls -td artifacts/bags/datasets/* | head -n 1)"
ros2 bag info "$BAG"
python3 tools/bag/render_bag_overlay_video.py "$BAG" --image-topic /camera/image_raw --output "artifacts/reports/videos/$(basename "$BAG")__preview.mp4" --output-size 1280x720 --max-frames 600 --draw-detections

---

## Scenario Scripts

### S01 - Simple Lock

Tag: field_simple_lock_01  
People: 1 target, no distractor  
Duration: 1 to 2 min

Script:

1. Select target.
2. Target walks left/right.
3. Target walks closer/farther.
4. Target stays visible.

Purpose:

Clean baseline. Raw /target and TIM /target_memory should both remain correct.

---

### S02 - Leave and Re-enter

Tag: field_reentry_01  
People: 1 target, no distractor  
Duration: 2 min

Script:

1. Select target.
2. Target leaves frame.
3. Wait 2 to 4 s.
4. Target re-enters.
5. Repeat 2 or 3 times.

Purpose:

Test LOST and REACQUIRED behaviour.

---

### S03 - Two People Separated

Tag: field_distractor_static_01  
People: selected target A, distractor B  
Duration: 2 min

Script:

1. Select target A.
2. B enters frame.
3. A and B stay separated.
4. Both move slowly.

Purpose:

Check that TIM does not switch to B.

---

### S04 - Crossing

Tag: field_crossing_01  
People: selected target A, distractor B  
Duration: 2 to 3 min

Script:

1. Select target A.
2. A and B cross paths.
3. Repeat crossing in both directions.
4. Allow partial overlap only if safe.

Purpose:

Trigger ambiguity and possible ID switch.

---

### S05 - Occlusion

Tag: field_occlusion_01  
People: selected target A, object/person occluder  
Duration: 2 min

Script:

1. Select target A.
2. A passes behind object/person.
3. Occlusion lasts 0.5 to 3 s.
4. A reappears.
5. Repeat 2 or 3 times.

Purpose:

Test UNCERTAIN, LOST, and REACQUIRED.

---

### S06 - Far Target

Tag: field_far_target_01  
People: 1 target  
Duration: 2 min

Script:

1. Select target while close.
2. Target walks away until small.
3. Target walks back.
4. Repeat once.

Purpose:

Test detector flicker and tiny-person behaviour.

---

## Minimum Useful Session

Record:

- S01 simple lock
- S02 leave/re-enter
- S03 two people separated
- S04 crossing
- S05 occlusion
- S06 far target

Extra, if time:

- repeat S04
- repeat S05
- record one extra run if raw /target visibly fails

---

## Manual Notes Per Bag

Write this for each bag:

- bag tag
- selected target ID
- target selection time
- leave-frame time
- re-entry time
- occlusion time
- crossing time
- possible ID switch
- possible wrong-target moment

Example:

field_crossing_01
selected ID: 3
target selected around 12 s
crossing around 35 s and 58 s
possible ID switch after second crossing
