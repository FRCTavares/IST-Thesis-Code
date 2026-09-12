"""Issue #50/#74 deliberate shutdown ordering (no Pixhawk, no ROS).

Drives ``tools/lib/live_shutdown.sh`` against fake background processes that
log the signals they receive, proving:

- a cleanly-exiting recorder gets SIGINT and never SIGTERM;
- a recorder that takes several seconds (< grace) finalizes gracefully;
- a recorder that ignores SIGINT is escalated to SIGTERM after the grace;
- application publishers are stopped before the recorders finalize.
"""

from __future__ import annotations

import subprocess
import textwrap
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB = REPO_ROOT / "tools" / "lib" / "live_shutdown.sh"

# A real recorder is a Python program (`ros2 bag record`) that installs its
# own SIGINT handler regardless of the inherited disposition; a bash
# background job cannot trap SIGINT, so the fake is Python too.
FAKE_PROC = textwrap.dedent(
    """\
    import os, signal, sys, time
    behaviour, sigfile = sys.argv[1], sys.argv[2]

    def log(name):
        with open(sigfile, "a") as fh:
            fh.write("%s %.6f\\n" % (name, time.time()))

    def on_int(_s, _f):
        log("INT")
        if behaviour == "exit_on_int":
            sys.exit(0)
        if behaviour == "slow_finalize":
            time.sleep(float(os.environ.get("FINALIZE_SECS", "2")))
            sys.exit(0)
        # ignore_int: only log, keep running

    def on_term(_s, _f):
        log("TERM")
        sys.exit(143)

    signal.signal(signal.SIGINT, on_int)
    signal.signal(signal.SIGTERM, on_term)
    while True:
        time.sleep(0.2)
    """
)


def _run_shutdown(tmp_path: Path, procs: list[tuple[str, str]], call: str,
                  env_extra: dict[str, str] | None = None) -> dict:
    """procs = list of (name, behaviour); `call` is the shutdown function line."""
    fake = tmp_path / "fake_proc.py"
    fake.write_text(FAKE_PROC)
    pid_file = tmp_path / "pids.txt"

    launch = []
    for name, behaviour in procs:
        sigfile = tmp_path / f"{name}.sig"
        # Redirect the fake's own stdio to a file (like start_ros_bg does) so a
        # still-running fake never holds the captured pipe open.
        launch.append(
            f'python3 {fake} {behaviour} "{sigfile}" >"{tmp_path}/{name}.out" 2>&1 & '
            f'echo "$! {name}" >> "{pid_file}"'
        )
    env_lines = "\n".join(
        f'export {k}={v}' for k, v in (env_extra or {}).items()
    )
    script = textwrap.dedent(
        f"""\
        set +u
        {env_lines}
        export PID_FILE="{pid_file}"
        export RUN_DIR="{tmp_path}"
        source "{LIB}"
        {chr(10).join(launch)}
        sleep 0.4
        START=$(date +%s.%N)
        {call}
        END=$(date +%s.%N)
        python3 -c "import sys; print('ELAPSED %.3f' % (float(sys.argv[2]) - float(sys.argv[1])))" "$START" "$END"
        echo "OUTCOME ${{RECORDER_FINALIZE_OUTCOME:-unset}}"
        """
    )
    result = None
    try:
        result = subprocess.run(
            ["bash", "-c", script], capture_output=True, text=True, timeout=60
        )
    finally:
        # The harness `bash -c` has returned by now; reap any fake that was
        # never signalled (its stdio is redirected to a file so it never held
        # the captured pipe -- this is just tidy-up).
        subprocess.run(["pkill", "-9", "-f", str(fake)], capture_output=True)
    assert result is not None and result.returncode == 0, (
        (result.stderr + result.stdout) if result else "subprocess timed out"
    )

    sigs = {}
    for name, _ in procs:
        p = tmp_path / f"{name}.sig"
        sigs[name] = (
            [ln.split() for ln in p.read_text().splitlines()]
            if p.is_file()
            else []
        )
    out = {"sigs": sigs, "stdout": result.stdout}
    for line in result.stdout.splitlines():
        if line.startswith("OUTCOME "):
            out["outcome"] = line.split(maxsplit=1)[1]
        if line.startswith("ELAPSED "):
            out["elapsed"] = float(line.split()[1])
    return out


