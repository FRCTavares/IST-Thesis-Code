#!/usr/bin/env bash
# Fail-closed, non-actuating field preflight for the retained flight workflow.
# The default path only observes host/repository state. The optional live gate
# runs the existing passive --field-record --no-control profile and stops it
# through the launcher's normal interactive stop command.

set +u
set -o pipefail

THESIS_ROOT="${FIELD_PREFLIGHT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
NETWORK_CONFIG="${THESIS_HOST_CONFIG_FILE:-/etc/default/thesis-host-health}"
EXPECTED_GCS_CIDR="${FIELD_PREFLIGHT_GCS_CIDR:-192.168.8.174/24}"
EXPECTED_PIXHAWK_PI_CIDR="${FIELD_PREFLIGHT_PIXHAWK_PI_CIDR:-192.168.144.183/24}"
PIXHAWK_ADDRESS="${FIELD_PREFLIGHT_PIXHAWK_ADDRESS:-192.168.144.14}"
WIFI_INTERFACE="wlan0"
ETHERNET_INTERFACE="eth0"
PASSIVE_GATE_SECONDS="${FIELD_PREFLIGHT_GATE_SECONDS:-40}"
PASSIVE_GATE_STARTUP_TIMEOUT_S="${FIELD_PREFLIGHT_STARTUP_TIMEOUT_S:-180}"
SUMMARY_TOOL="${FIELD_PREFLIGHT_SUMMARY_TOOL:-$THESIS_ROOT/tools/live/summarize_field_evidence.py}"
FAILURES=0
PASSIVE_REQUESTED=0
PASSIVE_LAUNCH_PID=""
PASSIVE_FIFO=""
PASSIVE_FIFO_FD_OPEN=0

pass() {
    printf 'PASS  %s\n' "$1"
}

fail() {
    FAILURES=$((FAILURES + 1))
    printf 'FAIL  %s\n' "$1"
    if [[ -n "${2:-}" ]]; then
        printf '      fix: %s\n' "$2"
    fi
}

note() {
    printf 'INFO  %s\n' "$1"
}

usage() {
    cat <<'EOF_USAGE'
Usage: tools/flight/field_preflight_check.sh [--passive-live-gate]

Default: fail-closed, read-only software/network/hardware checks.
--passive-live-gate: after those checks pass, run a bounded, non-held-out
                     --field-record --no-control ground recording gate.
EOF_USAGE
}

load_project_defaults() {
    if [[ -r "$THESIS_ROOT/tools/lib/live_defaults.sh" ]]; then
        # shellcheck disable=SC1091
        source "$THESIS_ROOT/tools/lib/live_defaults.sh"
    else
        fail "project recording defaults unavailable" \
            "restore tools/lib/live_defaults.sh from the current field revision"
    fi
}

check_repository() {
    local actual_root revision tracked_changes stage_output stage_rc
    actual_root="$(git -C "$THESIS_ROOT" rev-parse --show-toplevel 2>/dev/null || true)"
    if [[ "$actual_root" == "$THESIS_ROOT" && "$(pwd -P)" == "$THESIS_ROOT" ]]; then
        pass "repository root: $THESIS_ROOT"
    else
        fail "repository root (pwd=$(pwd -P), git=${actual_root:-missing})" \
            "cd ~/Desktop/Thesis-Code || exit 1"
    fi

    revision="$(git -C "$THESIS_ROOT" --no-pager log -1 --format='%H %s' 2>/dev/null || true)"
    if [[ -n "$revision" ]]; then
        pass "Git revision: $revision"
    else
        fail "Git revision unavailable" "git --no-pager log -1 --oneline"
    fi

    tracked_changes="$(git -C "$THESIS_ROOT" status --short --untracked-files=no 2>/dev/null || true)"
    if [[ -z "$tracked_changes" ]]; then
        pass "tracked worktree clean"
    else
        fail "unexpected tracked worktree changes" "git status --short"
        printf '%s\n' "$tracked_changes" | sed 's/^/      /'
    fi

    # H01/H02/H03 retain their historical prospective source freeze.
    # The #50 aircraft runtime includes documented post-heldout transport and
    # provenance follow-on commits, so this field gate checks completion of
    # the Stage-7 evidence contract without reapplying the historical runtime
    # byte-identity check to the current aircraft stack.
    stage_output="$(
        cd "$THESIS_ROOT" || exit 1
        python3 tools/analysis/validate_tim_evaluation_split.py \
            docs/data/splits/tim_mars_split_v4.json --require-final-ready 2>&1
    )"
    stage_rc=$?
    if [[ "$stage_rc" -eq 0 ]] && grep -Fq 'final_ready=3/3' <<< "$stage_output"; then
        pass "Stage-7 evidence contract: final_ready=3/3"
    else
        fail "Stage-7 evidence contract validation" \
            "python3 tools/analysis/validate_tim_evaluation_split.py docs/data/splits/tim_mars_split_v4.json --require-final-ready"
        printf '%s\n' "$stage_output" | sed 's/^/      /'
    fi
}

