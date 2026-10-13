# Frozen thesis source provenance

Last reviewed: 2026-10-04

Thesis author: Francisco Tavares.

`frozen_tim_sources.tar.gz` preserves 116 source/configuration files verified
against `campaign_FREEZE.json` from Thesis-Report. `source_catalogue.json`
explains their roles and identifies the exact recovery source of each file.
Original source notices and bytes are preserved. The snapshot includes both
retained target-memory configurations and their tracker/evaluation authorities.

These files document the historical implementations; the archive is not a
standalone ROS installation or a dataset distribution. Reproduction still
requires the pinned complete source checkouts, model dependencies and associated
run manifests. The development revision alone is insufficient: the campaign
manifest records a modified freeze helper, and the archive retains its verified
bytes. No trial variant was promoted into the delivery main branch.

The live-flight checkout, frozen public evaluator and guarded development
implementation have separate source revisions. Do not relabel replay as flight
execution, replace frozen hashes with current delivery hashes, or treat source
packaging as acceptance of Code #50 or #32.
