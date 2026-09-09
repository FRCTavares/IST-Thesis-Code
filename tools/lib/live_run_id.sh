#!/usr/bin/env bash

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