check_storage() {
    local probe available_kib required_kib available_gib
    if ! [[ "${RECORDING_MIN_FREE_GIB:-}" =~ ^[1-9][0-9]*$ ]]; then
        fail "recording free-space threshold unavailable" \
            "inspect RECORDING_MIN_FREE_GIB in tools/lib/live_defaults.sh"
        return
    fi

    # Use the same closest-existing-parent probe as the live launcher without
    # creating an output directory.
    # shellcheck disable=SC1091
    source "$THESIS_ROOT/tools/lib/live_storage.sh"
    probe="$(recording_storage_probe_path "${BAG_OUT_ROOT:-$THESIS_ROOT/bags/live_camera}")"
    available_kib="$(df -Pk -- "$probe" 2>/dev/null | awk 'NR == 2 {print $4}')"
    required_kib=$((RECORDING_MIN_FREE_GIB * 1024 * 1024))
    if [[ "$available_kib" =~ ^[0-9]+$ ]] && (( available_kib >= required_kib )); then
        available_gib="$(awk -v kib="$available_kib" 'BEGIN {printf "%.1f", kib/1048576}')"
        pass "storage: ${available_gib} GiB free (minimum ${RECORDING_MIN_FREE_GIB} GiB)"
    else
        fail "storage below ${RECORDING_MIN_FREE_GIB} GiB or unreadable" \
            "df -h \"$THESIS_ROOT\" \"$THESIS_ROOT/bags\""
    fi
}

load_network_contract() {
    if [[ ! -r "$NETWORK_CONFIG" ]]; then
        fail "field network configuration missing: $NETWORK_CONFIG" \
            "sudo tools/host/set_pi_network_mode.sh status"
        return 1
    fi
    set -a
    # This is the same installed configuration consumed by the project helper.
    # shellcheck disable=SC1090
    source "$NETWORK_CONFIG"
    local rc=$?
    set +a
    if [[ "$rc" -ne 0 ]]; then
        fail "field network configuration unreadable" \
            "sudo tools/host/set_pi_network_mode.sh status"
        return 1
    fi
    WIFI_INTERFACE="${THESIS_HOST_INTERFACE:-wlan0}"
    return 0
}

