#!/usr/bin/env bash

# Issue #50/#74 field hardening: deliberate shutdown ordering for retained
# recordings. Scientific recorders must never be killed before the publishers
# whose final state they are supposed to capture, and MCAP finalization must
# get a real grace window -- not ~1s and not an accidental side effect of
# reversing a generic PID array.
#
# Sourced by tools/start_live_stack.sh. Uses: PID_FILE, RUN_DIR,
# RECORDER_FINALIZE_GRACE_S, STOP_APP_GRACE_S, STOP_APP_SETTLE_S.

# Recorder process names started via start_ros_bg. Everything else is an
# "application" node (camera, perception, tracker, TIM-MARS, dashboard,
# control, MAVROS, web video).
_live_is_recorder_name() {
    case "$1" in
        rosbag|dataset_rosbag|raw_image_bag|source_raw_image_bag|source_mavros_bag)
            return 0
            ;;
    esac
    return 1
}

# Signal a process and all of its descendants.
kill_tree() {
    local pid="$1"
    local sig="${2:-TERM}"

    if [[ -z "${pid:-}" ]]; then
        return
    fi
    if ! kill -0 "$pid" >/dev/null 2>&1; then
        return
    fi

    local child
    for child in $(pgrep -P "$pid" 2>/dev/null || true); do
        kill_tree "$child" "$sig"
    done

    kill -s "$sig" "$pid" >/dev/null 2>&1 || true
}

_live_pid_alive() {
    kill -0 "$1" >/dev/null 2>&1
}

