# Thesis-Code
# Purpose: Define the selected-person identity and image-space state passed
# between ROS 2 nodes.
# Author: Francisco Tavares
# Copyright (c) 2026 Francisco Carreira Tavares
# SPDX-License-Identifier: MIT
#
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.

std_msgs/Header header
uint32 frame_id
int64 src_stamp_ns
int64 t_cam_msg_seen_ns
int64 t_target_cb_start_ns
int64 t_target_cb_end_ns
uint32 id
float32 cx
float32 cy
float32 w
float32 h
float32 score
float32 quality