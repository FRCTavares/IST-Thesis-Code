#!/usr/bin/env bash
set -eo pipefail

source /opt/ros/jazzy/setup.bash

set -u
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"

ros2 launch mavros apm.launch \
  fcu_url:=udp://:14550@ \
  tgt_system:=9 \
  tgt_component:=1