check_field_network() {
    local primary rescue fallback eth_profile configured active_wifi wifi_addresses
    local eth_active eth_addresses eth_profile_state default_routes eth_defaults tailscale_state carrier

    if ! load_network_contract; then
        return
    fi
    primary="${THESIS_HOST_PIXHAWK_WIFI_CONNECTION:-ISR Aero.Next GCS}"
    rescue="${THESIS_HOST_GCS_RESCUE_WIFI_CONNECTION:-ISR Aero.Next GCS Rescue}"
    fallback="${THESIS_HOST_PIXHAWK_WIFI_FALLBACK_CONNECTION:-}"
    eth_profile="${THESIS_HOST_PIXHAWK_ETHERNET_CONNECTION:-pixhawk-apm}"
    configured="${THESIS_HOST_MODE:-unattended}"

    if [[ "$configured" == "pixhawk" ]]; then
        pass "configured network mode: pixhawk"
    else
        fail "configured network mode: $configured" \
            "sudo tools/host/set_pi_network_mode.sh pixhawk"
    fi

    active_wifi="$(nmcli -g GENERAL.CONNECTION device show "$WIFI_INTERFACE" 2>/dev/null || true)"
    if [[ "$active_wifi" == "$primary" ]]; then
        pass "GCS Wi-Fi: $active_wifi"
    elif [[ -n "$fallback" && "$active_wifi" == "$fallback" ]]; then
        pass "approved field Wi-Fi fallback: $active_wifi"
    elif [[ -n "$rescue" && "$active_wifi" == "$rescue" ]]; then
        pass "approved Rescue Wi-Fi recognized: $active_wifi (management only)"
        fail "Rescue has no Pixhawk/flight authority" \
            "sudo tools/host/set_pi_network_mode.sh pixhawk"
    else
        fail "GCS Wi-Fi association: ${active_wifi:-none}" \
            "sudo tools/host/set_pi_network_mode.sh pixhawk"
    fi

    wifi_addresses="$(ip -4 -o addr show dev "$WIFI_INTERFACE" 2>/dev/null || true)"
    if grep -Fq "inet $EXPECTED_GCS_CIDR" <<< "$wifi_addresses"; then
        pass "GCS address: $EXPECTED_GCS_CIDR"
    else
        fail "GCS address $EXPECTED_GCS_CIDR absent on $WIFI_INTERFACE" \
            "ip -brief address show $WIFI_INTERFACE"
    fi

    carrier="$(cat "/sys/class/net/$ETHERNET_INTERFACE/carrier" 2>/dev/null || true)"
    if [[ "$carrier" == "1" ]]; then
        pass "Pixhawk Ethernet carrier: $ETHERNET_INTERFACE"
    else
        fail "Pixhawk Ethernet carrier absent on $ETHERNET_INTERFACE" \
            "check Pixhawk power/cable, then run sudo tools/host/set_pi_network_mode.sh pixhawk"
    fi

    eth_active="$(nmcli -g GENERAL.CONNECTION device show "$ETHERNET_INTERFACE" 2>/dev/null || true)"
    eth_profile_state="$(nmcli -g ipv4.method,ipv4.addresses,ipv4.never-default,ipv6.never-default,connection.interface-name connection show "$eth_profile" 2>/dev/null || true)"
    if [[ "$eth_active" == "$eth_profile" ]] \
        && grep -Fxq 'manual' <<< "$eth_profile_state" \
        && grep -Fxq "$EXPECTED_PIXHAWK_PI_CIDR" <<< "$eth_profile_state" \
        && [[ "$(grep -Fxc 'yes' <<< "$eth_profile_state")" -ge 2 ]] \
        && grep -Fxq "$ETHERNET_INTERFACE" <<< "$eth_profile_state"; then
        pass "Pixhawk profile: $eth_profile on $ETHERNET_INTERFACE, never-default"
    else
        fail "Pixhawk profile inactive or inconsistent: ${eth_active:-none}" \
            "sudo tools/host/set_pi_network_mode.sh status"
    fi

    eth_addresses="$(ip -4 -o addr show dev "$ETHERNET_INTERFACE" 2>/dev/null || true)"
    if grep -Fq "inet $EXPECTED_PIXHAWK_PI_CIDR" <<< "$eth_addresses"; then
        pass "Pixhawk-side Pi address: $EXPECTED_PIXHAWK_PI_CIDR"
    else
        fail "Pixhawk-side Pi address $EXPECTED_PIXHAWK_PI_CIDR absent" \
            "ip -brief address show $ETHERNET_INTERFACE"
    fi

    eth_defaults="$(ip route show default dev "$ETHERNET_INTERFACE" 2>/dev/null || true)"
    if [[ -z "$eth_defaults" ]]; then
        pass "no $ETHERNET_INTERFACE default route"
    else
        fail "$ETHERNET_INTERFACE unexpectedly owns a default route" \
            "sudo tools/host/set_pi_network_mode.sh pixhawk"
    fi

    default_routes="$(ip route show default 2>/dev/null || true)"
    if grep -Eq " dev ${WIFI_INTERFACE}([[:space:]]|$)" <<< "$default_routes" \
        && ! grep -Eq " dev ${ETHERNET_INTERFACE}([[:space:]]|$)" <<< "$default_routes"; then
        pass "default route remains on $WIFI_INTERFACE"
    else
        fail "default route is not exclusively on $WIFI_INTERFACE" \
            "ip route show default"
    fi

    if ping -c 1 -W 1 "$PIXHAWK_ADDRESS" >/dev/null 2>&1; then
        pass "Pixhawk reachable: $PIXHAWK_ADDRESS"
    else
        fail "Pixhawk unreachable: $PIXHAWK_ADDRESS" \
            "ping -c 3 -W 1 $PIXHAWK_ADDRESS"
    fi

    tailscale_state="$(systemctl is-active tailscaled.service 2>/dev/null || true)"
    if [[ "$tailscale_state" == "inactive" ]]; then
        pass "Tailscale inactive"
    else
        fail "Tailscale state: ${tailscale_state:-unknown}" \
            "sudo tools/host/set_pi_network_mode.sh pixhawk"
    fi
}

