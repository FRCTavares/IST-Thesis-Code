# Tools Directory

This directory contains thesis support tools used for replay, evaluation, visualization, live operation, and setup.

## Main entrypoints

- `tools/thesis_eval.sh` — main thesis evaluation wrapper.
- `tools/thesis_live.sh` — live stack helper.
- `tools/start_live_stack.sh` — convenience live startup script.
- `tools/start_ui_stack.sh` — convenience UI startup script.

## Subdirectories

- `analysis/` — offline bag analysis, target correctness evaluation, bbox correctness evaluation, timing checks, and TIM score extraction.
- `experiments/` — reproducible replay runners for clean TIM replay and detector-from-image replay.
- `visualization/` — TIM audit UI, clean UI, and video rendering tools.
- `bag/` — bag-specific overlay/video utilities.
- `live/` — small live inspection helpers.
- `camera/` — camera probing scripts.
- `setup/` — host/runtime setup scripts.
- `lib/` — shared shell helper functions used by live scripts.

## Current policy

Do not move or rename scripts casually. Many reports, commands, and runbooks refer to these paths directly.
Prefer adding documentation first, then migrate scripts only when all references can be updated and tested.
