#!/usr/bin/env bash
set -euo pipefail

PROFILE="${1:-px4}"

source /opt/ros/jazzy/setup.bash

PARAMS_FILE="$HOME/Desktop/Thesis-Code/ros2_ws/src/thesis_bringup/config/mavros_pixhawk.yaml"

if [[ "$PROFILE" == "px4" ]]; then
  sudo nmcli con up pixhawk-px4
  FCU_URL="udp://0.0.0.0:14550@10.41.10.2:14540"
elif [[ "$PROFILE" == "apm" ]]; then
  sudo nmcli con up pixhawk-apm
  FCU_URL="udp://0.0.0.0:14550@192.168.144.14:14550"
else
  echo "usage: $0 [px4|apm]"
  exit 1
fi

echo "[info] profile=$PROFILE"
echo "[info] fcu_url=$FCU_URL"
echo "[info] params=$PARAMS_FILE"

ros2 run mavros mavros_node --ros-args \
  --params-file "$PARAMS_FILE" \
  -p fcu_url:="$FCU_URL" \
  -p gcs_url:=""
