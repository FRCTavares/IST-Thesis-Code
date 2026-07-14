
## Session validation — 14 July 2026 (post-revert safe-baseline confirmation)

Confirmed on `main` (post-revert, diagnostic bypass preserved only at
`diagnostic/trusted-same-id-bypass-2026-07-14`):

- Seq01 (RAW_TARGET_MODE=source): raw 0.587/0.000/0.413,
  TIM-MARS 1.000/0.000/0.000. Matches prior independent measurement.
- May (RAW_TARGET_MODE=selected_id): raw 0.723/0.100/0.178,
  TIM-MARS 0.944/0.015/0.041. Matches NOVELTY.md canonical figure and
  prior independent measurement.

Separately discovered: `tools/experiments/run_one_memory_tim_replay.sh`
silently accepts an inherited/exported `RAW_TARGET_MODE` shell variable
with no warning that it differs from the script's own default, which
produced one degenerate raw==TIM-MARS comparison in this session before
being caught. Add to P0.13/evaluator-tests scope: log override-vs-default
source explicitly, and capture full resolved override environment in
run_metadata.json, not just the threaded-through fields.
