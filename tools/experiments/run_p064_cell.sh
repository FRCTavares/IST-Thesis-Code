#!/usr/bin/env bash
# Run one operator-controlled Issue #64 runtime cell.
set +u
THESIS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$THESIS_ROOT" || exit 1
export THESIS_ROOT
export GIT_PAGER=cat PAGER=cat GH_PAGER=cat
export COLCON_LOG_PATH="$THESIS_ROOT/ros2_ws/log/colcon"
export HAILORT_LOGGER_PATH="$THESIS_ROOT/ros2_ws/log/hailort"
source /opt/ros/jazzy/setup.bash || exit 1
source "$THESIS_ROOT/ros2_ws/install/setup.bash" || exit 1
python3 "$THESIS_ROOT/tools/experiments/run_p064_cell.py" "$@"
