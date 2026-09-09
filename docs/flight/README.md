# Flight day

Last reviewed: 2026-09-09

This is the **only current day-of-flight operator sheet**.
The other `P027_*.md` files here are frozen #27 provenance.

## 0. Before leaving

- [ ] Pi, drone, controller, batteries, chargers
- [ ] camera, Hailo, Pixhawk
- [ ] target + distractor + pilot
- [ ] >=40 GiB free
- [ ] #27 and normal-runtime worktrees ready

## 1. H01-H03 held-out captures

**Source-only: no MAVROS, controller or TIM outcome inspection.**

Use validator-passing revision:

    1f57e2d55ec41342edc75e48032106b69278ae04

Precheck:

    git status --short
    python3 tools/analysis/validate_tim_evaluation_split.py --verify-hashes
    df -h /
    ls -l /dev/video0 /dev/media0 /dev/hailo0

### Run 1 — H01 exit / re-entry

    tools/experiments/record_p027_heldout_sequence.sh h01

- [ ] target + distractor visible
- [ ] target fully absent about 5-8 s
- [ ] distractor visible during absence
- [ ] target re-enters
- [ ] >=10 s afterward; bag readable

### Run 2 — H02 crossing

    tools/experiments/record_p027_heldout_sequence.sh h02

- [ ] start separated
- [ ] close crossing + sustained overlap
- [ ] separate
- [ ] second crossing
- [ ] >=10 s afterward; bag readable

### Run 3 — H03 occlusion

    tools/experiments/record_p027_heldout_sequence.sh h03

- [ ] target + distractor visible
- [ ] partial then full occlusion
- [ ] target remains physically present
- [ ] distractor near last target position
- [ ] reveal same target; >=10 s; bag readable

Allowed now: integrity, counts, timestamps, imagery and physical-scenario check.
**Do not inspect tracker/TIM correctness or architecture outcomes.**

## 2. Run 4 — #64 small-target drone POV

Switch back to normal validated runtime.

    tools/experiments/record_p064_drone_sequence.sh small_target_r1

- [ ] native 1280x720; detector stays 640x640
- [ ] target becomes genuinely small at realistic distance
- [ ] crossing/occlusion
- [ ] exit + re-entry with distractor visible
- [ ] final bag copied successfully

## 3. #50 aircraft gate

**No closed-loop flight until every gate passes.**

    sudo tools/host/set_pi_network_mode.sh pixhawk
    sudo tools/host/set_pi_network_mode.sh status
    nmcli -t -f ACTIVE,SSID dev wifi
    ip route
    systemctl is-active tailscaled

- [ ] ISR Wi-Fi preferred; approved AERONEXT fallback available
- [ ] `pixhawk-apm` active, never default route
- [ ] Tailscale inactive
- [ ] real Pixhawk + MAVROS connected
- [ ] TIM-MARS sole controller target authority
- [ ] raw `/target` has no motion authority
- [ ] stale/UNCERTAIN/REACQUIRED/LOST fails safe
- [ ] command signs checked on ground
- [ ] pilot takeover / abort agreed
- [ ] retained topics/bags frozen

`--record-mavros` is a recording option, not an approved flight command.

Diagnostic only:

    ./tools/start_live_stack.sh --field-record --record-raw --tag SCENARIO

### Aircraft launch command

    NOT FROZEN — DO NOT USE AN OLD P023 COMMAND

## 4. Flight 1 — basic following

- [ ] pilot-controlled takeoff / stable hover
- [ ] select target; trusted LOCKED + NORMAL
- [ ] slow person movement
- [ ] yaw/distance directions correct
- [ ] no unexpected authority; evidence finalized

## 5. Flight 2 — loss / reacquisition

- [ ] trusted following
- [ ] target leaves view; translation stops
- [ ] target re-enters
- [ ] motion resumes only at trusted LOCKED + NORMAL
- [ ] no distractor authority; evidence finalized

## 6. Flight 3 — crossing / distractor

- [ ] controlled target/distractor crossing
- [ ] no wrong-person non-zero command
- [ ] uncertainty/loss fails safe
- [ ] trusted recovery if achieved
- [ ] evidence finalized

## 7. Flight 4 — bounded yaw recovery

**Only if #50 promotes recovery first; otherwise skip.**

- [ ] recovery command frozen + ground-tested
- [ ] yaw only; no translation
- [ ] duration/yaw budget respected
- [ ] no wrong-person command
- [ ] evidence finalized

## 8. End of day

- [ ] H01/H02/H03/#64 paths recorded
- [ ] all flight bags finalized and backed up
- [ ] H01-H03 outcomes still unopened
- [ ] no evidence deleted
- [ ] Pixhawk disconnected

    sudo tools/host/set_pi_network_mode.sh unattended
