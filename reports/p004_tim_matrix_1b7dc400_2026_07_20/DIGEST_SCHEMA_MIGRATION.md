# P0.4 Clean Regeneration Audit

- Repository commit: `1b7dc4002c19e5235703913826e174df1025f1d0`
- Repository state recorded by every replay: clean
- Replay metadata schema: `3`
- Resolved-runtime schema: `2`
- Semantic-digest migration: `tim_mars_replay_generated_fields_v1` to `tim_mars_replay_generated_fields_v2`
- Matrix cases audited: ByteTrack, SORT, OC-SORT, DeepSORT
- Evaluation metrics: identical to the prior promoted evidence
- Topic counts: identical to the prior promoted evidence
- Generated messages: identical when both old and new bags are evaluated under the current v2 semantic-digest contract
- Runtime and metadata SHA-256 fingerprints: verified

The stored v1 and v2 digest strings are intentionally different because their
schemas differ. They are not directly comparable. Recomputing both generations
under v2 produced identical aggregate digests and identical per-message
records, confirming that the clean regeneration did not change TIM outputs.
