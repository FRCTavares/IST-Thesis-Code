# tools/issues

Last reviewed: 2026-09-27

## Issue-scoped tooling

This directory contains tooling whose purpose belongs to one specific thesis
issue rather than to the reusable analysis, experiment, live, flight, bag,
camera, host, or library surfaces.

Rules:

- Keep generic/reused helpers outside this directory.
- Do not move files whose literal historical path is part of a frozen evidence
  or prospective-evaluation contract merely for cosmetic consistency.
- Each issue directory documents whether it is active or retained historical
  reproduction tooling.
- Tests remain under `tools/tests/` so the normal regression suite discovers
  them without special configuration.
