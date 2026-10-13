# Thesis-Code delivery audit — 5 October 2026

## Verdict

The source, packaging and software checks pass on revision `00c120e9` with
preserved uncommitted delivery changes. This is not a clean-host installation,
physical flight acceptance or closure of Code #50/#32. All prior author changes,
historical evidence, retained configurations and negative findings are preserved.

## Verified

| Check | Result |
| --- | --- |
| Maintained source purpose/Francisco Tavares headers | 389 files; zero omissions |
| Python syntax | 325 files compile |
| Tooling tests | 1,330 pass; two external-bag integration checks skipped |
| ROS tests | 531 bringup + 13 tracker tests pass |
| ROS build | All three packages build in isolated directories |
| Live software/model availability | Pass, including nine installed ROS entrypoints |
| Retained research snapshots | 2,929 individual source/model files hash-verified |
| Model, promoted report and result provenance | Before-audit hashes retained |
| Source deletion review | No maintained source without code/docs/test/provenance references |

ROS tests used the isolated build and a separate local DDS domain. No aircraft,
camera stack, experiment, tuning or dataset was started. The two skipped tests
need source bags deliberately kept outside Git; they are not marked passed.

## Gaps corrected

- Clean installation omitted TensorFlow for MARS and NumPy/SciPy/OpenCV tracker
  requirements. ROS manifests and setup instructions now declare the required
  libraries and distinguish live, field, offline and campaign prerequisites.
- A reusable environment checker verifies imports, installed ROS executables,
  required commands and retained model hashes without starting nodes/hardware.
- The earlier 116-file provenance archive was insufficient as an execution
  source. Separate complete pinned TIM-MARS/TIM-MARS-G source snapshots now
  include canonical models and campaign-verified modified-file overlays.
- Historical byte-exact gates remain strict. Positive regression fixtures use
  verified historical bytes; the headered delivery cannot pass as its predecessor.
  Frozen manifests and historical evidence identities were not refreshed.
- Current runtime configuration metadata now describes its actual headered file;
  parsed parameters and all historical evidence-version entries are unchanged.
- Stale TODO wording and YAML-text assumptions were corrected. Synthetic tiny-bag
  decompression tests isolate their disk-space fixture; the production 25 GiB
  reserve and insufficient-space rejection test remain intact.
- Finder metadata was preserved outside the checkout; the layout test ignores
  this automatically regenerated macOS file.

## Organisation and deletion review

Maintained tools remain in their functional/issue directories; literal paths
used by frozen authorities stay in place. Every maintained source has a code,
documentation, test or provenance reference. No additional source deletion is
supported by this audit. Deprecated experiments preserved as historical source
are explicitly separated from the current live stack.

Catalogue-only detector models still occupy roughly 330 MB. Their inventory
records incomplete provenance, and the external dashboard advertises available
models. They are omitted from the portable retained snapshots, but are not
silently deleted from the main checkout. The only removed local clutter is a
preserved Finder metadata file and the audit's disposable Pi workspace.

## External requirements and unresolved items

Source bags/videos, annotations and caches remain external and must match the
selected run manifest. ROS 2 Jazzy, compatible Hailo drivers/runtime, camera,
MAVROS/geoid data, field networking and the external UI must be installed where
applicable. Historical Git-based helpers also need the retained Git history;
source archives are not Git repositories or virtual-machine images.

The Pi software imports/models pass, but `pip check` reports two existing
consistency warnings: OpenCV 4.12.0.88 declares NumPy >=2 while the retained
environment has NumPy 1.26.4; installed PyNaCl also lacks cffi. The frozen Pi
environment was not upgraded. Use a separate resolved environment for a fresh
installation and verify it before operation; observed package versions are not
a validated clean-install lock.

Code #50 still needs its native Pixhawk log attribution verdict. Code #32 still
needs sustained-runtime acceptance or an explicit missing-evidence conclusion.
The author must review the package before delivery. No commit, push, deployment
or physical acceptance claim was made.

## Repository records

`docs/delivery_audit_20261005.json` stores counts and boundaries.
`docs/source_header_audit_20261005.json` stores current source hashes.
`docs/archive/delivery_audit_20261005/` contains the test/build/environment logs.
`docs/archive/delivery_sources_20261005/` contains the complete retained sources.
`tools/setup/README.md` defines installation profiles and external prerequisites.
