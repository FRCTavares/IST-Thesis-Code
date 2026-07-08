#!/usr/bin/env bash
set -eo pipefail

source /opt/ros/jazzy/setup.bash

set -u
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"

ros2 service call /mavros/set_stream_rate mavros_msgs/srv/StreamRate \
"{stream_id: 0, message_rate: 50, on_off: true}"
