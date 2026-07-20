# P0.4 OC-SORT Sequence Regeneration Audit

- Repository commit: `1b7dc4002c19e5235703913826e174df1025f1d0`
- Repository state recorded by every replay: clean
- Replay metadata schema: `3`
- Resolved-runtime schema: `2`
- Semantic-digest migration: `tim_mars_replay_generated_fields_v1` to `tim_mars_replay_generated_fields_v2`
- Sequences audited: seq03 and seq04
- Repeats per sequence: two
- Evaluation and event-level metrics: identical to the prior evidence
- Repeatability: passed for semantic messages, topic counts, aggregate evaluation, event evaluation, and resolved runtime after output-path normalization
- Runtime and metadata SHA-256 fingerprints: verified

The stored v1 and v2 digest strings are intentionally different because their
schemas differ. Recomputing the old and clean-regenerated bags under v2 produced
identical aggregate digests and identical per-message records.
