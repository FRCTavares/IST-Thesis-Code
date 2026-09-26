# Final lab-to-postflight master checklist

This document is the orchestration checklist for the remaining physical thesis
work. It deliberately does not duplicate operational commands.

The objective is to make the final B-C-B session the last planned airborne
experiment. A later visit to the laboratory may still be required for disarmed
runtime characterization, but no further flight should be required if the
retained B-C-B evidence satisfies the frozen contract.

## Authorities

Use these documents as the operational authorities:

- Day-of-flight commands and safety gates:
  `docs/flight/field_day_runbook.md`
- Post-flight reconstruction and controller-policy analysis:
  `docs/flight/postflight_analysis.md`
- Final mounted runtime/resource characterization:
  `docs/issues/p032-final-mounted-runbook.md`
- Detailed #50 preparation/evidence record:
  `docs/issues/p050-flight-validation.md`

During flight operations, `docs/flight/field_day_runbook.md` is the only
operator sheet. Do not substitute commands from this checklist, old archived
runbooks, notes, chat history, or historical issue text.

Implementation/evidence-verification baseline before this checklist:
`2a3b4a83` (`26-09-26: finalize pre-field evidence verification`).

Do not retune, refactor, upgrade packages, or modify the frozen runtime merely
because laboratory access is available. A newly discovered correctness or
safety defect is a STOP condition and must be handled explicitly.

---

## Phase A — Before leaving for the laboratory

- [ ] Repository is clean and synchronized with `origin/main`.
- [ ] Current runtime configuration has not been retuned after the frozen
      pre-field checkpoint.
- [ ] `docs/flight/field_day_runbook.md` is available offline on the operator
      computer.
- [ ] `docs/flight/postflight_analysis.md` is available offline.
- [ ] `docs/issues/p032-final-mounted-runbook.md` is available offline.
- [ ] Laptop, chargers, Ethernet/network equipment and required storage are
      available.
- [ ] Aircraft batteries and transmitter/pilot equipment are ready.
- [ ] Enough Pi storage exists for three retained B-C-B runs plus associated
      visual, provenance and Pixhawk evidence.
- [ ] No planned task depends on the unavailable AERONEXT fallback credentials.
      The validated primary field path remains `ISR Aero.Next GCS` plus
      `pixhawk-apm`.

### Gate A

Proceed to laboratory qualification only when the repository and equipment are
ready without requiring speculative software changes.

---

## Phase B — Monday laboratory qualification

The purpose of this visit is to remove avoidable reasons for losing the final
flight session. Airborne scientific comparison is not required during this
phase.

### B1 — Physical hardware inspection

- [ ] Inspect aircraft structure and mounting.
- [ ] Inspect camera mounting and field of view.
- [ ] Inspect Raspberry Pi, Hailo-8, Pixhawk and all relevant power/data
      connections.
- [ ] Confirm `/dev/hailo0` is available.
- [ ] Confirm the TEVS camera/media path is available.
- [ ] Confirm Pixhawk Ethernet connectivity through the canonical
      `pixhawk-apm` path.
- [ ] Confirm sufficient local storage.
- [ ] Confirm batteries required for the eventual B-C-B session are serviceable.

### B2 — Capture dissertation physical assets

- [ ] Capture the final F05 platform photograph while the complete aircraft is
      physically available.
- [ ] Capture any additional hardware photograph that would otherwise require
      another laboratory visit.
- [ ] Preserve the original-resolution image files with clear filenames and
      provenance.

### B3 — Canonical field stack

Follow the pre-flight/static/passive sections of
`docs/flight/field_day_runbook.md`.

- [ ] Primary ISR/Pixhawk network contract passes.
- [ ] Tailscale/ordinary-network state transitions behave as required by the
      canonical field procedure.
- [ ] MAVROS connects to the real Pixhawk using the retained target/system
      contract.
- [ ] Camera starts cleanly.
- [ ] Detector, tracker and TIM-MARS become ready.
- [ ] Visual recording becomes ready using the validated progress-based check.
- [ ] Rosbag recording becomes ready.
- [ ] Runtime provenance identifies the intended frozen stack.
- [ ] No root-level `log/` or `hailort.log` noise is created.

