# Dynamic UAV TIM-MARS Validation Trial

## Status

**NON-HELD-OUT PHYSICAL VALIDATION.**

This trial is separate from the frozen H01/H02/H03 prospective held-out
evaluation. Do not modify, access, replay, or inspect H01/H02/H03 as part of
this trial.

The purpose is to close a distinct thesis-evidence gap: TIM-MARS must be
demonstrated from a genuinely moving aerial sensing platform rather than only
from a near-static hovering viewpoint.

## Scientific objective

Demonstrate selected-person identity maintenance and recovery while both the
camera platform and the observed scene move.

The trial must create meaningful UAV ego-motion, including:

- lateral image/background motion;
- changing camera-to-target distance and target scale;
- changing viewing angle;
- yaw-induced image motion;
- combined target motion and aircraft motion;
- geometric ambiguity from at least one distractor;
- a controlled temporary loss or strong visibility degradation followed by
  visibility from a changed UAV viewpoint.

A stationary or nearly stationary hover does **not** satisfy this trial.

## Authority boundary

The aircraft is flown manually by the qualified pilot.

TIM-MARS, tracking and retained telemetry may run, but the thesis controller
must be **disabled for this trial**.

Use `--no-control` explicitly. Do not use `--control-mavros`.

`--field-record` may run MAVROS for telemetry/evidence only. The explicit
`--no-control` flag prevents `control_ref_node` from running, while the absence
of `--control-mavros` ensures there is no thesis command path to the aircraft.

The pilot owns all translation, altitude and yaw commands and retains normal
abort authority throughout the trial.

## Pre-flight gate

Use the normal #50 aircraft/network gate first:

    cd ~/Desktop/Thesis-Code || exit 1
    set +u
    sudo tools/host/set_pi_network_mode.sh pixhawk
    sudo tools/host/set_pi_network_mode.sh status

Required state:

- approved field Wi-Fi active;
- `pixhawk-apm` active with no default route;
- Tailscale inactive;
- real Pixhawk/MAVROS telemetry available;
- camera/Hailo healthy;
- no thesis controller process running;
- H01/H02/H03 Stage-7 validator still reports `final_ready=0/3`.

Verify the freeze:

    python3 tools/analysis/validate_tim_evaluation_split.py \
        docs/data/splits/tim_mars_split_v4.json \
        --verify-hashes

## Start the trial

Choose a unique run identifier before launch:

    export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"
    echo "$RUN_ID"

Start the normal retained field stack **without** controller authority:

    ./tools/start_live_stack.sh \
        --field-record \
        --record-raw \
        --no-control \
        --tag dynamic_uav_tim_manual_r1

Keep `--no-control` present and do not add `--control-mavros`.

Select the intended physical target only after the aircraft is safely
established and the target/distractor identities are visually unambiguous.

Record the trial start:

    python3 tools/live/operator_event.py trial_start \
        --run-id "$RUN_ID" \
        --condition baseline \
        --scenario dynamic_uav_tim_manual

After selection, record the intended physical person using the normal
`target_selected` operator event.

## Flight choreography

Target approximately **90–120 seconds** of retained evidence. Exact motion
remains subordinate to the pilot's safety judgement and the available flight
area.

### Phase A — stationary reference

- establish a safe stable hover;
- target and at least one distractor clearly visible;
- select the target;
- retain approximately 10 s of stable reference footage.

### Phase B — lateral platform translation

- pilot translates laterally in one direction while keeping the people in
  view;
- reverse direction and cross back through a substantially different camera
  position;
- the target may walk slowly during part of this phase.

The background should visibly move across the image. Tiny hover corrections do
not satisfy this phase.

### Phase C — range and scale change

- increase camera-to-target distance enough to make the target visibly
  smaller;
- subsequently reduce the distance again;
- keep the manoeuvre smooth and inside the pilot-agreed safety envelope.

This phase should produce a meaningful target-scale change rather than only
minor frame-to-frame variation.

### Phase D — yaw and viewpoint change

- perform a controlled yaw/heading change while retaining the target in the
  field of view where practical;
- continue with a shallow arc around the target area if the flight area permits;
- obtain visibly different front/side/rear or oblique target viewpoints.

A full orbit is not required and must not be attempted if the pilot considers
it unsafe.

### Phase E — combined target and UAV motion

- target walks continuously;
- pilot simultaneously translates or arcs the UAV;
- distractor performs a controlled crossing or passes close to the selected
  target;
- continue long enough to generate simultaneous target motion, background
  motion and viewpoint change.

This is the core moving-platform TIM-MARS condition.

### Phase F — changed-viewpoint loss and return

Create one safe, deliberate identity-recovery challenge while the UAV position
or heading differs from the initial reference:

- briefly move the selected target out of view, behind an available occluder,
  or through a strong partial visibility reduction;
- keep a distractor visible if practical;
- restore target visibility from a meaningfully changed UAV viewpoint;
- do not manipulate the scene based on observed TIM-MARS success/failure.

The physical event is what matters during capture.

### Phase G — final reference

- return to a safe stable hover;
- keep the target visible for at least 10 s;
- end the trial nominally.

## Safety constraints

- pilot judgement overrides choreography;
- use conservative manual motion suitable for the available field;
- avoid abrupt high-rate yaw or translation solely to make the experiment
  harder;
- maintain the normal person/UAV separation and flight-area boundaries;
- do not intentionally fly toward a person to create scale change;
- skip any phase that cannot be performed safely;
- record an operator abort/takeover event when relevant.

This experiment tests perception under realistic ego-motion, not aggressive
aircraft manoeuvring.

## Acceptance criteria

Retain the trial only as dynamic-platform evidence if:

- the bag/evidence package is finalized and usable;
- the aircraft visibly changes position and/or heading by more than ordinary
  hover corrections;
- lateral background motion is clearly present;
- meaningful target-scale change occurs;
- at least two substantially different target viewpoints occur;
- target and UAV move simultaneously for a sustained interval;
- at least one distractor interaction occurs;
- one controlled loss/strong-degradation and subsequent changed-viewpoint
  return occurs if safely achievable;
- `control_ref_node` did not run and no thesis controller was granted
  aircraft motion authority.

If recorder transport-loss checks classify the evidence as incomplete, retain
the files but do not treat that run as scientifically valid.

## Post-flight analysis

This is development/physical-validation evidence, not H01/H02/H03 final
held-out evidence.

Analyse, without changing frozen TIM-MARS behaviour:

- correct selected-person output while the target is physically present;
- wrong-person output;
- LOST/suppressed duration;
- TIM state transitions;
- identity switches or wrong-person authority;
- reacquisition success and delay where the physical event permits it;
- behaviour during simultaneous UAV and target motion;
- representative frames before, during and after major viewpoint changes.

The thesis should explicitly distinguish:

1. near-static-platform evidence;
2. manual moving-platform TIM-MARS evidence;
3. autonomous closed-loop following evidence.

Together these establish progressively stronger evidence than a stationary
camera-style demonstration.

## Held-out boundary

This trial does **not** alter the Stage-7 H01/H02/H03 contract.

Do not use its outcomes to change the frozen TIM-MARS algorithm, tracker,
models, thresholds, evaluator semantics, or the H01/H02/H03 physical scenario.

If a future final prospective evaluation specifically requires a
moving-platform held-out condition, define and freeze that new condition
**before any capture or outcome access** rather than retroactively modifying
H01/H02/H03.
