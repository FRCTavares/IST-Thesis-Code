# Live-system validation evidence

Last reviewed: 2026-09-09

## Purpose

Reviewed live, ground, and host evidence for specific runtime and integration
contracts. These results validate engineering boundaries of the onboard system;
they do not replace the final held-out selected-person evaluation.

## Contents

| Path | Role |
| --- | --- |
| `p051_unattended_host_recovery_validation.md` | Raspberry Pi unattended-host recovery validation. |
| `p052_target_authority_ground_evidence.md` | Ground validation of the controller-facing target-authority graph. |
| `p053_coordinate_image_time_person_evidence.md` | Physical-person coordinate and image-time consistency evidence. |
| `p054_raw_image_transport_cost.md` | Onboard cost of raw-image DDS publication. |
| `p054_raw_image_transport_cost_evidence/` | Promoted measurements and checksums backing the Issue #54 summary. |

## Rules

- Treat each document according to its stated implementation, model, and commit provenance.
- Historical detector or schema identities remain unchanged when they describe the measured run.
- Live-system validation is evidence for a specific contract, not general held-out tracking performance.