Do not spend laboratory time trying to invent or recover AERONEXT credentials.
Its unavailability is already a documented limitation.

### B4 — Final frozen normal-controller ground validation

The frozen normal-follow configuration is:

- `yaw_kp=0.60`
- `max_yaw_z=0.20 rad/s`
- `max_delta_yaw_z=0.03`
- `invert_yaw=true`

- [ ] Complete the remaining safe disarmed/ground validation using the
      authoritative field runbook.
- [ ] Confirm centred-target behaviour.
- [ ] Confirm left/right command sign.
- [ ] Confirm forward/back command sign where safely observable.
- [ ] Confirm stale/invalid target causes zero authority.
- [ ] Confirm saturation and slew limits behave as frozen.
- [ ] Confirm the controller can be stopped cleanly.
- [ ] Confirm pilot takeover/abort procedure is understood and operational
      where the authoritative runbook requires it.
- [ ] Do not substitute unsafe restrained props-on testing.

Aircraft motion, mode selection, arming and takeover remain pilot-owned.

### B5 — Evidence-path rehearsal

- [ ] Operator-event logging works with exact run/trial IDs.
- [ ] `target_selected` can be recorded unambiguously.
- [ ] Trial end/verdict events are retained.
- [ ] B-C-B strict opportunity verification is available.
- [ ] Visual evidence finalizes and decodes.
- [ ] Retained bag verification passes.
- [ ] Recorder transport loss is zero for evidence intended to qualify
      scientifically.
- [ ] Pixhawk DataFlash catalogue access works.
- [ ] FCU logging contract reads:
      `LOG_DISARMED=0`, `LOG_FILE_DSRMROT=1`, `LOG_BACKEND_TYPE=1`.
- [ ] Pre/post catalogue comparison can identify exactly one new log when one
      new log is expected.
- [ ] Explicit-ID DataFlash retrieval works.
- [ ] Retained DataFlash package contains the `.bin`, `before.json`,
      `after.json`, `association.json` and per-log retrieval JSON.
- [ ] Retained-package verification checks byte counts and SHA-256 provenance.

### Gate B — READY TO FLY

Declare READY TO FLY only when:

- [ ] frozen controller ground validation passes;
- [ ] camera/Hailo/Pixhawk/MAVROS stack is healthy;
- [ ] recording and visual paths are healthy;
- [ ] DataFlash path is healthy;
- [ ] operator-event path is understood;
- [ ] pilot has a clear takeover/abort procedure;
- [ ] no unresolved safety-critical defect remains.

If any safety-critical or evidence-critical defect is found, STOP. Fix and
revalidate it before scheduling the final flight comparison.

---

## Phase C — Final flight day

The goal is one frozen same-session scientific comparison with no field
retuning.

### C1 — Preflight freeze

Follow `docs/flight/field_day_runbook.md`.

- [ ] Repository/runtime identity is checked.
- [ ] No algorithm/controller parameters changed since qualification.
- [ ] Safe site, weather, pilot and operating conditions are acceptable.
- [ ] Aircraft and batteries pass pilot preflight.
- [ ] Storage capacity is sufficient.
- [ ] Field network passes.
- [ ] Passive/static readiness passes.
- [ ] DataFlash logging parameters match the frozen contract.
- [ ] Abort/takeover procedure is ready.

### C2 — Frozen three-flight order

Execute at most the frozen comparison sequence:

- [ ] Flight 1 — Baseline A: `bcb_baseline_a`
- [ ] Flight 2 — Candidate: `bcb_candidate`
- [ ] Flight 3 — Baseline B: `bcb_baseline_b`

Baseline flights use recovery disabled.

Candidate uses only the frozen bounded yaw-only recovery:

- `0.10 rad/s`
- maximum `1.0 s`
- maximum integrated yaw `0.10 rad`
- zero recovery translation

No field retuning is permitted.

### C3 — Opportunities in every flight

For each flight, reproduce as closely as practical:

- [ ] O1 — right loss/return
- [ ] O2 — left loss/return
- [ ] O3 — distractor crossing followed by selected-person loss/return

For every opportunity:

