#!/usr/bin/env bash
# Issue #54, required-work item 9: measure the raw-image stream's onboard
# cost on the Pi (not merely calculate width*height*bpp*fps and call it
# measured DDS bandwidth). Runs the live stack twice, minimal downstream
# (camera+perception only): once with /camera/image_raw publishing off
# (the new default), once forced on, sampling CPU/RSS for the
# perception_camera process in both, and measuring achieved rate (ros2
# topic hz) and serialized DDS bandwidth (ros2 topic bw) only in the "on"
# condition, where the topic actually exists.

export GIT_PAGER=cat PAGER=cat

THESIS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$THESIS_ROOT" || exit 1

# ROS's own setup.bash references unset variables internally; keep -u off
# for sourcing regardless of the caller's shell options.
set +u
source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash
set -u

# start_live_stack.sh defaults ROS_DOMAIN_ID to 42 *inside its own
# subshell*; this script's `ros2 topic` calls run in the parent shell and
# must join the same domain or they silently see an empty graph.
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"

OUT_DIR="${1:-$THESIS_ROOT/reports/p054_raw_image_transport_cost_$(date +%Y%m%d_%H%M%S)}"
mkdir -p "$OUT_DIR"

WARMUP_S=15
SAMPLE_S=20
HZ_WINDOW_S=10
BW_WINDOW_S=10

run_condition() {
    local label="$1"
    shift
    local -a extra_args=("$@")

    local ctl_fifo="$OUT_DIR/${label}_ctl.fifo"
    local stack_log="$OUT_DIR/${label}_stack.log"
    local cpu_rss_log="$OUT_DIR/${label}_cpu_rss.csv"
    local hz_log="$OUT_DIR/${label}_hz.txt"
    local bw_log="$OUT_DIR/${label}_bw.txt"
    local topic_list_log="$OUT_DIR/${label}_topic_list.txt"

    rm -f "$ctl_fifo"
    mkfifo "$ctl_fifo"
    exec 9<>"$ctl_fifo"

    echo "[measure] starting condition '$label' (${extra_args[*]:-<defaults>})"
    ./tools/start_live_stack.sh --no-dashboard --no-control --no-web-video --no-tracker \
        "${extra_args[@]}" <&9 >"$stack_log" 2>&1 &
    local stack_pid=$!

    sleep "$WARMUP_S"

    if ! kill -0 "$stack_pid" 2>/dev/null; then
        echo "[error] live stack exited during warmup for condition '$label'; see $stack_log"
        exec 9>&-
        rm -f "$ctl_fifo"
        return 1
    fi

    # `ros2 run` execs directly into the resolved installed script, so the
    # process's argv no longer contains "ros2 run ..." -- match the
    # installed entry-point path instead.
    local cam_pid
    cam_pid="$(pgrep -f 'lib/thesis_bringup/perception_camera_node' | head -n 1)"
    if [[ -z "$cam_pid" ]]; then
        echo "[error] could not find perception_camera_node pid for condition '$label'"
        echo "stop" >&9
        wait "$stack_pid" 2>/dev/null
        exec 9>&-
        rm -f "$ctl_fifo"
        return 1
    fi
    echo "[measure] perception_camera_node pid=$cam_pid"

    ros2 topic list > "$topic_list_log" 2>&1

    echo "elapsed_s,cpu_percent,rss_kib" > "$cpu_rss_log"
    local t=0
    while [[ "$t" -lt "$SAMPLE_S" ]]; do
        ps -o %cpu=,rss= -p "$cam_pid" 2>/dev/null | \
            awk -v t="$t" '{gsub(/^ +| +$/,""); split($0,a," "); print t","a[1]","a[2]}' >> "$cpu_rss_log"
        sleep 1
        t=$((t + 1))
    done

    if [[ "$label" == "on" ]]; then
        echo "[measure] running ros2 topic hz /camera/image_raw for ${HZ_WINDOW_S}s"
        timeout "$HZ_WINDOW_S" ros2 topic hz /camera/image_raw > "$hz_log" 2>&1
        echo "[measure] running ros2 topic bw /camera/image_raw for ${BW_WINDOW_S}s"
        timeout "$BW_WINDOW_S" ros2 topic bw /camera/image_raw > "$bw_log" 2>&1
    fi

    echo "stop" >&9
    wait "$stack_pid" 2>/dev/null
    exec 9>&-
    rm -f "$ctl_fifo"
    echo "[measure] condition '$label' complete"
}

run_condition off
run_condition on --camera-publish-image-raw

echo "[measure] all conditions complete, evidence in $OUT_DIR"
