# TIM-MARS deterministic-replay pinned numerical environment — 8 September 2026
#
# PURPOSE
#   Make the MARS/TensorFlow appearance-embedding path in
#   tools/experiments/run_deterministic_tim_replay.py bitwise reproducible
#   across machine states (system load, available cores, thermal throttling).
#
# WHY THIS EXISTS
#   TensorFlow 2.17.1 CPU inference on aarch64 selects its intra-op thread
#   count automatically from the machine state. The reduction order inside the
#   MARS-small128 conv/matmul ops depends on that thread count, so the 128-D
#   embeddings drift by ~1e-7 between runs taken under different machine states.
#   That drift does not change any controller-facing output, TIM state, or
#   physical-v2 duration bucket, but it does change appearance-similarity
#   diagnostics in /target_memory_mars/status and therefore the
#   `tim_mars_replay_generated_fields_v5` semantic digest.
#
#   Investigation (docs/results/selected_target_tracking/
#   tim_pinned_replay_semantic_rebaseline_20260908.md):
#     - default (auto threads) .............. Seq03 semantic 279890dd... x3 identical
#     - TF_ENABLE_ONEDNN_OPTS=0 only ........ Seq03 semantic 279890dd... x3 identical
#         => the oneDNN toggle is a NO-OP on this TF 2.17.1 aarch64 build and is
#            NOT required for reproducibility; it is kept below only as a
#            defensive pin against a future TF build that enables oneDNN.
#     - threads pinned to 1 + TF_DETERMINISTIC_OPS=1 .. Seq03 semantic ca1f1826... x3
#     - full (threads=1 + onednn off) ....... Seq03 semantic ca1f1826... x5
#     => 8/8 pinned runs identical; physical-v2 buckets, state counts and
#        proposal routing byte-identical to the historical retained selected
#        baseline.
#
# CONTRACT
#   Source this file before every deterministic TIM-MARS replay whose semantic
#   digest is compared against a pinned baseline. All pinned Stage-1 baselines
#   and all pinned ablation treatments MUST use exactly this environment.
#   This changes NO algorithm, NO configuration, NO #27 frozen contract; it is
#   a numerical-reproducibility pin only.

export TF_DETERMINISTIC_OPS=1
export TF_ENABLE_ONEDNN_OPTS=0
export TF_NUM_INTRAOP_THREADS=1
export TF_NUM_INTEROP_THREADS=1
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1

# Recorded reference toolchain (informational; see per-run environment.json):
#   Python 3.12.3 | numpy 1.26.4 | tensorflow 2.17.1 | aarch64 | nproc 4