- [ ] at least 3 s trusted LOCKED state before the intended loss;
- [ ] loss is safely observable;
- [ ] frozen 10 s observation horizon is respected;
- [ ] operator opportunity start/end records are retained;
- [ ] no later events are fabricated after an abort;
- [ ] at least 3 s separated trusted following is established before the next
      opportunity when the trial continues.

Correct-person reacquisition and exact timing are evidence-derived, not
declared by the operator.

### C4 — Immediate safety rule

Immediately use the authoritative abort procedure for:

- wrong-person non-zero authority;
- stale/invalid non-zero authority;
- unsafe or unexpected aircraft motion;
- unacceptable saturation/oscillation;
- pilot concern;
- any other condition requiring takeover.

Keep every failed or aborted run.

---

## Phase D — Verify every flight before considering the session complete

After each flight, while the aircraft is landed and disarmed:

- [ ] complete the nominal end events or coherent abort prefix;
- [ ] stop/finalize the retained recording using the canonical procedure;
- [ ] preserve the exact RUN_ID and TAG;
- [ ] compare pre/post DataFlash catalogues;
- [ ] require exactly one new DataFlash ID for an unambiguous association;
- [ ] explicitly retrieve that DataFlash ID;
- [ ] archive the `.bin` and all four retrieval/association sidecars;
- [ ] run the retained evidence-package verifier;
- [ ] confirm strict B-C-B operator-event validation;
- [ ] confirm bag integrity;
- [ ] confirm recorder transport loss is zero for a scientifically eligible
      run;
- [ ] confirm the retained visual file decodes;
- [ ] confirm the visual covers the intended O1/O2/O3 periods;
- [ ] preserve failures rather than deleting or replacing them.

Never select a DataFlash log from highest ID, timestamp or file age when the
catalogue association is ambiguous.

### Between flights

Only perform operational actions such as battery changes, physical inspection
and safety checks.

- [ ] no controller retuning;
- [ ] no TIM-MARS tuning;
- [ ] no detector/tracker tuning;
- [ ] no post-hoc change to the opportunity protocol.

---

## Phase E — Last-planned-flight gate

After Baseline B, do not leave the evidence state ambiguous.

Before treating the B-C-B session as the last planned flight session:

- [ ] Baseline A package is retained.
- [ ] Candidate package is retained.
- [ ] Baseline B package is retained.
- [ ] Every package has its exact RUN_ID/TAG recorded.
- [ ] Every package has valid operator-event evidence or an explicit retained
      abort/rejection record.
- [ ] Every scientifically usable package has zero recorder transport loss.
- [ ] Every scientifically usable package has decodable visual evidence.
- [ ] DataFlash association is either unambiguous and retained or explicitly
      marked unusable; no association is guessed.
- [ ] For each O1/O2/O3, visual evidence is sufficient to determine whether the
      intended physical person left and returned.
- [ ] A quick human review confirms that identity attribution is possible for
      the opportunities expected to contribute to the decision.
- [ ] No evidence file still exists only in a transient location.
- [ ] A backup/copy of the retained evidence exists before equipment is
      dismantled.

The protocol does not guarantee that the result will promote the Candidate.
If insufficient eligible triplets remain, report the result as non-promoting
or inconclusive according to the frozen decision contract rather than changing
the experiment after seeing the data.

Passing this gate means no additional airborne measurement is planned.

---

## Phase F — #50 post-flight reconstruction

Use `docs/flight/postflight_analysis.md`.

For all three retained flights:

- [ ] preserve exact run identities and provenance;
- [ ] complete physical-person annotation;
- [ ] establish permitted visual/command time alignment;
- [ ] classify controller-facing authority using physical truth;
- [ ] derive correct-target controlled duration;
- [ ] derive wrong-person non-zero command duration;
- [ ] derive stale/invalid non-zero command duration;
- [ ] derive lost/hover duration;
- [ ] derive recovery-search duration;
- [ ] derive reacquisition delay for O1/O2/O3;
- [ ] inspect saturation/smoothness and operator takeover;
- [ ] retain uncertainty/censoring rather than forcing a value.

### Opportunity-triplet eligibility

A matching O1, O2 or O3 triplet is eligible only if that opportunity is
eligible and physically attributable in all three flights.

