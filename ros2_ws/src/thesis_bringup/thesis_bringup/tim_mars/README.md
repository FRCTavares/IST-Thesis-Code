# TIM-MARS selected-target memory

TIM-MARS is the selected-target memory layer used for safer vision-based UAV
person-following perception. It sits above detection, multi-object tracking, and
raw target selection. Its job is not to improve generic tracking. Its job is to
publish one conservative, controller-facing target state for the selected person.

The core safety principle is simple: when identity evidence is weak, TIM-MARS
prefers uncertainty or no publication over publishing a plausible but possibly
wrong target.

## Canonical thesis configuration

The canonical algorithmic parameter set is stored in:

- `ros2_ws/src/thesis_bringup/config/tim_mars_canonical.yaml`

Its current SHA-256 and the report/commit claim boundaries are recorded in:

- `docs/algorithm/tim_mars_evidence_versions.md`
- `docs/data/catalogue/tim_evidence_versions.json`

“Canonical” identifies current reproducible bytes; it does not make historical
reports interchangeable or imply a universal safety result.

The installed runtime copy is stored in:

- `ros2_ws/install/thesis_bringup/share/thesis_bringup/config/tim_mars_canonical.yaml`

The live stack and the active clean, memory-only, and detector replay runners
load this file through `--params-file`.

Launchers may override only runtime-specific values:

- topic names;
- selected target ID;
- mirror-selection mode;
- appearance image topic;
- local MARS model path;
- live appearance enable or disable state.

Algorithm thresholds and recovery-policy settings must not be duplicated in
launcher scripts.

The former `MARS_TIM_PRESET` shell preset system is no longer part of the active
workflow. Experimental variants must use an explicit alternative YAML file and
record that file with the resulting evidence.

## Runtime data flow

Input topics:
- /tracks
- optional /camera/image_raw
- optional mirrored /target selection

Runtime path:
1. target_memory_mars_node.py receives tracker candidates.
2. Tracks are converted into CandidateTrack objects.
3. Optional MARS appearance embeddings are attached.
4. TargetIdentityMemory.update() evaluates the selected target.
5. The node publishes /target_memory_mars and /target_memory_mars/status.

Inside TargetIdentityMemory.update(), TIM-MARS combines:
- geometry scoring,
- appearance scoring,
- short-gap same-ID protection,
- rank-aware reacquisition,
- hard-negative rejection.

Absence recovery and candidate-belief confirmation remain implemented
experimental policies but are disabled in the canonical configuration.

## State machine

TIM-MARS maintains an internal selected-target state:

NO_TARGET -> LOCKED -> UNCERTAIN -> LOST -> REACQUIRED -> LOCKED

State meanings:
- NO_TARGET: no operator-selected or auto-selected target exists.
- LOCKED: the selected target is considered safe to publish.
- UNCERTAIN: the target is temporarily unreliable, usually after missed or weak evidence.
- LOST: the target has been missing long enough that reacquisition must be conservative.
- REACQUIRED: a candidate has been accepted after uncertainty/loss but needs confirmation before normal locked publication.

## Candidate scoring

Each tracker output is converted into a CandidateTrack. The memory state machine
compares each candidate against the remembered selected target using:
- tracker identity continuity,
- bbox IoU,
- normalized center distance,
- bbox scale similarity,
- detector/tracker confidence,
- optional positive appearance similarity,
- optional hard-negative appearance similarity.

Geometry is always the primary guard. Appearance is used only when configured
and when geometry makes the candidate plausible enough.

TIM-MARS does not add a velocity estimator or motion-prediction model. It
compares candidates with the last trusted bbox; motion models inside ByteTrack,
SORT, OC-SORT, or DeepSORT remain properties of those base trackers.

The score contract deliberately separates candidate ordering from safety
validation:

- `geometry_score` contains identity continuity, bbox geometry, and confidence.
  Geometry acceptance thresholds are applied to this score.
- `ranking_score` is used only to order otherwise plausible candidates. It may
  add appearance evidence and is intentionally not treated as an acceptance
  probability or clipped safety threshold.
- `total` is the legacy, clipped ranking diagnostic retained for compatibility.
  New policy code must use the explicit geometry or ranking field instead.

Appearance evidence also has independent diagnostic states:

- `appearance_available`: the candidate supplied a usable embedding.
- `appearance_evaluated`: the embedding was compared with positive memory.
- `appearance_similarity_passed`: it passed the base appearance threshold.
- `appearance_used`: appearance contributed to candidate ordering.
- `appearance_accepted_for_publication`: the accepted publication had evaluated,
  compatible appearance evidence.

These states must not be collapsed into a single boolean. In the canonical and
conservative appearance-enabled profiles, a candidate with a new tracker ID
must independently pass the configured ID-switch appearance threshold even
when it is the only candidate. Available but contradictory appearance is not
treated as missing evidence and cannot authorize an ID switch on geometry
alone. Same-ID locked continuity remains geometry-led. Geometry-only ID-switch
experiments require the appearance ID-switch and conservative identity gates to
be explicitly disabled in the experiment configuration.

## Appearance memory policy

TIM-MARS can attach MARS ReID embeddings to candidates. The positive appearance
memory is updated conservatively:
- update only when the target is confidently LOCKED,
- freeze during UNCERTAIN, LOST, and REACQUIRED,
- optionally apply a cooldown after reacquisition,
- do not let appearance rescue geometrically implausible candidates.

