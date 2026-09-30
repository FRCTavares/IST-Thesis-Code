# tools/issues/p125

Last reviewed: 2026-09-30

## P125 — Public VisDrone selected-person benchmark

Issue #125 adds the final broad public-dataset selected-person evaluation.

This directory is intentionally issue-scoped because the benchmark has a
prospective pre-result freeze contract. Reusable production algorithms stay in
their existing locations and must not be copied here.

Frozen protocol tooling:

- `audit_visdrone_selected_person_corpus.py` performs the GT-only corpus and
  frame-domain audit. It may read source images and official VisDrone ground
  truth only. It must not read detector, tracker, Target-ReID, TIM-MARS, or
  previous result artifacts.
- `build_visdrone_gt_only_episode_manifest.py` combines the train and
  validation audits only after reconciled frame-domain, eligibility-config,
  identity, and episode-count checks. It hashes both source archives and
  both audit files, and writes a deterministic draft manifest. Reproduction
  output must go to a temporary path because the tracked manifest is frozen.
- `evaluate_visdrone_selected_person.py` defines the four primary
  physical-person frame buckets and scores one selected identity through its
  last target observation. Missing GT rows stay outside the primary denominator.
  Core wrong-person, handover, LOST-run, first output after LOST,
  reference-gap/reacquisition and attributable target tracker-ID-change events
  are derived from source-frame records. The scorer requires one explicit
  output entry for every source frame from selection through the final
  target GT observation, including GT gaps; `None` means no controller output.
  Per-frame target GT height, occlusion and truncation support predeclared
  stratification; the correct-only localization summary averages target IoU
  and is null when there are no correct frames. All six arm adapters feed
  this scorer through frozen-only sequence commands.
- `controller_output_adapter.py` maps the four raw tracker backend outputs,
  Target-ReID publications, and control-valid TIM-MARS publications into the
  scorer's box and tracker-ID maps. Suppressed TIM-MARS candidate belief is
  excluded. These adapters are synthetic-tested; they do not execute runtimes.
- `shared_detector_cache.py` delegates image preparation and coordinate
  mapping to production preprocessing, applies the frozen person/score filter,
  and requires exact source-frame coverage. Its cache document builder
  rejects any protocol that is not frozen. The input gateway also requires the
  protocol and episode manifest to match HEAD and share a freeze commit. A
  ROS-backed synthetic check compares the cache's mapped boxes with the
  live perception node's detection publication method without Hailo inference.
- `write_shared_detector_cache.py` prepares one frozen-manifest sequence,
  invokes the existing direct Hailo engine once per image, and writes an
  immutable cache under ignored artifacts. Its committed-freeze check runs
  before any image or Hailo engine is opened. A fake engine and synthetic
  images tested the writer; all seven validation sequences now have
  real same-HEF immutable detector caches.
- `run_same_hef_detector_parity_smoke.py` uses the frozen YOLOv8s HEF on fixed
  validation frames 1–3 of `uav0000086_00000_v`. It compares direct-cache
  preprocessing and detections against the production perception node's
  frame-preparation and publication methods. All 59 person detections matched
  in source pixels and score within the recorded tolerances; the immutable
  ignored report SHA-256 is
  `ee6c321156f6a0309c2c395ece9f5f1e800bfe4cfabf6340fe27d73bcacde8c4`.
  The check uses node methods directly and does not test ROS scheduling.
- `replay_shared_detector_cache.py` validates cache provenance and exact
  image-frame coverage, then feeds one cached detection stream into a supplied
  canonical tracker backend. It applies each tracker's YAML minimum score and
  uses a declared nominal 30 Hz logical replay clock from the canonical
  ByteTrack configuration so image and track updates align. The source image
  files lack capture timestamps, so this clock is an assumption; TIM-MARS
  millisecond policies run against it and results must not claim measured time.
  Fake-backend tests and seven real validation sequence replays have run.
- `write_raw_tracker_replay.py` is the frozen-only one-sequence command for
  SORT, ByteTrack, OC-SORT and DeepSORT. It verifies the shared detector cache,
  source files, model/config hashes and frame domain before using the existing
  production tracker constructor. DeepSORT receives the matching BGR image
  before each logical-frame update. Four raw replays completed on all seven
  validation sequences after the freeze.
- `resolve_episode_initialization.py` applies the existing frozen-target
  unique-IoU confirmation rule to each GT episode after tracker replay. Raw
  controller authority starts on the confirmation frame; failed
  initialization stays explicit and publishes no target. Only synthetic
  tracker records have been used in tests.
- `score_raw_tracker_sequence.py` is the frozen-only raw-arm scoring command.
  It validates replay provenance, loads the frozen GT episodes, retains each
  per-tracker initialization result, and applies the common physical-person
  scorer. The four raw arms have scored all validation sequences.
- `target_reid_episode.py` adapts one confirmed ByteTrack selection to the
  existing Target-ReID runtime. The confirmation frame only bootstraps the
  appearance anchor. Failed tracker initialization or anchor bootstrap leaves
  explicit no-output records for the episode; later output uses only published
  Target-ReID decisions. Its timing and failure paths are synthetic-tested.
- `write_target_reid_sequence.py` is the frozen-only Target-ReID 0.90 sequence
  scorer. It validates the ByteTrack replay and frozen model/config/source
  hashes, shares one MARS extractor across fresh per-episode anchors, and
  records every episode's initialization and bootstrap status. All
  seven validation sequences have completed this arm.
- `tim_mars_episode.py` applies the confirmed ByteTrack selection to the
  existing TIM-MARS runtime and maps only control-valid publications into
  the common scorer. Failed initialization remains explicit no-output.
- `write_tim_mars_sequence.py` is the frozen-only ByteTrack + canonical
  TIM-MARS sequence scorer. It verifies frozen replay and implementation
  hashes, loads the canonical runtime configuration through the existing
  deterministic replay builder, and gives each episode fresh target memory
  while sharing one MARS extractor. All seven validation sequences
  have completed this arm.
- `analyse_visdrone_selected_person_statistics.py` implements fixed-seed
  paired episode effects, source-sequence cluster bootstrap and the primary
  cluster sign-flip test. It has only been exercised on synthetic data.

- `summarize_visdrone_selected_person_corpus.py` reconciles detector,
  tracker and six-arm score hashes against the frozen manifest; it checks
  four-bucket frame totals and reports the ByteTrack-initialisable and common
  raw-tracker subsets. Formal frozen statistics run only for `--split all`.
- `run_visdrone_selected_person_corpus.py` runs the frozen sequence stages
  in order and verifies existing immutable outputs before skipping them. Use
  `--dry-run` to inspect pending stages and `--max-sequences` for a bounded run.
  Source ROS setup must be loaded by the calling shell.

The protocol and GT-only manifest were frozen together after archive, audit,
manifest and implementation-hash checks. The same-HEF smoke passed before
sequence outcomes. Real output remains under ignored `artifacts/reports/`;
the nominal replay clock is an assumption, not measured capture time.
