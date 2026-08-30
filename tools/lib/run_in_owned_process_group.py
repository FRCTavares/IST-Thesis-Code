#!/usr/bin/env python3
"""Run one command in an owned process group and supervise its lifetime.

The supervisor itself remains the PID tracked by the calling shell. A forked
child creates a new session/process group with setsid() and then execs the
requested command. Signals sent to the supervisor are forwarded to the whole
owned child process group.

SIGUSR1 is reserved as an escalation request and is forwarded as SIGKILL to
the owned child process group.
"""

from __future__ import annotations

import os
import signal
import sys
import time


def _exit_code_from_wait_status(status: int) -> int:
    if os.WIFEXITED(status):
        return os.WEXITSTATUS(status)
    if os.WIFSIGNALED(status):
        return 128 + os.WTERMSIG(status)
    return 1


def _group_alive(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _signal_group(pgid: int, sig: int) -> None:
    try:
        os.killpg(pgid, sig)
    except ProcessLookupError:
        pass


def _cleanup_remaining_group(pgid: int) -> None:
    if not _group_alive(pgid):
        return

    _signal_group(pgid, signal.SIGTERM)

    for _ in range(20):
        if not _group_alive(pgid):
            return
        time.sleep(0.05)

    _signal_group(pgid, signal.SIGKILL)


def main() -> int:
    if len(sys.argv) < 2:
        print(
            "usage: run_in_owned_process_group.py COMMAND [ARG ...]",
            file=sys.stderr,
        )
        return 2

    ready_read, ready_write = os.pipe()
    child_pid = os.fork()

    if child_pid == 0:
        os.close(ready_read)

        try:
            os.setsid()
            os.write(ready_write, b"1")
            os.close(ready_write)
            os.execvp(sys.argv[1], sys.argv[1:])
        except BaseException as exc:
            try:
                os.close(ready_write)
            except OSError:
                pass
            print(
                f"owned-process-group launch failed: {exc}",
                file=sys.stderr,
            )
            os._exit(127)

    os.close(ready_write)

    ready = False
    pending_signals: list[int] = []

    def forward_signal(signum: int, _frame: object) -> None:
        forwarded = signal.SIGKILL if signum == signal.SIGUSR1 else signum

        if ready:
            _signal_group(child_pid, forwarded)
        else:
            pending_signals.append(forwarded)

    signal.signal(signal.SIGINT, forward_signal)
    signal.signal(signal.SIGTERM, forward_signal)
    signal.signal(signal.SIGHUP, forward_signal)
    signal.signal(signal.SIGUSR1, forward_signal)

    try:
        ready_byte = os.read(ready_read, 1)
    finally:
        os.close(ready_read)

    ready = ready_byte == b"1"

    if ready:
        for pending_signal in pending_signals:
            _signal_group(child_pid, pending_signal)

    while True:
        try:
            waited_pid, status = os.waitpid(child_pid, 0)
            break
        except InterruptedError:
            continue

    if waited_pid != child_pid:
        return 1

    _cleanup_remaining_group(child_pid)
    return _exit_code_from_wait_status(status)


if __name__ == "__main__":
    raise SystemExit(main())
