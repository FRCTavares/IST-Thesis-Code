# Issue #27 — Prospective H01–H03 Held-Out Capture Runbook

## Purpose

This runbook governs the final prospective selected-person identity data for
Issue #27. It operationalises `tim_mars_split_v2_2026_09_01` without changing
the frozen algorithm or comparison contract.

H01–H03 are source-first algorithmic evaluation sequences. They are not live
closed-loop flight-result sequences.

## Frozen acquisition mode

Every retained H01–H03 source uses:

- camera source: `640x480`, requested explicitly with `--res vga`;
- nominal camera rate: `30 FPS`;
- detector: frozen direct/in-process Hailo YOLOv8s;
- detector inference geometry: `640x640`;
- retained topics: `/camera/image_raw` and `/detections`;
- tracker: disabled;
- TIM-MARS: disabled;
- controller: disabled;
- dashboard/web video: disabled;
- MAVROS: disabled for this algorithmic held-out capture.

The detector evidence is generated exactly once during source capture. Later
ByteTrack, Target-ReID, ByteTrack+TIM-MARS and DeepSORT cells must fan out from
that same frozen detector stream.

Do not substitute the Issue #64 HD capture protocol. Issue #64 separately owns
the unresolved small-target/high-resolution appearance question.

## Before any retained capture

The repository must be clean and the active prospective freeze must pass:

    python3 tools/analysis/validate_tim_evaluation_split.py --verify-hashes

The final-ready gate is expected to fail because H01–H03 have not yet been
released.

Use at least 40 GiB free space. Do not delete prior attempts in the field.
Recording-integrity failures may be repeated because no algorithm outcome has
been inspected; document every retained/aborted attempt.

## Participant and outfit coding

Before architecture evaluation, assign anonymous codes only.

Example:

- participant: `P01`, `P02`, `P03`;
- outfit: `P01_O1_black_top`, `P02_O1_grey_top`.

For each H01–H03 entry, record truthfully whether the participant and outfit
occur in any development or legacy sequence. Do not use names, facial
identifiers, or biometric data.

Using the same people/outfits across H01–H03 is allowed if necessary, but the
thesis must state that those held-out sequences are not person-independent from
one another. New people/outfits relative to development are preferable when
practical, but must never be falsely claimed when overlap is unknown.

## H01 — exit and re-entry

Run:

    tools/experiments/record_p027_heldout_sequence.sh h01

Physical scenario:

1. selected physical target clearly visible at the start;
2. at least one distractor present;
3. target fully exits the camera image;
4. target remains physically absent for approximately 5–8 seconds;
5. distractor remains visible during at least part of the absence;
6. target re-enters and remains clearly visible for at least 10 seconds.

The frozen split mentions tracker-ID churn as the intended challenge. Do not
inspect tracker output to determine whether churn actually occurred. Capture
acceptance is based on the physical scenario and recording integrity only.

## H02 — close crossing

Run:

    tools/experiments/record_p027_heldout_sequence.sh h02

Physical scenario:

1. target and distractor begin clearly separated;
2. perform two close crossings;
3. include a sustained overlap or near-overlap;
4. separate cleanly again;
5. retain at least 10 seconds after the final separation.

Do not inspect tracker or TIM outcomes to decide whether the crossing was
"difficult enough".

## H03 — occlusion with distractor

Run:

    tools/experiments/record_p027_heldout_sequence.sh h03

Physical scenario:

1. target and at least one distractor are visible;
2. target becomes partially occluded;
3. target then becomes fully visually occluded while remaining physically in
   the scene;
4. a distractor stays visible near the target's last visible location;
5. reveal the same physical target again;
6. retain at least 10 seconds of clear post-occlusion visibility.

H03 is intentionally distinct from H01: H01 contains a genuine scene exit and
physical absence; H03 tests visual occlusion while the target remains present.

## Allowed integrity inspection after each capture

Before moving to the next sequence, it is permissible to inspect only:

- bag existence and finalisation;
- topic names;
- message counts;
- duration;
- timestamps;
- corruption/readability;
- source image quality;
- whether the planned physical scenario actually occurred.

For example:

    source /opt/ros/jazzy/setup.bash
    ros2 bag info <SOURCE_BAG>

Do not inspect tracker IDs, TIM states, candidate scores, architecture
correctness, or any output that could influence threshold/model/policy choice.

A source may be repeated for an objective acquisition defect such as corruption,
missing topics, unusable imagery, or failure to perform the specified physical
scenario. It must not be repeated because an algorithm later performed badly.

## Physical-v2 annotation

Create one artifact per retained source:

- `docs/data/physical_target_references/heldout_h01_exit_reentry.json`
- `docs/data/physical_target_references/heldout_h02_crossing.json`
- `docs/data/physical_target_references/heldout_h03_occlusion_distractor.json`

Use the source images as the identity authority. Keep tracker/TIM overlays off.
Do not use tracker IDs as physical identities. Distractors use annotation-local
`phys_dNNN` identities.

Image-only optical-flow proposals are permitted as annotation assistance, but
they are never ground truth until explicitly reviewed and accepted by the
human annotator.

The annotation UI is launched with:

    cd ~/Desktop/Thesis-Code || exit 1
    export GIT_PAGER=cat
    export PAGER=cat
    set +u
    source /opt/ros/jazzy/setup.bash
    source ros2_ws/install/setup.bash
    thesis_env/bin/python tools/bag_annotation_ui/tim_clean_ui.py --host 100.69.42.62 --port 8888

Freeze the selected physical person and the initial bootstrap instant from the
physical annotation before architecture outcome inspection.

## Release order

The final architecture evaluation remains forbidden until all three sequences
have completed every item below:

1. retained source bag selected using physical-scenario/integrity criteria only;
2. source path and source files frozen;
3. physical-v2 annotation complete and validated;
4. participant and outfit codes recorded;
5. exact development/legacy people/clothing overlap recorded;
6. source and annotation sizes/SHA-256 values entered in
   `tim_mars_split_v2.json`;
7. each final entry changed to `ready`;
8. the following command passes:

    python3 tools/analysis/validate_tim_evaluation_split.py         --verify-hashes         --require-final-ready

Only after the gate passes may the four frozen architecture cells be generated
and evaluated.

## Contamination rule

After held-out architecture outcomes become visible:

- do not tune TIM thresholds;
- do not alter TIM identity policy;
- do not change tracker parameters;
- do not change Target-ReID threshold `0.90`;
- do not switch detector/ReID models;
- do not move the bootstrap instant;
- do not change physical-v2 evaluation semantics in response to results.

If an outcome-driven behavior change is made, the accessed sequences are no
longer untouched final held-out evidence and a new prospective split is
required.
