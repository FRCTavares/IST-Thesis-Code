# Algorithm contracts

Last reviewed: 2026-09-09

## Purpose

Maintained algorithm-level contracts for TIM-MARS and the live selected-target
pipeline. These documents define current semantics separately from historical
experiment evidence.

## Contents

| Path | Role |
| --- | --- |
| `tim_mars_versions.md` | Current TIM-MARS algorithm scope and version evolution. |
| `tim_mars_evidence_versions.md` | Boundary between current runtime identity and frozen evidence versions. |
| `coordinate_image_time_contract.md` | Live coordinate, resize, and image-time contract. |
| `output_freshness_contract.md` | Controller-facing output freshness semantics. |

## Rules

- Current runtime behavior must agree with implementation and canonical config.
- Frozen evidence fingerprints remain historical facts.
- Do not silently reinterpret historical bags under newer contracts.
