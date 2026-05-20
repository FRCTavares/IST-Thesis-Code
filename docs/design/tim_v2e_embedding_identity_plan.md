# TIM-V2E: Event-Triggered Lightweight Identity Embedding

## Goal

Reduce wrong selected-target persistence during hard re-entry and crossing cases without turning TIM into a generic MOT/ReID tracker.

## Core idea

TIM-V2K handles LOST/UNCERTAIN rank-aware reacquisition. TIM-V2E adds a lightweight identity descriptor used only when geometry is ambiguous or when re-entry is being considered.

## Non-goals

- No full DeepSORT-style always-on ReID.
- No global MOT identity optimisation.
- No live default behaviour changes.
- No claims from regenerated tracker IDs unless annotations match that exact eval bag.

## Descriptor

Initial offline descriptor:
- 64x128 RGB person crop
- 10% horizontal padding, 5% vertical padding
- upper/lower body split
- 16D descriptor baseline from HSV plus simple gradient statistics

Learned descriptor target:
- 8D or 16D L2-normalised embedding
- tiny depthwise CNN
- CPU first on Raspberry Pi 5
- Hailo only if CPU cost is unacceptable

## TIM use policy

Use embedding only when:
- TIM state is UNCERTAIN, LOST, or REACQUIRED, or
- top two geometric candidates are within the ambiguity margin, or
- LOCKED candidate has a strong appearance contradiction.

Update embedding memory only when:
- state is LOCKED,
- association is unambiguous,
- bbox is large enough,
- descriptor is valid.

Never update embedding memory during UNCERTAIN, LOST, or ambiguous REACQUIRED.

## Evaluation

Compare:
1. raw tracker-ID target
2. TIM-V1 HSV
3. TIM-V2K
4. TIM-V2K + descriptor
5. TIM-V2K + learned 16D embedding

Primary metric:
- wrong valid target duration

Secondary metrics:
- correct valid duration
- lost visible duration
- time to reacquire
- embedding trigger rate
- embedding latency p50/p95/p99

Success criterion:
- reduce wrong target duration without collapsing correct target time.
