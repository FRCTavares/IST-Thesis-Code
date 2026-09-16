# Issue #27 — Held-Out Capture and Annotation-Preparation Checkpoint

Date: 15 September 2026

Status: source acquisition and annotation preparation complete; human
physical-v2 annotation, reviewed release and final evaluation pending.

## Frozen authority

The accepted captures were acquired after the Stage-7 prospective freeze:

- split: `tim_mars_split_v4_2026_09_08`;
- algorithm authority:
  `79f11b631688889bf5ffbeb3c16ef543a53f9973`;
- canonical TIM-MARS SHA-256:
  `b0a98334cadf635aa831d1bbe335f172686339f81def3efd2200211479c50f8c`.

The source-only contract retained exactly `/camera/image_raw` and
`/detections`. Tracker, TIM-MARS, controller and MAVROS were disabled for the
held-out source acquisition. The resolved perception configuration still had
`publish_dashboard_topic=true`, but `/camera/dashboard` was not retained in the
held-out bag and has no role in the held-out evidence contract.

## Accepted source captures

| Sequence | Accepted source path | Capture duration | Raw images | Detections | MCAP bytes | Recorder transport losses |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| H01 exit/re-entry | `bags/source/held_out/2026-09/h01_exit_reentry/2026-09-15__16-31-10__source__p027_h01_exit_reentry__image_raw_detections` | 62.132661226 s | 1825 | 1865 | 1,684,445,781 | 38 |
| H02 crossing | `bags/source/held_out/2026-09/h02_crossing/2026-09-15__16-35-33__source__p027_h02_crossing__image_raw_detections` | 51.445882423 s | 1513 | 1544 | 1,396,667,282 | 30 |
| H03 occlusion/distractor | `bags/source/held_out/2026-09/h03_occlusion_distractor/2026-09-15__16-55-25__source__p027_h03_occlusion_distractor__image_raw_detections` | 49.465997660 s | 1460 | 1485 | 1,347,803,642 | 24 |

The non-zero recorder transport-loss observations are retained as capture
provenance. They were not used to inspect or judge algorithm performance.

An earlier H03 attempt at `2026-09-15__16-41-41` is retained as a rejected
recording-integrity attempt. Its MCAP exists, but final `metadata.yaml` and a
complete recorder-finalization record are absent. The rejection is therefore
based on source-evidence integrity, not algorithm outcome. The accepted H03
source is the later `16-55-25` run above.

## Independent preservation

Each accepted source directory was duplicated to independent Mac storage and
verified byte-for-byte by SHA-256. The associated live-stack capture-log
directories were also copied independently; all four retained files for each
accepted run match the Pi originals exactly.

Accepted source payload SHA-256 values:

| Sequence | `metadata.yaml` | MCAP payload | `run_metadata.json` |
| --- | --- | --- | --- |
| H01 | `9a502cbec94e010cd8b2c1e1d2daa199a31c1666429f8e32eefd12cb6b7cd64a` | `9d902ecf68c570e677db6ff004b547cd01c5c979c737aa249c0de385307fe259` | `fa7d15282cd7aa8ba8d3bbee645017469452d9caa5039f112d6a9e3841b68df1` |
| H02 | `6dcce151a235702932c37cd5c9820d20bc7bb23a12b6f369d109e088039755d6` | `39bb5f2d1d5963d08534d9d72869e6752809028fd9bdd17826a5a14ba6139fc1` | `639abc4f6988a0c5c93bb9265bbac0f934a439b88658a4ccc1c74d52e68117f1` |
| H03 | `1f3a09717b6ada3971f91b781c92abe722db0bd5c3ffd0fb61c0572d944c1855` | `4575a0b1679afe039b9f5137d9d9212dbee1a005dd9d300a1ca809a728948053` | `c03a4806cf8baa23e323b3c9ff2026754792a1493ea812c423ad50b27c10099f` |

## Human annotation preparation

Working CVAT packages were generated locally from the accepted source images at
their native 640x480 geometry.

| Sequence | Frames | Evaluation window | CVAT image archive SHA-256 |
| --- | ---: | ---: | --- |
| H01 | 1825 | 0.000000000--62.066439517 s | `6d596f2b085d7ae27294c2e7ee9c8fed264a0adb88434599f8b19ffaed72e8bd` |
| H02 | 1513 | 0.000000000--51.399725327 s | `9bbc5f7f11259c9df80f5ca37bef2ed28ece4c75ae161e8d07812d1bb8cf6b46` |
| H03 | 1460 | 0.000000000--49.433053780 s | `ea8e14d177f94de25593db3f7dea9a01b4d6c2080513ca5679160fe4dee792fe` |

All three generated conversion configurations remain
`human_review_required`, with `semantic_intervals=[]`. No accepted physical-v2
reference exists yet.

Anonymous physical-role coding for the annotation workflow is:

- `sep15_p001`: target, blue shirt and shorts;
- `sep15_p002`: `phys_d001`, lighter blue T-shirt;
- `sep15_p003`: `phys_d002`, woman with cap and lighter striped clothing.

The same three physical participants were present in
`june19_four_person_group_A`, but all used completely different clothing on
15 September. According to the annotator's direct session knowledge, none of
these participants appeared in the May recording and no May outfits were
reused. Historical May participant/outfit coding is incomplete, so that part of
the overlap record remains explicitly based on annotator session knowledge
rather than archived May participant codes.

## Release state

H01 completed human CVAT review on 16 September 2026. The raw export was
preserved unchanged, the conversion-only export and reviewed semantic sidecar
were hashed, and the resulting physical-v2 reference validated against all 1825
manifest frames. The accepted reference is
`docs/data/physical_target_references/heldout_h01_exit_reentry.json`, SHA-256
`63361fb28372913886fc5735c7d9067c5ec24212627ccddf0a6370c4d8469042`.
The completed annotation/reference package was also verified byte-for-byte on
independent Mac storage before release.

The reviewed H01 ready-entry proposal was then applied explicitly. H01 is now
`ready`; H02 and H03 remain `reserved_pending_capture` pending their own
independent human physical-v2 annotation and reviewed finalization.

Current release state is:

    final_ready=1/3

The normal split validator passes with verified hashes, while
`--require-final-ready` still fails closed because H02 and H03 are not ready.
No tracker/TIM-MARS correctness, architecture result, threshold decision,
bootstrap choice or held-out score has been inspected or used during this
capture/preparation stage. The final Issue #58 held-out runner remains forbidden
until all three reviewed ready-entry patches have been applied sequentially and
the `--require-final-ready` validator exits successfully at `3/3`.
