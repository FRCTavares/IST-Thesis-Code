#!/usr/bin/env bash
# Thesis-Code
# Purpose: Choose and validate one run identifier shared by live logs and
# recording directories.
# Author: Francisco Tavares
# Copyright (c) 2026 Francisco Carreira Tavares
# SPDX-License-Identifier: MIT
#
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.


# Choose once, before creating any run or capture directory. An explicitly
# empty value is invalid; an unset value retains the normal timestamp default.
initialize_live_run_id() {
    if [[ ! ${RUN_ID+x} ]]; then
        RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)" || return
    fi
    if [[ ! "$RUN_ID" =~ ^[A-Za-z0-9_.-]+$ || "$RUN_ID" == *..* || "$RUN_ID" == "." ]]; then
        echo "[error] RUN_ID must be a non-empty identifier using letters, digits, '_', '-', or '.', without '..'" >&2
        return 2
    fi
    export RUN_ID
}