check_hardware() {
    local media_device="" topology="" scan_output="" scan_rc=1 stuck="" missing=()
    [[ -e /dev/video0 ]] && pass "camera device: /dev/video0" \
        || fail "camera device /dev/video0 missing" "see docs/debug/HAILO_RECOVERY.md"

    # Match the launcher's read-only media-graph discovery rule. Do not apply
    # links, formats, controls, or a stream probe in the static check.
    if command -v media-ctl >/dev/null 2>&1; then
        for candidate in /dev/media*; do
            [[ -e "$candidate" ]] || continue
            topology="$(timeout 5s media-ctl -d "$candidate" -p 2>/dev/null || true)"
            if grep -qi "driver[[:space:]]*rp1-cfe" <<< "$topology" \
                && grep -qiE "tevs|11-0048|rp1-cfe-csi2_ch[0-9]" <<< "$topology"; then
                media_device="$candidate"
                break
            fi
        done
    fi
    if [[ -n "$media_device" ]]; then
        pass "TEVS camera media graph: $media_device"
    else
        fail "no media device exposes the TEVS camera graph" \
            "see docs/debug/HAILO_RECOVERY.md"
    fi

    [[ -e /dev/hailo0 ]] && pass "Hailo device: /dev/hailo0" \
        || fail "Hailo device /dev/hailo0 missing" "see docs/debug/HAILO_RECOVERY.md"

    for command_name in ffmpeg ffprobe v4l2-ctl media-ctl hailortcli timeout; do
        command -v "$command_name" >/dev/null 2>&1 || missing+=("$command_name")
    done
    [[ -x /opt/ros/jazzy/bin/ros2 ]] || missing+=("/opt/ros/jazzy/bin/ros2")
    [[ -r /opt/ros/jazzy/setup.bash ]] || missing+=("/opt/ros/jazzy/setup.bash")
    [[ -r "$THESIS_ROOT/ros2_ws/install/setup.bash" ]] || missing+=("ros2_ws/install/setup.bash")
    [[ -r "$THESIS_ROOT/models/hef/yolov8s.hef" ]] || missing+=("models/hef/yolov8s.hef")
    [[ -r "$THESIS_ROOT/models/reid/mars-small128.pb" ]] || missing+=("models/reid/mars-small128.pb")
    if (( ${#missing[@]} == 0 )); then
        pass "camera/Hailo/live-launch prerequisites"
    else
        fail "missing launcher prerequisites: ${missing[*]}" \
            "see docs/debug/HAILO_RECOVERY.md and do not install/rebuild at the field"
    fi

    if command -v hailortcli >/dev/null 2>&1 && [[ -e /dev/hailo0 ]]; then
        scan_output="$(HAILORT_LOGGER_PATH="$THESIS_ROOT/ros2_ws/log/hailort" timeout 10s hailortcli scan 2>&1)"
        scan_rc=$?
    fi
    if [[ "$scan_rc" -eq 0 && -n "$scan_output" ]]; then
        pass "Hailo health: hailortcli scan"
    else
        fail "Hailo health scan" "hailortcli scan"
        [[ -n "$scan_output" ]] && printf '%s\n' "$scan_output" | tail -n 5 | sed 's/^/      /'
    fi

    stuck="$(ps -eo pid=,stat=,cmd= | awk '$2 ~ /^D/ && $0 ~ /(v4l2-ctl|media-ctl)/ {print}' || true)"
    if [[ -z "$stuck" ]]; then
        pass "no camera process stuck in uninterruptible I/O"
    else
        fail "camera process stuck in uninterruptible I/O" \
            "see docs/debug/HAILO_RECOVERY.md; a reboot is normally required"
        printf '%s\n' "$stuck" | sed 's/^/      /'
    fi
}

stale_processes() {
    local ancestor="$PPID" ancestors=" $$ " line candidate parent

    # Remote wrappers and test shells can contain the literal search pattern
    # in their own command line. Exclude this checker and its ancestor chain;
    # only independent matching processes are stale live workloads.
    while [[ "$ancestor" =~ ^[0-9]+$ ]] && (( ancestor > 1 )); do
        ancestors+="$ancestor "
        parent="$(ps -o ppid= -p "$ancestor" 2>/dev/null | tr -d ' ')"
        [[ "$parent" != "$ancestor" ]] || break
        ancestor="$parent"
    done

    while IFS= read -r line; do
        [[ -n "$line" ]] || continue
        candidate="${line%% *}"
        [[ "$ancestors" == *" $candidate "* ]] && continue
        printf '%s\n' "$line"
    done < <(pgrep -af '[s]tart_live_stack.sh|[r]os2 bag record|[r]osbag2_recorder|[r]os2 launch mavros|[m]avros_node|[c]ontrol_ref_node|[f]fmpeg.*visual_' 2>/dev/null || true)
}

check_no_stale_processes() {
    local found
    found="$(stale_processes)"
    if [[ -z "$found" ]]; then
        pass "no stale live-stack/recorder/MAVROS/controller process"
    else
        fail "stale live process detected" \
            "inspect with pgrep -af '[s]tart_live_stack.sh|[r]os2 bag record|[r]osbag2_recorder|[r]os2 launch mavros|[m]avros_node|[c]ontrol_ref_node|[f]fmpeg.*visual_'; use the live-stack> stop command when available"
        printf '%s\n' "$found" | sed 's/^/      /'
    fi
}

run_static_checks() {
    load_project_defaults
    check_repository
    check_storage
    check_field_network
    check_hardware
    check_no_stale_processes
}

passive_cleanup() {
    if [[ -n "$PASSIVE_LAUNCH_PID" ]] && kill -0 "$PASSIVE_LAUNCH_PID" >/dev/null 2>&1; then
        if [[ "$PASSIVE_FIFO_FD_OPEN" -eq 1 ]]; then
            printf 'stop\n' >&3 2>/dev/null || true
        fi
        wait "$PASSIVE_LAUNCH_PID" 2>/dev/null || true
    fi
    if [[ "$PASSIVE_FIFO_FD_OPEN" -eq 1 ]]; then
        exec 3>&-
        PASSIVE_FIFO_FD_OPEN=0
    fi
    [[ -n "$PASSIVE_FIFO" ]] && rm -f -- "$PASSIVE_FIFO"
    PASSIVE_LAUNCH_PID=""
    PASSIVE_FIFO=""
}

observe_live_mavros() {
    local run_dir="$1" state_log frame_log publisher_log raw_log state_ok=0 raw_ok=0 frame_ok=0 publishers_ok=0
    state_log="$run_dir/preflight_mavros_state.txt"
    raw_log="$run_dir/preflight_mavros_raw_imu.txt"
    frame_log="$run_dir/preflight_mavros_frame.txt"
    publisher_log="$run_dir/preflight_setpoint_publishers.txt"

    set +u
    # shellcheck disable=SC1091
    source /opt/ros/jazzy/setup.bash
    # shellcheck disable=SC1091
    source "$THESIS_ROOT/ros2_ws/install/setup.bash"
    set +u
    export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"

    timeout 8s ros2 topic echo /mavros/state >"$state_log" 2>&1 || true
    if grep -Fq 'connected: true' "$state_log" && grep -Fq 'armed: false' "$state_log"; then
        state_ok=1
        pass "MAVROS telemetry: connected=true, armed=false"
    else
        fail "MAVROS state did not prove connected=true and armed=false" \
            "cat $state_log"
    fi

    if timeout 10s ros2 topic echo /mavros/imu/data_raw --once >"$raw_log" 2>&1; then
        raw_ok=1
        pass "MAVROS raw IMU"
    else
        fail "MAVROS raw IMU unavailable" "cat $raw_log"
    fi

    ros2 param get /mavros/setpoint_velocity mav_frame >"$frame_log" 2>&1 || true
    if grep -Fxq 'String value is: BODY_NED' "$frame_log"; then
        frame_ok=1
        pass "MAVROS setpoint frame: BODY_NED"
    else
        fail "MAVROS setpoint frame is not BODY_NED" "cat $frame_log"
    fi

    ros2 topic info /mavros/setpoint_velocity/cmd_vel -v >"$publisher_log" 2>&1 || true
    if grep -Fxq 'Publisher count: 0' "$publisher_log"; then
        publishers_ok=1
        pass "MAVROS velocity-command publishers: 0"
    else
        fail "MAVROS velocity-command publisher count is not zero" \
            "cat $publisher_log; do not proceed to controller authority"
    fi

    [[ "$state_ok" -eq 1 && "$raw_ok" -eq 1 && "$frame_ok" -eq 1 && "$publishers_ok" -eq 1 ]]
}

check_passive_evidence() {
    local bag_dir="$1" summary_output summary_rc
    summary_output="$(python3 "$SUMMARY_TOOL" --bag-dir "$bag_dir" 2>&1)"
    summary_rc=$?
    printf '%s\n' "$summary_output" | sed 's/^/      /'
    if [[ "$summary_rc" -eq 0 ]] \
        && grep -Fq 'transport: observed_zero count=0 parse_ok=True' <<< "$summary_output" \
        && grep -Fq 'runtime_evidence_acceptable: True' <<< "$summary_output"; then
        pass "structured recorder: observed_zero transport loss"
        pass "visual evidence and evidence-package finalization"
        return 0
    fi
    fail "passive structured/visual evidence did not meet the strict gate" \
        "python3 tools/live/summarize_field_evidence.py --bag-dir \"$bag_dir\""
    return 1
}

run_passive_live_gate() {
    local run_id tag bag_dir run_dir deadline ready=0 gate_start elapsed remaining launcher_rc
    local launch=("$THESIS_ROOT/tools/start_live_stack.sh" --res vga --field-record --no-control --tag)

    if ! [[ "$PASSIVE_GATE_SECONDS" =~ ^[0-9]+$ ]] \
        || (( PASSIVE_GATE_SECONDS < 30 || PASSIVE_GATE_SECONDS > 45 )); then
        fail "passive gate duration must be 30-45 seconds (got $PASSIVE_GATE_SECONDS)" \
            "unset FIELD_PREFLIGHT_GATE_SECONDS"
        return
    fi

    run_id="$(date +%Y-%m-%d__%H-%M-%S)"
    tag="field_preflight_passive_ground"
    bag_dir="${BAG_OUT_ROOT:-$THESIS_ROOT/bags/live_camera}/${run_id}__video__${tag}"
    run_dir="$THESIS_ROOT/ros2_ws/log/live_stack/$run_id"
    if [[ -e "$bag_dir" ]]; then
        fail "passive gate output already exists: $bag_dir" "rerun after the clock advances"
        return
    fi

    note "NON-HELD-OUT DEVELOPMENT / FIELD GROUND GATE"
    note "aircraft must remain disarmed and stationary; controller and command mirroring are off"
    note "RUN_ID=$run_id"
    note "recording for ${PASSIVE_GATE_SECONDS}s after recorder readiness"

    PASSIVE_FIFO="$(mktemp -u "/tmp/thesis-field-preflight.${run_id}.XXXXXX")"
    if ! mkfifo "$PASSIVE_FIFO"; then
        fail "could not create passive-gate control FIFO" "check /tmp permissions"
        PASSIVE_FIFO=""
        return
    fi
    exec 3<>"$PASSIVE_FIFO"
    PASSIVE_FIFO_FD_OPEN=1

    RUN_ID="$run_id" "${launch[@]}" "$tag" <"$PASSIVE_FIFO" &
    PASSIVE_LAUNCH_PID=$!

    deadline=$((SECONDS + PASSIVE_GATE_STARTUP_TIMEOUT_S))
    while (( SECONDS < deadline )); do
        if ! kill -0 "$PASSIVE_LAUNCH_PID" >/dev/null 2>&1; then
            break
        fi
        if [[ -f "$bag_dir/flight_metadata.txt" && -s "$bag_dir/visual_${run_id}.mkv" ]]; then
            ready=1
            break
        fi
        sleep 1
    done

    if [[ "$ready" -ne 1 ]]; then
        fail "passive live gate did not reach recorder readiness" \
            "inspect $run_dir and any partial $bag_dir"
        if kill -0 "$PASSIVE_LAUNCH_PID" >/dev/null 2>&1; then
            printf 'stop\n' >&3
        fi
    else
        gate_start=$SECONDS
        observe_live_mavros "$run_dir" || true
        elapsed=$((SECONDS - gate_start))
        remaining=$((PASSIVE_GATE_SECONDS - elapsed))
        (( remaining > 0 )) && sleep "$remaining"
        printf 'stop\n' >&3
    fi

    wait "$PASSIVE_LAUNCH_PID"
    launcher_rc=$?
    PASSIVE_LAUNCH_PID=""
    exec 3>&-
    PASSIVE_FIFO_FD_OPEN=0
    rm -f -- "$PASSIVE_FIFO"
    PASSIVE_FIFO=""

    if [[ "$launcher_rc" -eq 0 ]]; then
        pass "passive launcher stopped through the normal stop path"
    else
        fail "passive launcher exited with status $launcher_rc" \
            "inspect $run_dir and $bag_dir"
    fi

    if [[ -d "$bag_dir" ]]; then
        check_passive_evidence "$bag_dir" || true
        note "passive evidence retained: $bag_dir"
    else
        fail "passive evidence directory missing: $bag_dir" "inspect $run_dir"
    fi
    check_no_stale_processes
}

print_human_gates() {
    cat <<'EOF_GATES'

HUMAN PHYSICAL GATES NOT VALIDATED BY THIS COMMAND:
  - RC takeover and RC failsafe
  - PreArm/arming readiness
  - physical controller direction/sign correctness
  - restrained/props-off command-path correctness
  - pilot judgement and actual flight safety
EOF_GATES
}

print_final_status() {
    print_human_gates
    if [[ "$FAILURES" -eq 0 ]]; then
        printf '\nSOFTWARE/PASSIVE PREFLIGHT: READY FOR HUMAN PHYSICAL SAFETY GATES\n'
        return 0
    fi
    printf '\nSOFTWARE/PASSIVE PREFLIGHT: NOT READY\n'
    printf 'Failed checks: %d\n' "$FAILURES"
    return 1
}

main() {
    if [[ $# -gt 1 ]]; then
        usage
        return 2
    fi
    case "${1:-}" in
        "") ;;
        --passive-live-gate) PASSIVE_REQUESTED=1 ;;
        -h|--help) usage; return 0 ;;
        *) usage; return 2 ;;
    esac

    trap passive_cleanup INT TERM EXIT
    printf 'Field software/passive preflight (non-actuating)\n\n'
    run_static_checks

    if [[ "$PASSIVE_REQUESTED" -eq 1 ]]; then
        if [[ "$FAILURES" -eq 0 ]]; then
            printf '\nPassive live gate\n'
            run_passive_live_gate
        else
            fail "passive live gate refused because static preflight failed" \
                "resolve the failures above, then rerun with --passive-live-gate"
        fi
    else
        note "passive MAVROS/recording gate not requested"
    fi

    print_final_status
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    main "$@"
fi
