# TIM-MARS deterministic-replay semantic re-baseline (numerical reproducibility) — 8 September 2026

Development-only evidence. **H01/H02/H03 were not accessed, captured or inspected.**
No algorithm, configuration, tracker setting, model, bootstrap rule or evaluation
semantic is changed by this document. The Issue #27 frozen contracts
(`docs/data/splits/tim_mars_split_v3.json`,
`docs/data/splits/tim_mars_final_comparison_v2.json`,
`docs/flight/P027_HELDOUT_EXECUTION_PLAN.md`) are untouched.

This is a **numerical-reproducibility re-baseline only**, not a behavioural or
algorithmic re-freeze. The historical selected semantic SHA-256 values are
preserved unchanged as historical evidence; the retained mechanism-ablation
evidence files (`tim_ablation_stage1_2x2_20260907.*`,
`tim_ablation_stage1_mechanisms_20260908.*`,
`tim_ablation_stage1_positive_memory_20260908.*`) are **not modified**.

## 1. Problem

On 8 September 2026 the retained selected-development semantic SHA-256 digests
stopped reproducing on the development Raspberry Pi. Re-running the retained
selected replay bags produced new semantic digests while every controller-facing
quantity stayed byte-identical:

| Sequence | Historical selected semantic SHA-256 | Re-run (uncontrolled env) | physical-v2 correct/wrong/LOST/absent |
| --- | --- | --- | --- |
| May   | `252829b914efdb81876a41bda5494985db4ddcf0f07d8a9de267c91415a13cd9` | `c5aaa04ca5f76c953f5a5c60e285264a8bcdf7dfb846bbf01a2a76648290c868` | byte-identical (62.796329712 / 0.033394241 / 5.035185821 / 0) |
| Seq03 | `307c9c3c2d5ad0f468a452ec8b753552a276e51d3fcd85381158bc13c93811ca` | `279890dd79c95a17bef9772274db0cb376cb7687eb8fe6fc755103dbe821af35` | byte-identical (24.600414282 / 0 / 59.166383501 / 0) |
| Seq04 | `ff818a434e52a4c5f6733846434cc455f6501182ac4632a2f4da65cc68e6d980` | `26a79d6f5c711fdc76f9b58537788bc0bd72e8edaf44154287069bd46eb6dc3e` | byte-identical (48.766241082 / 0 / 23.733800690 / 0) |

The candidate-stream SHA-256 of every frozen ByteTrack input matched exactly
(`a85270138a46cb51888dc2656d3525647109647fa69886f39024e3ec9cab8d8d` May,
`1c9b90773a86c1dc5739d7af5617268a60f6c109086ac5354e1a14825a04ac2b` Seq01,
`60e41fb14822af5a04b781ac08a6a75e7a05382a9bd55629a737a325512582db` Seq03,
`9c514facb5cd946a02800885e8bacb9ea9fb0132d6ceab4c73e7f4a30ce3c3bf` Seq04).

## 2. Root cause

Frame-by-frame diff of `/target_memory_mars/status` between a retained bag and a
fresh re-run: TIM `/target`, raw `/target`, `TargetState` counts and every
physical-v2 duration bucket are byte-identical; the only differences are
appearance-similarity **diagnostics** drifting at the 7th decimal, e.g. Seq03
frame 3:

    adaptive_similarity   0.9875444762435244  ->  0.9875445365905762   (~6.1e-8)
    candidate_score       0.6229282401001759  ->  0.6229282380604020   (~2e-9)
    appearance_margin_best_vs_second : same ~6.1e-8 drift

`tim_mars_replay_generated_fields_v5` hashes the full status JSON string, so any
such drift changes the semantic digest.

The MARS-small128 extractor
(`thesis_tracker/backends/deepsort_core_backend.py::MarsSmall128Extractor`)
builds its `tf.compat.v1` session with a bare `ConfigProto` — it sets **no**
`intra_op_parallelism_threads` / `inter_op_parallelism_threads`. TensorFlow
2.17.1 CPU then picks its thread count from the live machine state (load,
available cores, throttling). The reduction order inside the conv/matmul ops is
thread-count dependent, so the 128-D embeddings — and every appearance
similarity computed from them — drift by ~1e-7 between runs taken under
different machine states. `numpy` (EMA + L2-norm) is single-threaded and not
implicated; `cv2` crop/resize is deterministic.

The digest is fully reproducible **within** a fixed machine/thread state (the
uncontrolled re-run reproduced `279890dd…` 3/3), which is why the historical
freeze and the 8 September mechanism-ablation neutrality runs were internally
consistent at the time they were taken.

## 3. Investigation

Seq03 selected/neutrality workload, N runs per candidate environment:

| Environment | Seq03 semantic SHA-256 | runs identical | note |
| --- | --- | --- | --- |
| uncontrolled (auto threads) | `279890dd79c95a17bef9772274db0cb376cb7687eb8fe6fc755103dbe821af35` | 3/3 | machine-state dependent value |
| `TF_ENABLE_ONEDNN_OPTS=0` only | `279890dd79c95a17bef9772274db0cb376cb7687eb8fe6fc755103dbe821af35` | 3/3 | **oneDNN toggle is a no-op on TF 2.17.1 aarch64 — NOT required** |
| threads=1 + `TF_DETERMINISTIC_OPS=1` | `ca1f1826e2092a03c36b73015045d55c55dc232046b28871e769b85200079eaf` | 3/3 | machine-state independent |
| full (threads=1 + onednn off + deterministic) | `ca1f1826e2092a03c36b73015045d55c55dc232046b28871e769b85200079eaf` | 5/5 | identical to threads=1 |

Total pinned runs on Seq03: **11/11 identical** (`ca1f1826…`), across the probe
and the three baseline repeats.