_live_pid_starttime() {
    local pid="$1"
    local stat rest
    local -a fields=()

    [[ -r "/proc/$pid/stat" ]] || return 1
    stat="$(cat "/proc/$pid/stat" 2>/dev/null)" || return 1
    rest="${stat##*) }"
    read -r -a fields <<< "$rest"
    [[ ${#fields[@]} -ge 20 ]] || return 1
    printf "%s\n" "${fields[19]}"
}

_live_collect_tree_identities() {
    local pid="$1"
    _live_pid_alive "$pid" || return 0

    local start child
    start="$(_live_pid_starttime "$pid")"
    if [[ -n "${start:-}" ]]; then
        _LIVE_TREE_IDENTITIES+=("${pid}:${start}")
    fi

    for child in $(pgrep -P "$pid" 2>/dev/null || true); do
        _live_collect_tree_identities "$child"
    done
}

_live_identity_alive() {
    local identity="$1"
    local pid="${identity%%:*}"
    local expected_start="${identity#*:}"
    local actual_start

    _live_pid_alive "$pid" || return 1
    actual_start="$(_live_pid_starttime "$pid")"
    [[ -n "${actual_start:-}" && "$actual_start" == "$expected_start" ]]
}

# Read PID_FILE into parallel arrays (start order preserved).
_live_load_pids() {
    _LIVE_PIDS=()
    _LIVE_NAMES=()
    [[ -f "${PID_FILE:-}" ]] || return 0
    local pid name
    while read -r pid name; do
        [[ -n "${pid:-}" ]] || continue
        _LIVE_PIDS+=("$pid")
        _LIVE_NAMES+=("$name")
    done < "$PID_FILE"
}

# Stop the application nodes (everything that is not a recorder), newest-first,
# so their final safe-zero / shutdown state is emitted while the recorders are
# still running. SIGINT, a bounded settle, then SIGTERM for stragglers.
stop_app_nodes() {
    local grace="${STOP_APP_GRACE_S:-3}"
    _live_load_pids
    local i pid name
    for (( i=${#_LIVE_PIDS[@]}-1; i>=0; i-- )); do
        pid="${_LIVE_PIDS[i]}"
        name="${_LIVE_NAMES[i]}"
        _live_is_recorder_name "$name" && continue
        if _live_pid_alive "$pid"; then
            kill_tree "$pid" INT
        fi
    done

    local waited=0
    while (( waited < grace )); do
        local any=0
        for (( i=${#_LIVE_PIDS[@]}-1; i>=0; i-- )); do
            name="${_LIVE_NAMES[i]}"
            _live_is_recorder_name "$name" && continue
            _live_pid_alive "${_LIVE_PIDS[i]}" && any=1
        done
        [[ "$any" -eq 0 ]] && break
        sleep 1
        waited=$((waited + 1))
    done

    for (( i=${#_LIVE_PIDS[@]}-1; i>=0; i-- )); do
        pid="${_LIVE_PIDS[i]}"
        name="${_LIVE_NAMES[i]}"
        _live_is_recorder_name "$name" && continue
        if _live_pid_alive "$pid"; then
            kill_tree "$pid" TERM
        fi
    done
}

# Deliberately finalize the recorder(s): SIGINT, allow up to
# RECORDER_FINALIZE_GRACE_S for process exit after flushing/finalizing,
# escalate to SIGTERM then SIGKILL only if still alive, and clean only
# recorder processes/descendants tracked for this run. Finalized bag
# integrity is checked afterward by verify_retained_bag.py.
# Sets RECORDER_FINALIZE_OUTCOME to graceful|escalated|none.
finalize_recorders() {
    local grace="${RECORDER_FINALIZE_GRACE_S:-10}"
    _live_load_pids

    local -a rpids=() rnames=()
    local i
    for (( i=0; i<${#_LIVE_PIDS[@]}; i++ )); do
        if _live_is_recorder_name "${_LIVE_NAMES[i]}"; then
            rpids+=("${_LIVE_PIDS[i]}")
            rnames+=("${_LIVE_NAMES[i]}")
        fi
    done

    if [[ ${#rpids[@]} -eq 0 ]]; then
        RECORDER_FINALIZE_OUTCOME="none"
        _live_write_recorder_outcome
        return 0
    fi

    local -a recorder_tree_identities=()
    for (( i=0; i<${#rpids[@]}; i++ )); do
        if _live_pid_alive "${rpids[i]}"; then
            _LIVE_TREE_IDENTITIES=()
            _live_collect_tree_identities "${rpids[i]}"
            recorder_tree_identities+=("${_LIVE_TREE_IDENTITIES[@]}")
        fi
    done

    for (( i=0; i<${#rpids[@]}; i++ )); do
        if _live_pid_alive "${rpids[i]}"; then
            kill_tree "${rpids[i]}" INT
        fi
    done

    local waited=0
    while (( waited < grace )); do
        local any=0
        for (( i=0; i<${#rpids[@]}; i++ )); do
            _live_pid_alive "${rpids[i]}" && any=1
        done
        [[ "$any" -eq 0 ]] && break
        sleep 1
        waited=$((waited + 1))
    done

    local escalated=0
    for (( i=0; i<${#rpids[@]}; i++ )); do
        if _live_pid_alive "${rpids[i]}"; then
            escalated=1
            echo "[warn] recorder '${rnames[i]}' (pid ${rpids[i]}) did not finalize within ${grace}s; escalating to SIGTERM"
            kill_tree "${rpids[i]}" TERM
        fi
    done

    if [[ "$escalated" -eq 1 ]]; then
        local esc_waited=0
        while (( esc_waited < 5 )); do
            local any=0
            for (( i=0; i<${#rpids[@]}; i++ )); do
                _live_pid_alive "${rpids[i]}" && any=1
            done
            [[ "$any" -eq 0 ]] && break
            sleep 1
            esc_waited=$((esc_waited + 1))
        done
        for (( i=0; i<${#rpids[@]}; i++ )); do
            if _live_pid_alive "${rpids[i]}"; then
                echo "[error] recorder '${rnames[i]}' still alive after SIGTERM; sending SIGKILL"
                kill_tree "${rpids[i]}" KILL
            fi
        done
    fi

    # Final safety net: signal only processes snapshotted from recorder
    # trees owned by this run. Never kill unrelated rosbag processes.
    local identity pid
    local tracked_orphan=0

    for identity in "${recorder_tree_identities[@]}"; do
        if _live_identity_alive "$identity"; then
            tracked_orphan=1
            escalated=1
            pid="${identity%%:*}"
            echo "[warn] tracked recorder process survived finalization (pid $pid); sending SIGINT"
            kill -s INT "$pid" >/dev/null 2>&1 || true
        fi
    done

    if [[ "$tracked_orphan" -eq 1 ]]; then
        sleep 2
        for identity in "${recorder_tree_identities[@]}"; do
            if _live_identity_alive "$identity"; then
                pid="${identity%%:*}"
                echo "[warn] tracked recorder process still alive (pid $pid); sending SIGTERM"
                kill -s TERM "$pid" >/dev/null 2>&1 || true
            fi
        done

        sleep 1
        for identity in "${recorder_tree_identities[@]}"; do
            if _live_identity_alive "$identity"; then
                pid="${identity%%:*}"
                echo "[error] tracked recorder process still alive (pid $pid); sending SIGKILL"
                kill -s KILL "$pid" >/dev/null 2>&1 || true
            fi
        done
    fi

    if [[ "$escalated" -eq 1 ]]; then
        RECORDER_FINALIZE_OUTCOME="escalated"
        echo "[recorder] finalization ESCALATED (grace ${grace}s exceeded) -- evidence may be truncated"
    else
        RECORDER_FINALIZE_OUTCOME="graceful"
        echo "[recorder] finalization graceful within ${grace}s"
    fi
    _live_write_recorder_outcome
    return 0
}

_live_write_recorder_outcome() {
    if [[ -n "${RUN_DIR:-}" && -d "${RUN_DIR:-}" ]]; then
        printf '%s\n' "${RECORDER_FINALIZE_OUTCOME:-unknown}" \
            > "$RUN_DIR/recorder_finalize_outcome.txt" 2>/dev/null || true
    fi
}
