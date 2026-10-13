# tools/tests

Last reviewed: 2026-10-13

These tests protect the repository's non-ROS tooling contracts: the live-stack
launcher and its recording/shutdown behaviour, flight preflight and evidence
verification, host recovery, documentation links, and the tools/repository
layout.

Run the complete suite from the repository root after building:

```bash
./tools/thesis_build.sh
source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash
python3 -m pytest -q -p no:cacheprovider tools/tests
```

Use `-p no:cacheprovider` so validation does not leave a root-level
`.pytest_cache`. Focused tests may be run by passing one test file.

