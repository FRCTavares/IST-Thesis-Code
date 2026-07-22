"""Tests for the unattended Pi host-only recovery contract."""

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "tools/host/thesis_host_health.py"
DEPLOY_ROOT = REPO_ROOT / "deploy/host_recovery/systemd"

SPEC = importlib.util.spec_from_file_location("thesis_host_health", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
HOST_HEALTH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HOST_HEALTH)


def _snapshot(**overrides):
    snapshot = {
        "network_ok": True,
        "tailscale_ok": True,
        "ssh_ok": True,
        "tailscaled_active": True,
    }
    snapshot.update(overrides)
    return snapshot


def _state(**overrides):
    state = dict(HOST_HEALTH.DEFAULT_STATE)
    state.update(overrides)
    return state


def test_healthy_snapshot_clears_failure_counters_and_takes_no_action():
    state = _state(network_failures=9, tailscale_failures=4, ssh_failures=2)
    updated = HOST_HEALTH.update_failure_counters(_snapshot(), state)

    assert updated["network_failures"] == 0
    assert updated["tailscale_failures"] == 0
    assert updated["ssh_failures"] == 0
    assert HOST_HEALTH.choose_recovery_actions(
        _snapshot(),
        updated,
        now_epoch=10_000,
        failure_threshold=3,
        cooldown_seconds=900,
    ) == []


def test_network_recovery_requires_consecutive_failures_and_cooldown():
    failed = _snapshot(network_ok=False, tailscale_ok=False)
    below_threshold = _state(network_failures=2, tailscale_failures=2)
    assert HOST_HEALTH.choose_recovery_actions(
        failed,
        below_threshold,
        now_epoch=10_000,
        failure_threshold=3,
        cooldown_seconds=900,
    ) == []

    eligible = _state(network_failures=3, tailscale_failures=3)
    assert HOST_HEALTH.choose_recovery_actions(
        failed,
        eligible,
        now_epoch=10_000,
        failure_threshold=3,
        cooldown_seconds=900,
    ) == ["network_reconnect"]

    cooling_down = _state(
        network_failures=4,
        tailscale_failures=4,
        last_network_recovery_epoch=9_500,
    )
    assert HOST_HEALTH.choose_recovery_actions(
        failed,
        cooling_down,
        now_epoch=10_000,
        failure_threshold=3,
        cooldown_seconds=900,
    ) == []


def test_tailscale_is_not_restarted_while_underlying_network_is_down():
    actions = HOST_HEALTH.choose_recovery_actions(
        _snapshot(network_ok=False, tailscale_ok=False),
        _state(network_failures=1, tailscale_failures=20),
        now_epoch=10_000,
        failure_threshold=3,
        cooldown_seconds=900,
    )

    assert "tailscale_restart" not in actions


def test_tailscale_and_ssh_recovery_are_host_only_and_bounded():
    actions = HOST_HEALTH.choose_recovery_actions(
        _snapshot(tailscale_ok=False, ssh_ok=False),
        _state(tailscale_failures=3, ssh_failures=3),
        now_epoch=10_000,
        failure_threshold=3,
        cooldown_seconds=900,
    )

    assert actions == ["tailscale_restart", "ssh_socket_restart"]
    assert HOST_HEALTH.ACTION_COMMANDS["tailscale_restart"] == [
        "systemctl",
        "restart",
        "tailscaled.service",
    ]
    assert HOST_HEALTH.ACTION_COMMANDS["ssh_socket_restart"] == [
        "systemctl",
        "restart",
        "ssh.socket",
    ]


def test_pixhawk_mode_stops_tailscale_and_never_restarts_it():
    actions = HOST_HEALTH.choose_recovery_actions(
        _snapshot(tailscale_ok=False, tailscaled_active=True),
        _state(tailscale_failures=20),
        now_epoch=10_000,
        failure_threshold=3,
        cooldown_seconds=900,
        mode="pixhawk",
    )

    assert actions == ["tailscale_stop"]
    assert HOST_HEALTH.ACTION_COMMANDS["tailscale_stop"] == [
        "systemctl",
        "stop",
        "tailscaled.service",
    ]


