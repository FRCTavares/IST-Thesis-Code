# Retained research source handoff

Last reviewed: 2026-10-05

Thesis author: Francisco Tavares.

These archives supplement the earlier 116-file provenance catalogue. They
contain the complete tracked source, documentation and tracked evidence at the
retained research revisions, with the campaign-verified modified files overlaid.
All files are individually hashed in each archive's `DELIVERY_SNAPSHOT.json`.
Original bytes/notices are retained; these are immutable historical sources,
not maintained headered delivery code or newly promoted configurations.

| Archive | Retained source | Configuration |
| --- | --- | --- |
| `retained_tim_mars_source.tar.gz` | `0757e74e9ee6f0b3b2e689cfb8558633557cd79d` | Frozen TIM-MARS/evaluator source. |
| `retained_tim_mars_g_source.tar.gz` | `6c0172d867994340d5eddc974dab7aa2b802b07f` plus verified campaign overlays | Frozen guarded implementation and campaign executors. |

Both include the canonical YOLOv8s HEF and MARS TensorFlow model. The guarded
snapshot also includes the exact MARS ONNX encoder at `models/reid/mars.onnx`
and retained overrides at `delivery/retained_tim_overrides.json`. These are
copies of verified existing models, not new encoders or configurations.
Unreferenced catalogue-only detector binaries are omitted from these portable
snapshots; the maintained checkout retains them and their inventory.

## Prepare a historical execution directory

Extract each archive into a separate directory, preserve its original files,
install ROS 2 Jazzy and its declared package dependencies, and build its own
workspace. Use the Python and model/configuration hashes recorded in
`docs/archive/delivery_sources_20261004/campaign_FREEZE.json` and the associated
run manifests. The recorded package versions identify the retained environment;
they are not a newly solved installation lock.

These are source snapshots, not virtual-machine images or Git repositories.
Historical helpers that recover older files with `git show` additionally need
the original Git history. Use a separate checkout of the retained revision and
apply only manifest-verified modified-file overlays. The unchanged frozen
gates must pass before an evidence replay. Do not substitute the current main
checkout or refresh historical hashes because delivery comments differ.

The original manifest uses Pi paths for cache/model/checkouts. Verify and map
those external paths explicitly in a reproduction workspace; do not edit or
reinterpret the retained evidence manifest. Dataset images, source bags,
CVAT annotations, detector caches and the independently owned browser UI are
not distributed inside these source archives. Use the associated run manifests
and data-retention inventory to obtain those inputs. This audit does not claim
that a fresh host can reproduce the campaign without them.

TIM-MARS-G remains replay evidence; TIM-MARS was the configuration flown.
No experiment, new data, tuning, model conversion or flight was performed to
prepare these packages.
