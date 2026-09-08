# TIM-MARS AB-16 production regression (Stage-5) — 2026-09-08

Development regression only. **H01/H02/H03 were not accessed, listed, hashed, replayed, annotated, evaluated or captured.** This is **not** the Stage-7 prospective freeze: no prospective algorithm/configuration/split/comparison freeze is created or altered, and no historical Stage-1 evidence file was modified. The Issue #27 frozen contracts (`tim_mars_split_v3.json`, `tim_mars_final_comparison_v2.json`, `P027_HELDOUT_EXECUTION_PLAN.md`) are untouched.

**Verdict: PASS**

## Provenance

| Item | Value |
| --- | --- |
| Branch | `tim-mars-ab16-production-promotion-20260908` |
| Source commit | `75147ecb0e4edce81f54aea1b303a25df0572d45` |
| Base Stage-1 merge commit | `d3edbcc537b92f5ef66771911015e620fc7467d2` |
| Canonical config SHA-256 | `b0a98334cadf635aa831d1bbe335f172686339f81def3efd2200211479c50f8c` |
| Selected-dev-baseline config SHA-256 | `a8c8092199f6ad7659ef00226e77b3181b72c9e2fb89bb0e8e2c86c91a43cd5c` |
| MARS model SHA-256 | `e96f3cc09dbce76e2f6aeff09c8f2502916b4745f21e27911ee50d102a4a75f1` |
| Pinned environment | `docs/results/selected_target_tracking/tim_pinned_replay_env_20260908.sh` (sha256 `24f8c09f4d041c0f…`) |
| Effective toolchain | Python 3.12.3, numpy 1.26.4, tensorflow 2.17.1, aarch64, nproc 4 |
| Resolved-runtime schema | v4 |

