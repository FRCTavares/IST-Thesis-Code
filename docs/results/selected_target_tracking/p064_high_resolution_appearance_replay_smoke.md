# Issue #64 controlled appearance-resolution replay infrastructure

Status: implementation/development smoke only; not final Issue #64 evidence

Date: 26 August 2026

## Scope

This checkpoint adds the experiment-enabling path needed to vary only the
TIM-MARS appearance image while preserving one frozen detector/tracker
candidate stream. It does not change the detector HEF or 640x640 inference
input, tracker behaviour, CPU MARS authority, canonical TIM-MARS parameters,
or scientific evaluation thresholds.

Base commit:
`e9267c6ff3ca5b0f6ee0e0c3d4b671ba08754122`.

Implementation branch:
`issue-64-high-resolution-appearance-crops`.

The implementation commit is the commit containing this report.

## Contracts

`tools/experiments/run_deterministic_tim_replay.py` now has an opt-in
`--appearance-bag` path. Without it, the previous image source and processing
path are unchanged. Controlled mode:

- reads tracks only from the master input bag;
- retains all candidate and output geometry in master/source pixels;
- maps boxes into the alternate image through the existing TIM-MARS appearance
  attachment implementation;
- requires a complete one-to-one set of positive image-header timestamps;
- refuses missing, additional, duplicate, non-positive, or non-matching
  candidate/image timestamps;
- verifies the variant's master stream, output stream, dimensions, frame count,
  and timestamp digests against its provenance;
- never silently falls back to the master image source.

The candidate digest schema
`p064_frozen_candidate_stream_v1` includes processing order, semantic and bag
timestamps, source/frame timing fields, track list order, transport tracker ID,
bbox geometry, confidence, and label. Tracker IDs are included only to prove
that transport evidence is unchanged; they do not define physical identity.

## Variant generation

`tools/experiments/prepare_p064_appearance_variants.py` writes appearance-only
ROS bags by direct complete-frame resize. It preserves positive source header
timestamps and ordering, and records:

- master and output image-stream digests;
- exact timestamp digest;
- dimensions and aspect ratios;
- frame counts;
- interpolation method;
- complete-FOV/no-crop/no-pad/no-letterbox declarations;
- output artifact file hashes;
- resize classification.

Upsampling fails unless explicitly enabled as a labelled
`upsampled_control_not_high_resolution_evidence` condition.

The deployment matrix (640x480, 1280x720, 1920x1080) changes aspect ratio and is
not a pure density experiment. The additional 16:9 sensitivity matrix
(640x360, 1280x720, 1920x1080) isolates density more cleanly.

## Development smoke: VisDrone uav0000339

Source:

`data/datasets/processed/p064/uav0000339_master_bag_view`

This ignored directory is a metadata/symlink view of the retained uncompressed
MCAP; it does not copy or alter the source capture. Native image dimensions are
1904x1071. This must not be described as a true 1920x1080 condition.

The source bag contains 275 image messages. Its first image has a zero header
stamp and is ineligible under the pre-existing deterministic replay contract;
274 positive-stamped frames were therefore transformed and this exclusion is
recorded explicitly.

| Field | Value |
|---|---|
| Master image-stream SHA-256 | `c13f25bfc3f0915e0b278e9de90f9c8d1f2f0eea10374c168788f11d223afb07` |
| Exact timestamp SHA-256 | `2fc6c7cb1403315dc8b4f892b8ac2fbfb85a9a346f95c6a71429e6e820ee8663` |
| Positive appearance frames | 274 |
| Frozen track messages | 203 |
| Frozen candidate SHA-256 | `51624c29b37036bf290940a121855cb5309435fd4d007008f604388778c8b54c` |

Generated development conditions:

| Condition | Appearance-stream SHA-256 | MCAP SHA-256 | Result |
|---|---|---|---|
| 640x360 | `2921bd24e4a56b7ca56d3098808a94fe1f3c2cfad2243f1feaacf85a22459a41` | `06521b1507d1c2dc2f0249f4331d98332bea162852b2b265ecf8a1bfc1bf0c8f` | replay completed |
| 1280x720 | `1ac1cb412ac9aa14fdc5ecfcd4a2b58a3c85f339367cb16371fb2041705fa0f7` | `275bf0112147b3176d1c64f9f16d65a8f65d467b84482d9be7b247fba3f673c1` | replay completed; expected candidate digest enforced |

Both conditions retain the same 274-frame timestamp digest and the same
203-message candidate digest. The 1280x720 run explicitly supplied the
640x360 run's candidate digest and passed the fail-closed equality check.

Default equivalence was checked by executing the exact base-commit replay
script and the modified script with controlled mode disabled against the same
master input. Both produced semantic digest:

`579d3d64a642bf546e02a73b2db72af8d5880fcce26e767b0bfc3f4ec2b04a34`.

The older 7 August retained digest is not the pre/post baseline because
unrelated TIM-MARS implementation changes occurred between that historical run
and the current base commit.

Generated bags and metadata remain ignored under
`data/datasets/processed/p064/`.

## Verification

Focused command:

`python3 -m pytest -q tools/tests/test_p064_appearance_resolution.py tools/tests/test_run_deterministic_tim_replay.py ros2_ws/src/thesis_bringup/test/test_coordinate_time_contract.py ros2_ws/src/thesis_bringup/test/test_appearance_attachment.py ros2_ws/src/thesis_bringup/test/test_tim_mars_runtime.py`

Result: 115 passed. One final verification invocation omitted the ROS overlays and failed during collection before tests ran; the corrected sourced invocation passed completely. The development replays emitted the existing TensorFlow v1/deprecation notices only.

Tests cover exact correspondence, missing/future/duplicate/non-positive
timestamps, frame-count mismatch, provenance mismatch, candidate digest
changes, upsampling protection, complete-FOV generation, 640x360/1280x720/
1920x1080 mapping, all four crop boundaries, high-resolution detector inverse
mapping, and default-off CLI behaviour.

## Limitations and stopping boundary

This is not final Issue #64 scientific evidence:

- VisDrone timing is external dataset timing, not TEVS/ROS live sensor timing;
- 1904x1071 is not 1920x1080;
- no benefit or harm conclusion was drawn from the different TIM outputs;
- no live transport, latency, CPU, RSS, Hailo timing, stale/drop, or recording
  cost was measured;
- no final physical-reference matrix was evaluated;
- genuine TEVS high-resolution master capture and held-out evidence remain
  pending.