- [ ] identify all eligible O1/O2/O3 triplets;
- [ ] require at least two eligible triplets for a controller-policy decision;
- [ ] preserve every ineligible/rejected opportunity and its reason.

### Frozen controller-policy decision

Safety/integrity gates require:

- [ ] zero wrong-person non-zero command;
- [ ] zero stale/invalid non-zero command;
- [ ] zero Candidate recovery translation;
- [ ] no unsafe Candidate motion;
- [ ] no unacceptable Candidate saturation;
- [ ] no Candidate pilot takeover attributable to the recovery policy.

With three eligible triplets:

- [ ] Candidate is earlier than both baselines in at least two triplets;
- [ ] Candidate is no worse than either baseline in the remaining triplet.

With exactly two eligible triplets:

- [ ] Candidate is earlier than both baselines in both triplets.

Then record exactly one evidence-derived outcome:

- [ ] bounded Candidate recovery retained;
- [ ] conservative baseline retained;
- [ ] result inconclusive/non-promoting.

Do not claim statistical superiority. These are repeated descriptive
observations within one B-C-B session, not independent replicates.

### Gate F — #50 decision complete

- [ ] final retained controller configuration is explicitly recorded;
- [ ] #50 result/evidence documents are updated;
- [ ] GitHub #50 is reconciled with the evidence;
- [ ] no further airborne experiment is required by the retained decision.

---

## Phase G — Final #32 mounted runtime/resource characterization

Execute only after Gate F establishes the retained final controller.

This phase requires the mounted Pi/camera/Hailo/Pixhawk system but no flight.

Use `docs/issues/p032-final-mounted-runbook.md`.

- [ ] aircraft remains disarmed for the complete run;
- [ ] aircraft remains stationary for the complete run;
- [ ] exact scenario is `p032_final_mounted_vga`;
- [ ] exact retained controller from #50 is used;
- [ ] VGA 640x480 remains the retained appearance/source resolution;
- [ ] exact `trial_start`/`trial_end` interval is retained;
- [ ] resource sampler runs for 1260 s total;
- [ ] first 60 s are warm-up;
- [ ] following 1200 s are the active measurement;
- [ ] run is not shortened because the system appears stable.

### #32 evidence gate

- [ ] every `/mavros/state` sample inside the exact trial interval reports
      connected=true;
- [ ] every `/mavros/state` sample inside the exact trial interval reports
      armed=false;
- [ ] startup/shutdown state outside the trial interval remains retained;
- [ ] complete-interval timing/cadence/gap analysis is generated;
- [ ] selective-ReID/cache workload is reported;
- [ ] PID-tree CPU/RSS is reported;
- [ ] temperature/clocks/throttling are reported;
- [ ] Hailo contention/load is reported where observable;
- [ ] raw-image/transport cost is reported;
- [ ] power is reported only if a reproducible method is available;
- [ ] exact runtime/provenance package passes verification.

For this narrowly proven disarmed #32 experiment, physical-v2 annotation and
native Pixhawk DataFlash are not applicable to the runtime/resource claim.

If #32 must be repeated because of a runtime/evidence failure, the repeat is a
disarmed stationary laboratory measurement and does not require another
airborne flight.

### Gate G — #32 complete

- [ ] final runtime/resource table is frozen;
- [ ] GitHub #32 is reconciled/closed with retained evidence;
- [ ] no unresolved mounted-performance claim remains.

---

## Phase H — Final thesis claim freeze

After #50 and #32 are complete:

- [ ] update #39 claim matrix from final evidence;
- [ ] integrate #50 closed-loop results;
- [ ] integrate #32 sustained runtime/resource results;
- [ ] update limitations under #41;
- [ ] preserve #58 source-time repair qualifications;
- [ ] preserve scenario-dependent tracker-comparison conclusions;
- [ ] preserve the AERONEXT unavailable-path limitation;
- [ ] preserve the descriptive, non-statistical interpretation of B-C-B;
- [ ] do not convert unsupported observations into general safety claims;
- [ ] freeze final thesis-facing figures/tables/claims;
- [ ] reconcile GitHub #39.

At this point the thesis should have no planned remaining aircraft-flight
dependency.
