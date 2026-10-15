# Documentation

Last reviewed: 2026-10-13

This directory holds the operating documentation for the TIM-MARS system on the
Raspberry Pi 5 + Hailo-8: setup, daily operation, architecture, algorithm and
interface contracts, field procedures and recovery runbooks.

## Start here

1. [Handover](HANDOVER.md) - reaching the Pi, Tailscale, SSH keys, Wi-Fi profiles, first-day checklist.
2. [Getting started](GETTING_STARTED.md) - install, build, environment checks.
3. [Operations](OPERATIONS.md) - run, select a target, record, verify, troubleshoot.
4. [Architecture](ARCHITECTURE.md) - nodes, topics, the control-authority rule.
5. [Field day runbook](flight/field_day_runbook.md) - before anything leaves the ground.

## Folder map

- `algorithm/` - TIM-MARS definition, coordinate/image-time and output-freshness contracts.
- `control/` - controller, Pixhawk and MAVROS integration contracts.
- `debug/` - Hailo, camera and unattended-host recovery procedures.
- `design/` - source-header and README conventions, and the maintained tooling index.
- `flight/` - field-day procedure, retained evidence package, post-flight checks.
- `live/` - dashboard network exposure and access-control contract.
- `RUNTIME_METRICS.md` - timing schema v4 and resource-sampling vocabulary.

## Authority order

When documents disagree, trust in this order:

1. the current implementation and `tim_mars_canonical.yaml`;
2. the coordinate, freshness and control contracts under `algorithm/` and `control/`;
3. the operating runbooks in this directory;
4. anything else.

## Research archive

The thesis analysis, evaluation splits, annotation workflows, experiment
reports and delivery audits are no longer in the working tree. They are kept in
Git history at tag `archive/thesis-final-20261013`.
