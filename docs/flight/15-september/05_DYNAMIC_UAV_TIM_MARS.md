# Flight 5 — Manual Dynamic-UAV TIM-MARS

NON-HELD-OUT PHYSICAL VALIDATION.

The qualified pilot has sole aircraft-motion authority.

The thesis controller MUST remain OFF.

Do not use:

    --control-mavros
    --record-raw

This run is supporting/development evidence unless the retained runtime package
passes the strict evidence checks. The known MAVROS-inclusive recorder issue
must not be hidden or ignored.

## 1. Field network

Run:

    cd ~/Desktop/Thesis-Code || exit 1
    set +u

    sudo tools/host/set_pi_network_mode.sh pixhawk
    sudo tools/host/set_pi_network_mode.sh status

Verify the Stage-7 held-out freeze remains intact:

    python3 tools/analysis/validate_tim_evaluation_split.py \
        docs/data/splits/tim_mars_split_v4.json \
        --verify-hashes

Do not access H01/H02/H03 while running this trial.

## 2. Start retained manual stack

Run:

    export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"
    echo "$RUN_ID"

    ./tools/start_live_stack.sh \
        --field-record \
        --no-control \
        --tag dynamic_uav_tim_manual_r1

Confirm from startup output:

- controller is OFF
- no `--control-mavros`
- pilot retains full aircraft authority

## 3. Start trial event

In another terminal if needed:

    cd ~/Desktop/Thesis-Code || exit 1

    python3 tools/live/operator_event.py trial_start \
        --run-id "$RUN_ID" \
        --condition baseline \
        --scenario dynamic_uav_tim_manual

After the target is safely and unambiguously selected:

    read -r -p "Visible person description: " PERSON
    read -r -p "Track ID: " TRACK_ID

    python3 tools/live/operator_event.py target_selected \
        --run-id "$RUN_ID" \
        --track-id "$TRACK_ID" \
        --intended-physical-person "$PERSON"

## 4. Flight — about 90–120 s

Pilot performs conservative manual motion.

A. Reference:

- stable hover
- target + distractor visible
- about 10 s

B. Lateral translation:

- move laterally
- reverse direction
- clear background motion

C. Range / scale:

- increase target distance
- reduce distance again
- meaningful visible scale change

D. Yaw / viewpoint:

- controlled heading change
- shallow arc if safe
- materially different target viewpoints

E. Combined motion:

- target walks
- UAV moves simultaneously
- distractor crosses / passes close

F. Loss and return:

- one safe brief target visibility loss / occlusion / strong degradation
- restore target visibility from a changed UAV viewpoint

G. Final reference:

- stable hover
- target visible for at least 10 s

Pilot safety judgement overrides every phase.

## 5. End trial event

Run:

    python3 tools/live/operator_event.py trial_end \
        --run-id "$RUN_ID" \
        --end-reason nominal_complete

## 6. Stop stack

At the `live-stack>` prompt type:

    stop

Wait for complete shutdown.

## 7. Summarize evidence

Run:

    printf -v BAG "bags/live_camera/%s__video__dynamic_uav_tim_manual_r1" "$RUN_ID"

    python3 tools/live/summarize_field_evidence.py \
        --bag-dir "$BAG"

If transport is not:

    observed_zero count=0

or runtime evidence is not acceptable, retain the files but do NOT describe
the trial as final scientifically valid evidence.

The flight itself remains a manual-pilot, non-closed-loop perception trial.