This avoids learning a distractor during ambiguous recovery.

## Reacquisition safeguards

TIM-MARS includes several safeguards for selected-target recovery:
- same-ID relief: the previous tracker ID can be accepted with reduced threshold.
- short-gap protection: after a brief miss, new IDs can be suppressed while the old ID has a grace window to return.
- rank-aware reacquisition: in lost/uncertain states, candidates can be ranked by appearance evidence rather than raw total score alone.
- absence-aware recovery: after longer absence, new-ID recovery requires stronger geometry and appearance evidence.
- candidate-belief confirmation: plausible new candidates can require repeated observation before acceptance.
- hard-negative memory: distractor appearance prototypes observed while locked can suppress wrong-target recovery.

## ROS role

target_memory_mars_node.py is ROS glue around the pure algorithm. It owns:
- ROS parameter declaration and reading,
- subscriptions to tracks, selection commands, optional image stream, and optional raw target mirroring,
- conversion from Track2DArray to CandidateTrack,
- optional appearance attachment,
- publication of TargetState,
- JSON status diagnostics.

The node should not contain core selection policy. Core policy belongs in
target_memory.py and supporting modules.

## Module map

Modules are grouped by responsibility. Everything except the ROS layer is
ROS-free and Hailo-free.

### Selected-target state machine

- `target_memory.py`: core `TargetIdentityMemory` state machine (accept, reject,
  reacquire, miss, memory commit).
- `types.py`: public dataclasses, enums, and `TargetMemoryConfig`.
- `memory_state.py`: private `_Memory` dataclass and state-to-control-mode
  mapping.
- `candidate_safety_policy.py`: stateless candidate-acceptance safety checks
  lifted out of the state machine.
- `reacquisition_policy.py`: confirmation counters and uncertain/lost/reacquire
  helpers (candidate-belief, absence-aware recovery, appearance-margin,
  geometry-strength, scene-ambiguity risk).

### Scoring

- `geometry_scoring.py`: stateless bbox overlap, centre distance, scale
  similarity, and the base geometric `CandidateScore` (primary safety gate).
- `appearance_policy.py`: how optional appearance evidence modifies a geometric
  score (positive similarity, hard-negative similarity, appearance gating).

### Positive and negative appearance memory

- `positive_appearance_memory.py`: protected anchor, trusted gallery, and
  adaptive prototype (the P1.4 protected/adaptive positive-memory work).
- `hard_negative_memory.py`: bounded distractor-appearance memory.
- `appearance_memory.py`: low-level crop, HSV feature, cosine-similarity, and
  exponential feature-update helpers.
- `crop_quality.py`: pure crop-quality measurement in appearance-image pixels.

### Appearance embedding attachment (in-process, canonical)

- `appearance_attachment.py`: attaches MARS embeddings to `CandidateTrack`
  objects before the state machine; owns image-age checks, crop scheduling,
  identity-safe embedding-cache reuse, and diagnostics.
- `mars_reid_backend.py`: thin wrapper around the DeepSORT MARS-small128
  extractor (`models/reid/mars-small128.pb`, 128-D, CPU).

### Asynchronous Hailo RepVGG offload (optional, Issue #44)

Off by default (`appearance_async_reid_enabled=false`). CPU MARS stays
authoritative for TIM-MARS decisions; this path is used for embedded
appearance-offload measurement. Request flow:

`appearance_request_policy` (which candidates need an embedding)
-> `appearance_request_producer` (stage owned immutable BGR crops)
-> `appearance_request_transport` (causal in-flight ledger over the async boundary)
-> `appearance_ros_transport` (strict ROS message conversion)
-> `AppearanceEmbeddingRequest` on `/appearance/reid/request`
-> `perception_pipeline_node` Hailo RepVGG worker
-> `AppearanceEmbeddingResult` on `/appearance/reid/result`.

- `appearance_async.py`: ROS-free causal request/result lifecycle contract.
- `appearance_request_policy.py`: pure per-candidate request decision.
- `appearance_request_producer.py`: pure staging of causally identified crops.
- `appearance_request_transport.py`: TIM-owned causal ledger for RepVGG
  transport.
- `appearance_ros_transport.py`: strict ROS conversion for the async messages.
- `appearance_worker.py`: hardware-independent worker boundary (injected
  preprocess/infer/postprocess; used for deterministic tests).
- `repvgg_reid_adapter.py`: pure RepVGG pre/post-processing and the tracked-HEF
  tensor contract (UINT8 NHWC 256x128x3 in, 512-D out).

### Shared runtime and ROS layer

- `runtime.py`: ROS-free processing runtime — tracker messages to
  `CandidateTrack`, causal image selection, appearance attachment, and
  `TargetIdentityMemory.update()`.
- `ros_params.py`: ROS parameter declaration and conversion to
  `TargetMemoryConfig`.
- `ros_messages.py`: pure TIM outputs to ROS messages and JSON diagnostics.
- `target_memory_mars_node.py`: the ROS 2 node wiring subscriptions,
  publications, image handling, and the async ReID transport.

## Final thesis note

For thesis evaluation, TIM-MARS should be treated as a control-facing safety
layer. It is not a replacement for the detector or tracker. Its contribution is
conservative selected-target publication under identity ambiguity, short target
loss, distractors, and tracker ID instability. The interface is tracker-modular,
but safety is not tracker-independent. The current development evidence is not
flawless and must not be presented as a zero-wrong-target or held-out result.
