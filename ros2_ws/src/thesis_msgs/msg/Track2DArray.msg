# Thesis-Code
# Purpose: Define the frame-stamped collection of tracked detections published
# by the tracker.
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
int64 t_track_cb_start_ns
int64 t_track_cb_end_ns
thesis_msgs/Track2D[] tracks