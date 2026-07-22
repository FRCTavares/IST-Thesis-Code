# Tool Tests

These tests protect the repository's non-ROS tooling contracts: evaluators,
replay determinism and provenance, coordinate mapping, recording storage,
host recovery, the evidence catalogue, and the tools directory layout.

Run the complete suite from the repository root after building:

```bash
./tools/thesis_build.sh
source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash
python3 -m pytest -q -p no:cacheprovider tools/tests
```

Use `-p no:cacheprovider` so validation does not leave a root-level
`.pytest_cache`. Focused tests may be run by passing one test file.
