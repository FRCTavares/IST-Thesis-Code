#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1

export GIT_PAGER=cat
export PAGER=cat
set +u
source /opt/ros/jazzy/setup.bash
if [ -f ros2_ws/install/setup.bash ]; then
  source ros2_ws/install/setup.bash
fi

export THESIS_ROOT="$PWD"
export COLCON_LOG_PATH="$THESIS_ROOT/ros2_ws/log/colcon"
mkdir -p "$COLCON_LOG_PATH"

cd ros2_ws || exit 1
colcon build --symlink-install "$@"