`TF_ENABLE_ONEDNN_OPTS=0` was tested explicitly per the reproducibility brief:
it produces **no change** (uncontrolled == onednn_off; threads1 == full). It is
retained in the pinned environment only as a defensive pin against a future TF
build that enables oneDNN with non-deterministic threading.

## 4. Pinned environment (adopted)

`docs/results/selected_target_tracking/tim_pinned_replay_env_20260908.sh`:

    export TF_DETERMINISTIC_OPS=1
    export TF_ENABLE_ONEDNN_OPTS=0
    export TF_NUM_INTRAOP_THREADS=1
    export TF_NUM_INTEROP_THREADS=1
    export OMP_NUM_THREADS=1
    export OPENBLAS_NUM_THREADS=1
    export MKL_NUM_THREADS=1

Recorded toolchain (see each run's `environment.json`): Python 3.12.3,
numpy 1.26.4, tensorflow 2.17.1, Linux aarch64, nproc 4.

Operative settings: the five thread pins force a single-threaded, fixed
reduction order; `TF_DETERMINISTIC_OPS=1` selects deterministic op kernels.

## 5. New pinned selected-development semantic baselines

Config `docs/results/selected_target_tracking/tim_resilience_development_20260907/available_image_challenge.yaml`
SHA-256 `a8c8092199f6ad7659ef00226e77b3181b72c9e2fb89bb0e8e2c86c91a43cd5c`;
model `models/reid/mars-small128.pb` SHA-256
`e96f3cc09dbce76e2f6aeff09c8f2502916b4745f21e27911ee50d102a4a75f1`;
runner `tools/experiments/run_deterministic_tim_replay.py` at branch
`tim-mars-same-id-hijack-resilience-20260907`, default-off development ablation
controls, `SEMANTIC_DIGEST_SCHEMA = tim_mars_replay_generated_fields_v5`.

| Sequence | Historical semantic SHA-256 (preserved) | **New pinned semantic SHA-256** | candidate-stream SHA-256 | repeats |
| --- | --- | --- | --- | --- |
| May   | `252829b914efdb81876a41bda5494985db4ddcf0f07d8a9de267c91415a13cd9` | `9eb017711275e98bbba6f6b35ea30b1be036aac730c222a9686dd8ef446fa63b` | `a85270138a46cb51888dc2656d3525647109647fa69886f39024e3ec9cab8d8d` | 3/3 |
| Seq01 | `97b1f3ca36a75d4fe2f679c250fa8f53675b536001cf168572681f53d075e4f5` | `7754d5717a587f5ee596f00a5aa2402e11386856b52b6a5d8f0ce7f84103dce2` | `1c9b90773a86c1dc5739d7af5617268a60f6c109086ac5354e1a14825a04ac2b` | 3/3 |
| Seq03 | `307c9c3c2d5ad0f468a452ec8b753552a276e51d3fcd85381158bc13c93811ca` | `ca1f1826e2092a03c36b73015045d55c55dc232046b28871e769b85200079eaf` | `60e41fb14822af5a04b781ac08a6a75e7a05382a9bd55629a737a325512582db` | 11/11 |
| Seq04 | `ff818a434e52a4c5f6733846434cc455f6501182ac4632a2f4da65cc68e6d980` | `d7da756a5220a06e35ada759c5a7a7cafbf678e5c7102d31b35028c996a4c5ca` | `9c514facb5cd946a02800885e8bacb9ea9fb0132d6ceab4c73e7f4a30ce3c3bf` | 3/3 |

## 6. Behavioural equivalence to the retained selected baseline

For every sequence, the pinned baseline vs the retained selected reference bag:

| Sequence | physical-v2 buckets | reconciliation | `TargetState` counts | proposal-source counts | reason-prefix counts | TIM `/target` frame-by-frame | raw `/target` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| May   | byte-identical | ok, residual 0 | identical | identical | identical | identical | identical |
| Seq01 | byte-identical | ok, residual 0 | identical | identical | identical | identical | identical |
| Seq03 | byte-identical | ok, residual 0 | identical | identical | identical | identical | identical |
| Seq04 | byte-identical | ok, residual 0 | identical | identical | identical | identical | identical |

No new wrong-person authority (May stays 0.033394241 s, others 0). No new
target-absence leakage (0 s on all). Localisation/reconciliation unchanged.

## 7. Why this does not alter the selected algorithm

- Only environment variables changed; no source file, YAML, ROS parameter,
  launch file or evaluator was modified for reproducibility purposes.
- The pinned environment changes the floating-point reduction order of MARS CPU
  inference by ~1e-7; it does not change which candidate is selected, which
  state is entered, which output is published, or any physical-v2 bucket, on any
  of the four permitted development sequences.
- The historical semantic SHA-256 values remain valid historical evidence of
  the behaviour frozen under the earlier (uncontrolled) machine state and are
  preserved verbatim in the retained evidence files.

## 8. Forward comparison contract

From 8 September 2026, the Stage-1 semantic comparison contract is:

    NEW PINNED SELECTED BASELINE  vs  PINNED TREATMENT

both produced under `tim_pinned_replay_env_20260908.sh`. A pinned treatment
semantic SHA-256 is **never** compared directly against a historical
uncontrolled-environment semantic SHA-256. Candidate-stream SHA-256 and
physical-v2 references are unchanged and are still verified on every run.

Evidence artefacts: `reports/tim_ablation_stage1_pinned_probe_20260908/` (probe),
`reports/tim_ablation_stage1_pinned_20260908/baseline_r{1,2,3}/` (baselines);
helper scripts under `reports/tim_ablation_stage1_20260908/_helpers/`.
