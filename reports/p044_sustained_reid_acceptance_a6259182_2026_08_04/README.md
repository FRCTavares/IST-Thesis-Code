# P044 Sustained Observational ReID Acceptance

## Execution

- Execution commit: `a6259182d344bba8b2e32176a1e6a802e11ef682`
- Source run: `p044_sustained_reid_a6259182_2026_08_04_hard_reentry_sustained_acceptance_30m_r1`
- Requested duration: 1800.0 s
- Observed event duration: 1796.576 s
- Input: accepted hard-reentry replay through the experiment-only timestamp-refresh relay
- CPU appearance model: MARS-small128, authoritative
- Hailo appearance model: RepVGG 512D, observational only
- Explicit request policy: `ambiguity_guarded`
- Request interval: 250 ms
- TIM result deadline: 500 ms

## Accepted result

The bounded 30-minute execution completed through the external wall-clock watchdog. The sustained-operation analyser reported no violations.

- Requests: 5088
- Successful backend results: 4962 (97.524%)
- Accepted TIM observations: 4953 (97.347%)
- Expired requests: 135 (2.653%)
- Backend failures: 0
- Maximum concurrent Hailo calls: 1
- Final executor queue: 0
- Final TIM in-flight requests: 0
- Maximum temperature: 60.4 degC
- Mean temperature: 57.591 degC
- Nonzero throttle samples: 0
- Minimum available memory: 5957.0 MiB
- Image relay accounting: 9172/9172
- Track relay accounting: 25041/25041
- Source rewinds handled: 26 image and 26 track rewinds
- Runtime error-pattern matches: 0

Early, middle, and late windows remained within the predefined detector, ReID, CPU, RSS, temperature, throttle, and memory gates.

## Claim boundary

This evidence accepts bounded sustained operation only for the tested hard-reentry replay and experiment configuration.

It does not establish authoritative RepVGG target-decision safety, ranking integration, memory integration, cross-sequence generality, DDS packet-loss tolerance, live-flight endurance, or the final resource characterisation owned by Issue #32.

CPU MARS remained authoritative. RepVGG remained observational. Production nodes and canonical YAML were not changed.

## Evidence scope

This directory contains compact summaries, provenance, the acceptance review, and hashes. Raw JSONL streams, the MCAP evidence bag, and runtime logs remain ignored and local at the paths recorded in `acceptance_review.json`.