Pinned thread/determinism environment applied to every run: `TF_DETERMINISTIC_OPS=1`, `TF_ENABLE_ONEDNN_OPTS=0`, `TF_NUM_INTRAOP_THREADS=1`, `TF_NUM_INTEROP_THREADS=1`, `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, `MKL_NUM_THREADS=1`.

## Configurations

- **Baseline-control** — selected development baseline (`available_image_challenge.yaml`); production AB-16 absent (→ `False`), development AB-16 ablation control `False`, all other development-ablation controls `False`. Canonical YAML was **not** modified. 1 run per sequence.
- **Production candidate** — canonical production configuration (`tim_mars_canonical.yaml`), AB-16 activated through the production `TargetMemoryConfig` / ROS parameter path (`appearance_prevent_repeated_source_adaptive_update: true`); development AB-16 flag `False`; all other development-ablation controls `False`. `min_confirm_frames_after_reacquire` stays `1` (AB-14 not promoted). 3 runs per sequence.
- **Historical AB-16 equivalence** — selected development baseline + `--ablation-prevent-repeated-source-adaptive-update` (historical Stage-1 activation path). 1 run per sequence.

## Gate results

| Gate | Result |
| --- | --- |
| B — baseline-control reproduces the pinned selected baseline | PASS |
| C — production candidate 3/3 repeatable per sequence | PASS |
| D — candidate-input stream identical & matches frozen SHA-256 | PASS |
| E — controller-facing physical-v2 + `/target_memory_mars` byte-equal to baseline | PASS |
| F — state / proposal-path / persistence / challenge scheduling equal to baseline | PASS |
| G — only the adaptive-EMA trajectory changes; anchor/gallery/reasons intact; counts match Stage-1 AB-16 | PASS |
| H — hard-negative transactions unchanged | PASS |
| I — MARS appearance workload byte-equal to baseline (no inference change) | PASS |
| Part 3 — production AB-16 == historical Stage-1 AB-16 treatment (semantic + streams identical) | PASS |

## Per-sequence

### Baseline-control reproduction (vs retained pinned selected baseline)

| Sequence | Semantic SHA-256 | Reproduces pinned baseline | correct / wrong / LOST / absent (s) | adaptive updates |
| --- | --- | :--: | --- | ---: |
| May hard re-entry | `9eb017711275e98b…` | yes | 62.796329712 / 0.033394241 / 5.035185821 / 0.000000000 | 800 |
| Seq01 clean | `7754d5717a587f5e…` | yes | 61.200516816 / 0.000000000 / 0.000000000 / 0.000000000 | 1512 |
| Seq03 crossing | `ca1f1826e2092a03…` | yes | 24.600414282 / 0.000000000 / 59.166383501 / 0.000000000 | 524 |
| Seq04 occlusion / no-exit | `d7da756a5220a06e…` | yes | 48.766241082 / 0.000000000 / 23.733800690 / 0.000000000 | 839 |

### Production candidate (3 repeats/sequence, pinned environment)

| Sequence | Semantic SHA-256 (3/3) | `/target_memory_mars` SHA-256 (3/3) | correct / wrong / LOST / absent (s) | Δ vs baseline-control | adaptive updates |
| --- | --- | --- | --- | --- | ---: |
| May hard re-entry | `a19b451ed7037802…` (ok) | `18102c37b6c515ee…` (ok) | 62.796329712 / 0.033394241 / 5.035185821 / 0.000000000 | correct +0.000000000, wrong +0.000000000, absence +0.000000000 | 219 |
| Seq01 clean | `981a6fed40b80068…` (ok) | `b7bba484f5f27371…` (ok) | 61.200516816 / 0.000000000 / 0.000000000 / 0.000000000 | correct +0.000000000, wrong +0.000000000, absence +0.000000000 | 231 |
| Seq03 crossing | `689ac655e00433bd…` (ok) | `f262442ed88faa94…` (ok) | 24.600414282 / 0.000000000 / 59.166383501 / 0.000000000 | correct +0.000000000, wrong +0.000000000, absence +0.000000000 | 124 |
| Seq04 occlusion / no-exit | `0bf20a0ed74259a0…` (ok) | `320fe8576282536c…` (ok) | 48.766241082 / 0.000000000 / 23.733800690 / 0.000000000 | correct +0.000000000, wrong +0.000000000, absence +0.000000000 | 718 |

### Adaptive positive-memory update counts (`trusted_locked_adaptive_update`)

| Sequence | Baseline-control | Production AB-16 | Known Stage-1 AB-16 | Match |
| --- | ---: | ---: | ---: | :--: |
| May hard re-entry | 800 | 219 | 219 | yes |
| Seq01 clean | 1512 | 231 | 231 | yes |
| Seq03 crossing | 524 | 124 | 124 | yes |
| Seq04 occlusion / no-exit | 839 | 718 | 718 | yes |
| **Total** | **3675** | **1292** | **1292** | yes |

Aggregate reduction 3675 → 1292 (64.84%). This is a redundant adaptive-EMA reinforcement reduction only; MARS appearance inference workload is byte-identical to the baseline on every sequence (gate I) and no inference saving is claimed.

### Production AB-16 vs historical Stage-1 AB-16 treatment

| Sequence | Semantic equal | Status-scan equal | physical-v2 equal | `/target_memory_mars` equal | activation-source distinguished |
| --- | :--: | :--: | :--: | :--: | :--: |
| May hard re-entry | yes | yes | yes | yes | `production_config` vs `development_ablation` |
| Seq01 clean | yes | yes | yes | yes | `production_config` vs `development_ablation` |
| Seq03 crossing | yes | yes | yes | yes | `production_config` vs `development_ablation` |
| Seq04 occlusion / no-exit | yes | yes | yes | yes | `production_config` vs `development_ablation` |

Production AB-16 and the historical Stage-1 AB-16 treatment produce byte-identical generated output under identical inputs and environment; only the resolved-runtime provenance (`repeated_source_adaptive_update.activation_source`) distinguishes production-configuration activation from the development-ablation flag.

## Safety gate

Every sequence: no wrong-person-authority increase, no new or relocated wrong-person interval (the `/target_memory_mars` stream is byte-identical to the baseline, so May's retained ~0.033394241 s wrong interval is neither moved, extended nor replaced), no target-absence leakage, no same-ID hijack regression, no delayed Seq03 hijack revocation (identical `REACQUIRED`/`LOST` timing and `global_identity_reacquisition` proposal counts), no new identity switch, and no rejected candidate mutating trusted positive memory (protected-anchor initialisation counts and the controller-facing stream are unchanged).

## Retained low-level evidence

- `reports/tim_ab16_prod_regression_20260908/<mode>/<seq>/<rep>/` — per-run `provenance.json`, `tim_target_memory.json` (physical-v2), `raw_target.json`, `status_scan.json`, `environment.json`, replay stdout/stderr.
- `reports/tim_ab16_prod_regression_20260908/s5_analysis.json` — full machine-readable gate analysis.
- Replay bags: `bags/replay/tim_s5_<mode>_<seq>_<rep>_20260908` (ignored per repository convention).
