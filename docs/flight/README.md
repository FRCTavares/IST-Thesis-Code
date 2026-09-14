# Flight day

Last reviewed: 2026-09-14

This is the **only current day-of-flight operator sheet**.
The other `P027_*.md` files here are frozen #27 provenance.

## 0. Before leaving

- [ ] Pi/UAV/controller/batteries/chargers; camera, Hailo and Pixhawk
- [ ] target, distractor, qualified pilot; >=40 GiB free; #27 and normal-runtime worktrees ready

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

Switch back to normal validated runtime:

    tools/experiments/record_p064_drone_sequence.sh small_target_r1

- [ ] native 1280x720; detector remains 640x640; genuinely small target
- [ ] crossing/occlusion, then exit + re-entry with distractor visible
- [ ] copy the final bag

## 3. #50 aircraft gate

**No closed-loop flight until every gate passes.** If only `ISR Aero.Next GCS`
is available, connect the Mac to it and SSH to `francisco@192.168.8.174`.
The Rescue profile grants management access in `unattended` mode, never
Pixhawk/MAVROS/controller authority. With Pixhawk Ethernet physically
connected, explicitly enter field mode:

    sudo tools/host/set_pi_network_mode.sh pixhawk
    sudo tools/host/set_pi_network_mode.sh status
    nmcli -t -f ACTIVE,SSID dev wifi
    ip route
    systemctl is-active tailscaled

- [ ] ISR Wi-Fi preferred; approved AERONEXT fallback available
- [ ] `pixhawk-apm` active without default route; Tailscale inactive
- [ ] real Pixhawk + MAVROS connected
- [ ] TIM-MARS alone authorizes control; raw `/target` has no motion authority
- [ ] stale/UNCERTAIN/REACQUIRED/LOST fails safe; command signs checked on ground
- [ ] pilot takeover/abort agreed; commands and evidence: `docs/flight/field_day_runbook.md`, `docs/flight/retained_evidence_package.md`

`--record-mavros` only records; it grants no flight authority.
Recording-capacity gate: the 14 September no-MAVROS main-bag-only
benchmarks reported 1,032 and 891 aggregate transport losses. Paired raw
lost 52–68% of inferred frames under full-stack load. A representative
MAVROS-inclusive main-only ground run must show `observed_zero` and usable
visual reference before treating a flight recording as scientific evidence.
Do not add `--record-raw` to normal full-stack flights. The frozen H01/H02/H03
source-only capture is separate and unchanged.

### Aircraft launch command

    NOT FROZEN — DO NOT USE AN OLD P023 COMMAND

## 4. Dynamic UAV TIM validation — manual pilot, controller OFF

Required **non-held-out** moving-platform evidence; H01/H02/H03 unchanged.
Follow `docs/flight/P050_DYNAMIC_UAV_TIM_TRIAL.md`.

    ./tools/start_live_stack.sh --field-record --no-control --tag dynamic_uav_tim_manual_r1

- [ ] qualified pilot alone controls all motion; no `--control-mavros`
- [ ] lateral reversal, range/scale change, yaw/viewpoint change, safe arc
- [ ] simultaneous target + UAV motion; distractor crossing
- [ ] safe loss and changed-viewpoint return; stable final reference
- [ ] evidence finalized; `control_ref_node` absent

## 5. Flight 1 — basic following

- [ ] pilot-controlled takeoff / hover; select target at trusted LOCKED + NORMAL
- [ ] slow person motion; yaw/distance directions correct
- [ ] no unexpected authority; evidence finalized

## 6. Flight 2 — loss / reacquisition

- [ ] trusted following; target leaves view and translation stops
- [ ] target re-enters; motion resumes only at trusted LOCKED + NORMAL
- [ ] no distractor authority; evidence finalized

## 7. Flight 3 — crossing / distractor

- [ ] controlled crossing; no wrong-person non-zero command
- [ ] uncertainty/loss fails safe; trusted recovery if achieved
- [ ] evidence finalized

## 8. Flight 4 — bounded yaw recovery

**Only if #50 promotes recovery first; otherwise skip.**

- [ ] candidate flags: `--control-yaw-recovery --acknowledge-yaw-recovery-candidate` (see `docs/control/p074_state_aware_control_contract.md`)
- [ ] yaw only, no translation; duration/yaw budget respected
- [ ] no wrong-person command; evidence finalized

## 9. End of day

- [ ] H01/H02/H03/#64 paths recorded; H01-H03 outcomes unopened
- [ ] dynamic-UAV trial flown with genuine platform motion or marked not flown
- [ ] each flight: review `evidence_package_status.json`; archive `run_logs/` and `.bin`; back up
- [ ] keep failed evidence; retrieve Pixhawk `.bin` with `tools/live/archive_pixhawk_dataflash.py`, then disconnect Pixhawk

    sudo tools/host/set_pi_network_mode.sh unattended
