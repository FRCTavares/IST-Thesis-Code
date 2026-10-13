# Thesis-Code — Final completion queue

Last reconciled with GitHub: **3 October 2026**. **9 open Code issues**, including milestones; this is not a thesis completion percentage. GitHub issue bodies define acceptance and retain historical scope beneath the current checklists.

## Scope

The seven-method campaign is complete and under evidence review. The bounded BoT-SORT substitution is complete and independently reconciled; exploratory work is closed. Complete evidence reconciliation and thesis handoff. No new datasets, 4K/tiled evaluation, parameter sweeps, encoder/compiler searches or flights. The three flights and all three CVAT annotation tasks are complete. TIM-MARS was flown; TIM-MARS-G was not.

## Active queue

- [ ] [Code #127 — Final seven-method comparison](https://github.com/FRCTavares/IST-Thesis-Code/issues/127) — **CAMPAIGN COMPLETE / RECONCILIATION OPEN**. Audit the completed executor campaign; verify configurations, counts, failed initialisations, uncertainty, matched cost and per-dataset conclusions. Do not start a duplicate campaign.

- [ ] [Code #125 — Historical public benchmark and confirmation reconciliation](https://github.com/FRCTavares/IST-Thesis-Code/issues/125) — **EVIDENCE REVIEW**. Preserve frozen protocols and the inconclusive confirmation verdict. Label later reuse explicitly; final expanded evaluation belongs to #127.

- [ ] [Code #50 — Original-flight evidence closeout](https://github.com/FRCTavares/IST-Thesis-Code/issues/50) — **NATIVE LOGS PENDING**. Retrieve and associate Pixhawk logs Tuesday 6 October. Reconcile FCU response, battery events, original event corrections and attribution limits; publish the controller verdict. No further flight.

- [ ] [Code #32 — Sustained runtime and resource evidence](https://github.com/FRCTavares/IST-Thesis-Code/issues/32) — **ACCEPTANCE AUDIT**. Audit the retained configuration and existing full-interval measurements. Short replays do not replace the declared 60 s warm-up plus 20-minute mounted measurement. Record unavailable evidence; scope any necessary disarmed measurement separately.

- [ ] [Code #41 — Final limitations](https://github.com/FRCTavares/IST-Thesis-Code/issues/41) — **DRAFT NOW / FINALISE AFTER EVIDENCE**. Include seed ambiguity, detector/geometry limits, bridge drift, reused data, failed initialisations, crowded latency tails and original-flight timing limitations.

- [ ] [Code #39 — Final thesis claim freeze](https://github.com/FRCTavares/IST-Thesis-Code/issues/39) — **DEPENDS ON #127/#50/#32/#41**. Reconcile identity, cost and physical claims with verified evidence. A negative or inconclusive result is a valid completed conclusion.

- [ ] [Code #66 — Background, architecture and method revision](https://github.com/FRCTavares/IST-Thesis-Code/issues/66) — **HISTORICAL 7-SEP MILESTONE**. Complete the expanded-scope revision through Report #39 and architecture/editorial issues. Record actual completion without claiming the original deadline was met.

- [ ] [Code #67 — Final experiments/results/discussion draft](https://github.com/FRCTavares/IST-Thesis-Code/issues/67) — **HISTORICAL 30-SEP MILESTONE**. Integrate final comparison, flights, runtime verdict and limitations through Report #23/#24; record actual supervisor-ready delivery.

- [ ] [Code #68 — Review and submission](https://github.com/FRCTavares/IST-Thesis-Code/issues/68) — **FINAL COORDINATION**. Complete supervisor review, provenance, metadata and compliance. Verify the official deadline; final build/artwork remains deferred during the current text-only pass.

## Completion rules

- Preserve rejected variants, invalid runs, frozen evidence and corrected-event sidecars. Never erase errors to improve a result.
- Separate historical held-out results, completed independent confirmation, reused-data evaluation, original flight outputs and new frame-indexed replay.
- Controller freshness is unchanged. Crowded latency tails remain reported even though the 150 ms development selection rule was revised prospectively.
- Receiving Pixhawk logs does not automatically close #50 or #32. Finish each issue's evidence verdict or explicitly document revised/retired requirements.
- Report missing measurements rather than fabricate completion or a positive superiority claim.
- Update this queue whenever an issue is tackled. Do not reset other work, alter flight source/install or interfere with the existing campaign.

## Report handoff

Report #39 owns retained-TIM and Chapters 2–5 reconciliation; #23 tables/figure instructions; #24 discussion; #21 flight analysis; #22 runtime; #25 conclusions; #26 claim matrix; #35 overall coordination. Always qualify repository names: Code #32 is runtime, Report #32 is supervisor feedback.

## Historical queue

The complete previous queue is preserved under docs/archive/. Its future-work wording and earlier blocked/promoted states are historical and do not define the current active scope.

## 3 October checkpoint: names and bounded follow-up

Use TIM-MARS for the flown TensorFlow MARS layer and TIM-MARS-G for the guarded FP32 ORT/1000-ms bridge variant. Preserve old labels in frozen source artifacts.

The final campaign shows mixed outcomes: TIM-MARS-G's development gain does not generalise to all inputs; TIM-MARS recovers 7/8 internal primary re-entries versus 0/8 for TIM-MARS-G; BoT-SORT is a strong public-coverage/cost baseline. No universal improvement is established.

- [ ] Code #127: retain the completed seven-method matrix and add the separately declared five-arm tracker-substitution comparison without overwriting it. No threshold tuning or new data.
- [ ] Code #39/#41: reconcile the new combinations only after their evidence is verified; retain failure/initialisation and cost boundaries.
- [ ] Code #50: Tuesday native-log collection and original-flight verdict.
- [ ] Code #32: existing sustained-interval evidence audit and explicit remaining limitations.

Mac Report sources now use the agreed names and include verified core results. Full matrix/uncertainty insertion and the pending combinations remain Report #23/#24/#26/#39. No flight code/install or executor source was edited by this documentation pass.


### Final method names

- [x] Apply TIM-MARS and TIM-MARS-G in active prose; present them as two configurations of the same architecture.
- [x] Prepare five-arm result-insertion requirements; historical identifiers and frozen artifacts remain unchanged.
- [x] Verify the completed tracker-substitution report and insert its separately scoped accuracy/runtime outcomes; no automatic promotion.
- [ ] Update actual figure artwork/display labels only in the later authorised asset pass.


## Completed substitution handoff — 3 October 2026

Accuracy rates and matched runtime medians were independently reconstructed from saved records. TIM-MARS: NO BENEFIT. TIM-MARS-G: SUPPORTED (exploratory) under its declared public rule, but not promoted because internal coverage falls and crowded p95 reaches 673–906 ms. Keep ByteTrack as the input in both retained configurations. The Report includes the fixed exploratory result and separate common-start/all-manifest denominators. Preserve the wrapper split-label deviation and original campaign snapshots. No new run, push, merge or flight. #50 and #32 retain their native-log and sustained-runtime requirements.

## Accepted research closeout — 3 October 2026

Stop algorithm tuning and new campaigns. Retain ByteTrack under TIM-MARS and TIM-MARS-G. The Report closeout manifest hashes the retained evidence snapshots. Saved per-frame audit confirms 7/8 first-correct-frame events in four recordings, not seven sustained recoveries: two initial runs last one frame and two June gaps lack confirmed absence. Remaining #50 native-log and #32 sustained-runtime acceptance requirements stay open; no flight/source/install or configuration is changed. Compact presentation and supervisor review proceed in Thesis-Report.


## Delivery source documentation — 4 October 2026

- [x] Add professional file-specific purpose and Francisco Tavares attribution
  headers throughout maintained code, tools, ROS messages, launch/build files,
  tests and runtime/host configurations (387 files audited on Pi main; no missing headers).
- [x] Retain six upstream ament template notices and immutable evidence/data
  artifacts; add a reusable source-header audit and document the exclusions.
- [x] Standardise ROS maintainer metadata; fix the four identified packaging
  failures and two import-order failures; enable both existing copyright gates.
- [x] Verify Python syntax/semantics, shell syntax, configuration/message values,
  34 packaging tests, six ROS lint gates and 454 protected artifact hashes.
- [x] Fast-forward the Mac to Pi main `00c120e9` as authorised (13 existing
  commits); preserve the author closeout queue and archive the exact local
  six-flight operator sheet alongside the newer active B-C-B procedure.
- [x] Identify the separately frozen TIM-MARS-G implementation, exact model and
  configuration hashes in the delivery manifest; preserve 116 verified frozen
  source/configuration files without substituting a trial variant.
- [ ] Complete the Code #50 and #32 evidence verdicts before claiming final
  thesis/code delivery closure. This header pass does not close those issues.

See docs/DELIVERY_READINESS_20261004.md for scope and verified boundaries.


## Complete delivery audit — 5 October 2026

- [x] Audit all maintained headers again: 389 files, zero omissions.
- [x] Correct dependency declarations and clean-install/live/field/offline guidance.
- [x] Build all three ROS packages; verify nine installed ROS executables.
- [x] Run 1,330 tooling tests and 544 ROS package tests; record two skipped
  external-bag integration tests explicitly.
- [x] Preserve complete pinned research-source snapshots, canonical models and
  verified overlays; 2,929 individual files match their source inventories.
- [x] Preserve frozen gates/hashes and evidence identities; update only the
  current runtime's documentation fingerprint and harmless test assumptions.
- [x] Review source deletion candidates and file organisation: no further
  maintained-source deletion is supported; catalogue-only binaries remain
  documented and excluded from the portable snapshots.
- [ ] Resolve dependency consistency in a separate fresh installation before
  deployment; the retained Pi environment has OpenCV/NumPy and PyNaCl/cffi warnings.
- [ ] Complete Code #50/#32 evidence verdicts and author review. Software/source
  checks do not close physical acceptance or final submission approval.

See docs/DELIVERY_READINESS_20261005.md and docs/delivery_audit_20261005.json.

## SORT confidence repair — 12 October 2026

- [x] Carry the matched detector's confidence into each confirmed SORT track and verify unchanged associations, complete accuracy on the original cohort, native controls, and matched runtime. Preserve the earlier interface-limited study as separate evidence. Pi package: reports/sort_confidence_repair_20261012. Completed: 44 invariant tracker streams, 88 accuracy files, four native controls, 24 runtime runs, 69,613 preserved input/source hashes, and installed ROS package check. Report Chapters 5–7 and Desktop PDFs refreshed; author review remains open.