# --------------------------------------------------------------------------- #
def test_recorder_name_classification():
    script = (
        f'source "{LIB}"; '
        'for n in rosbag dataset_rosbag raw_image_bag control tracker '
        'perception_camera mavros; do '
        'if _live_is_recorder_name "$n"; then echo "$n rec"; '
        'else echo "$n app"; fi; done'
    )
    out = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    lines = dict(ln.split() for ln in out.stdout.split("\n") if ln)
    assert lines["rosbag"] == "rec"
    assert lines["dataset_rosbag"] == "rec"
    assert lines["raw_image_bag"] == "rec"
    assert lines["control"] == "app"
    assert lines["perception_camera"] == "app"
    assert lines["mavros"] == "app"


# A. recorder gets SIGINT, never SIGTERM
def test_clean_recorder_gets_sigint_and_no_sigterm(tmp_path):
    out = _run_shutdown(
        tmp_path,
        [("rosbag", "exit_on_int")],
        "finalize_recorders",
        {"RECORDER_FINALIZE_GRACE_S": "6"},
    )
    kinds = [s[0] for s in out["sigs"]["rosbag"]]
    assert "INT" in kinds
    assert "TERM" not in kinds
    assert out["outcome"] == "graceful"


# B. slow-but-within-grace finalizes gracefully
def test_slow_recorder_within_grace_finalizes_gracefully(tmp_path):
    out = _run_shutdown(
        tmp_path,
        [("rosbag", "slow_finalize")],
        "finalize_recorders",
        {"RECORDER_FINALIZE_GRACE_S": "8", "FINALIZE_SECS": "3"},
    )
    kinds = [s[0] for s in out["sigs"]["rosbag"]]
    assert kinds == ["INT"]
    assert out["outcome"] == "graceful"
    assert 2.5 < out["elapsed"] < 8.0
    assert (tmp_path / "recorder_finalize_outcome.txt").read_text().strip() == "graceful"


# C. ignoring SIGINT is escalated to SIGTERM after the grace
def test_recorder_ignoring_sigint_is_escalated(tmp_path):
    out = _run_shutdown(
        tmp_path,
        [("rosbag", "ignore_int")],
        "finalize_recorders",
        {"RECORDER_FINALIZE_GRACE_S": "2"},
    )
    kinds = [s[0] for s in out["sigs"]["rosbag"]]
    assert kinds[0] == "INT"
    assert "TERM" in kinds
    assert out["outcome"] == "escalated"
    assert out["elapsed"] >= 2.0


# D. application publishers stop before recorders finalize
def test_publishers_stop_before_recorder_finalization(tmp_path):
    out = _run_shutdown(
        tmp_path,
        [("control", "exit_on_int"), ("rosbag", "slow_finalize")],
        'stop_app_nodes; echo "APP_DONE $(date +%s.%N)"; finalize_recorders',
        {
            "STOP_APP_GRACE_S": "3",
            "RECORDER_FINALIZE_GRACE_S": "8",
            "FINALIZE_SECS": "1",
        },
    )
    control_int = float(out["sigs"]["control"][0][1])
    rosbag_int = float(out["sigs"]["rosbag"][0][1])
    app_done = float(
        next(ln for ln in out["stdout"].splitlines() if ln.startswith("APP_DONE")).split()[1]
    )
    # the publisher is signalled during stop_app_nodes; the recorder is only
    # signalled by finalize_recorders, which runs afterwards
    assert control_int < rosbag_int
    assert control_int <= app_done + 0.01
    assert rosbag_int >= app_done - 0.01
    assert [s[0] for s in out["sigs"]["control"]] == ["INT"]
    assert [s[0] for s in out["sigs"]["rosbag"]] == ["INT"]
    assert out["outcome"] == "graceful"


def test_no_recorder_reports_none(tmp_path):
    out = _run_shutdown(
        tmp_path,
        [("control", "exit_on_int")],
        "finalize_recorders",
        {"RECORDER_FINALIZE_GRACE_S": "3"},
    )
    assert out["outcome"] == "none"
    assert [s[0] for s in out["sigs"]["control"]] == []

def test_unrelated_rosbag_process_is_not_killed(tmp_path):
    unrelated = subprocess.Popen(
        ["bash", "-c", "exec -a \"ros2 bag record unrelated\" sleep 60"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        out = _run_shutdown(
            tmp_path,
            [("rosbag", "exit_on_int")],
            "finalize_recorders",
            {"RECORDER_FINALIZE_GRACE_S": "4"},
        )
        assert out["outcome"] == "graceful"
        assert unrelated.poll() is None
    finally:
        if unrelated.poll() is None:
            unrelated.terminate()
            try:
                unrelated.wait(timeout=3)
            except subprocess.TimeoutExpired:
                unrelated.kill()
                unrelated.wait(timeout=3)
