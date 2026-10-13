# Thesis-Code delivery readiness audit

Review date: 4 October 2026.

Superseded by [the complete 5 October audit](DELIVERY_READINESS_20261005.md).
The later audit fixes dependency and frozen-contract gaps missed by this
initial focused verification.

## Current verdict

The maintained-source documentation and packaging checks are complete on the
Pi main revision selected by the author. Research acceptance remains pending
Code #50 and #32. This audit does not establish new runtime or flight evidence.

## Source documentation

**387 maintained files** have file-specific purpose and attribution headers:
Python tools and ROS nodes, launch/build files, tests, messages, runtime
configuration, shell utilities and host-service assets. Project source credits
Francisco Tavares and retains the MIT licence. Six upstream ament templates
retain their original Open Source Robotics Foundation Apache-2.0 notices and
credit thesis integration.

[Source header standard](design/SOURCE_HEADERS.md) defines placement, attribution
and exclusions. Historical source/evidence copies, binary models, fixture data,
machine-readable templates and empty ament markers retain their original bytes.

## Verification

- Header audit: **387 files, zero failures**.
- **324 Python files compile** and **34 shell sources pass syntax checks**.
- Of 386 header insertions, 377 are exactly reversible comment additions.
  Nine files also have documented metadata, test or import-order corrections.
  Both import reorderings retain the same imported symbols and executable
  statements; no runtime algorithm or controller policy was changed by this pass.
- **34 existing packaging/documentation tests pass** on the Mac.
- **Six existing ROS copyright/style/docstring gates pass** on isolated Pi
  copies, three per Python package. Unrelated ROS launch-test plugin discovery
  is disabled for these lint checks; these are not full ROS runtime tests.
- The installed ROS copyright checker accepts **322 supported source files**.
- **454 protected evidence/model/data files** retain the Pi-main baseline hashes.
  Header insertion preserves file modes, shebangs and existing licence notices.
- `git diff --check` reports no whitespace errors.

The packaging corrections remove a preserved Finder metadata file from the
maintained tools surface, accept generated colcon-directory references, align
the TODO contract test with the author queue and date the flight README. ROS
maintainer names are consistent, both existing copyright gates are enabled and
two pre-existing import-order lint failures are corrected.

Records: [header inventory](source_header_audit_20261004.json),
[change/preservation verification](source_delivery_verification_20261004.json)
and [delivery source manifest](delivery_source_manifest_20261004.json).

## Revision and preserved work

The Mac was fast-forwarded from `143cfc0` to
`00c120e9054b37658ebf91effd5890bde1786428`, adopting 13 existing Pi-main commits.
All prior changed files were copied into a SHA-256 inventoried backup first.
The author closeout TODO remains active. The exact author-edited six-flight
operator sheet is [archived](archive/field_day_runbook_author_before_sync_20261004.md);
the active runbook retains the newer B-C-B procedure and native-log safeguards.
The superseded upstream queue is also archived. The original Pi flight checkout
and installed stack were not modified. No new commit or push was made.

## Retained research implementations

[Source provenance snapshot](archive/delivery_sources_20261004/README.md)
contains 116 original source/configuration files independently matched to the
Report campaign manifest, covering the retained TIM-MARS and TIM-MARS-G paths.
The manifest records exact source revisions, model hashes, configuration hashes
and encoder/bridge settings. This is a provenance snapshot, not a standalone
ROS install or a distribution of videos/datasets/all dependencies. Historical
replay requires the complete pinned checkouts and associated run manifests.

Header comments change SHA-256 values. Historical manifests remain unchanged;
do not replace their hashes with delivery-source hashes. TIM-MARS and TIM-MARS-G
remain two configurations of one architecture. No trial configuration was
promoted, and no new experiment, tuning, dataset or flight was performed.

## Remaining delivery decisions

- Code #50: native Pixhawk log attribution verdict.
- Code #32: sustained-runtime acceptance verdict or explicit missing-evidence
  conclusion.
- Author review of the delivery checkout and documentation before submission.

These evidence dependencies remain open. Source-documentation readiness does
not close scientific acceptance or author approval.