def test_pixhawk_network_recovery_uses_exact_aeronext_profile():
    commands = []

    def runner(command, *, timeout):
        import subprocess

        commands.append((list(command), timeout))
        return subprocess.CompletedProcess(command, 0, "", "")

    HOST_HEALTH.execute_actions(
        ["network_reconnect"],
        interface="wlan0",
        mode="pixhawk",
        pixhawk_wifi_connection="ISR Aero.Next GCS",
        dry_run=False,
        runner=runner,
    )

    assert commands == [
        ([
            "nmcli", "connection", "up", "ISR Aero.Next GCS",
            "ifname", "wlan0",
        ], 45.0)
    ]


def test_systemd_units_never_start_thesis_or_aircraft_processes():
    service = (DEPLOY_ROOT / "thesis-host-health.service").read_text(
        encoding="utf-8"
    )
    exec_lines = [
        line for line in service.splitlines() if line.startswith("ExecStart=")
    ]

    assert exec_lines == [
        "ExecStart=/usr/bin/python3 /usr/local/libexec/thesis_host_health.py"
    ]
    assert "start_live_stack" not in service
    assert "mavros" not in service.lower()
    assert "control_ref" not in service


def test_retention_watchdog_and_restart_limits_are_explicit():
    journal = (
        DEPLOY_ROOT / "journald.conf.d/10-thesis-retention.conf"
    ).read_text(encoding="utf-8")
    watchdog = (
        DEPLOY_ROOT / "system.conf.d/10-thesis-watchdog.conf"
    ).read_text(encoding="utf-8")
    tailscale = (
        DEPLOY_ROOT / "tailscaled.service.d/10-thesis-recovery.conf"
    ).read_text(encoding="utf-8")
    timer = (DEPLOY_ROOT / "thesis-host-health.timer").read_text(
        encoding="utf-8"
    )

    assert "SystemMaxUse=1G" in journal
    assert "SystemKeepFree=10G" in journal
    assert "MaxRetentionSec=30day" in journal
    assert "RuntimeWatchdogSec=30s" in watchdog
    assert "Restart=always" in tailscale
    assert "RestartSec=10s" in tailscale
    assert "OnUnitActiveSec=2min" in timer
    assert "Persistent=true" in timer


def test_installer_enforces_tailscale_only_inbound_firewall():
    installer = (
        REPO_ROOT / "tools/host/install_unattended_host_recovery.sh"
    ).read_text(encoding="utf-8")

    assert "ufw default deny incoming" in installer
    assert "ufw default allow outgoing" in installer
    assert "ufw allow in on tailscale0" in installer
    assert 'proto udp to any port 41641' in installer
    assert 'ufw allow in on eth0 proto udp to any port 14550' in installer
    assert "ufw allow 22" not in installer
    assert "ufw allow OpenSSH" not in installer


def test_field_stack_enters_network_mode_instead_of_direct_ethernet_up():
    live_stack = (REPO_ROOT / "tools/start_live_stack.sh").read_text(
        encoding="utf-8"
    )

    assert live_stack.count(
        'sudo "$THESIS_ROOT/tools/host/set_pi_network_mode.sh" pixhawk'
    ) == 2
    assert "sudo nmcli connection up pixhawk-apm" not in live_stack


def test_network_mode_script_is_fail_closed():
    mode_script = (
        REPO_ROOT / "tools/host/set_pi_network_mode.sh"
    ).read_text(encoding="utf-8")

    wifi_up = 'nmcli connection up "$PIXHAWK_WIFI"'
    mode_persist = "set_mode pixhawk"
    tailscale_stop = "systemctl disable --now tailscaled.service"
    assert mode_script.index(wifi_up) < mode_script.index(mode_persist)
    assert mode_script.index(wifi_up) < mode_script.index(tailscale_stop)
    assert "ipv4.never-default yes ipv6.never-default yes" in mode_script
