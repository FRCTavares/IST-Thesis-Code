# Algorithm contracts

Last reviewed: 2026-10-13

## Purpose

Maintained algorithm-level contracts for TIM-MARS and the live selected-target
pipeline. These documents define current semantics; experiment evidence is in
the research archive (tag `archive/thesis-final-20261013`).

## Contents

| Path | Role |
| --- | --- |
| `tim_mars_versions.md` | TIM-MARS scope, safety objective and the components of the final method. |
| `tim_mars_final_method_authority.md` | Implementation-backed method, parameters and the behaviour-to-test map. |
| `coordinate_image_time_contract.md` | Live coordinate, resize and image-time contract. |
| `output_freshness_contract.md` | Controller-facing output freshness semantics. |

## Rules

- Current runtime behaviour must agree with the implementation and
  `ros2_ws/src/thesis_bringup/config/tim_mars_canonical.yaml`.
- Changing a TIM-MARS parameter means editing the canonical YAML; the launcher
  never duplicates thresholds on the command line.
- Do not reinterpret recorded bags under a newer contract.
