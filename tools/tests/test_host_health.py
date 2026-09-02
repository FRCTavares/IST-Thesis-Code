"""Tests for the unattended Pi host-only recovery contract."""

import importlib.util
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "tools/host/thesis_host_health.py"
SYSTEMD_ASSET_ROOT = REPO_ROOT / "tools/host/systemd"

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
        "pixhawk_network_valid": True,
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


def test_nominally_connected_but_unreachable_network_requests_bounded_recovery():
    actions = HOST_HEALTH.choose_recovery_actions(
        _snapshot(network_ok=False, tailscale_ok=False),
        _state(network_failures=3, tailscale_failures=3),
        now_epoch=10_000,
        failure_threshold=3,
        cooldown_seconds=900,
    )

    assert actions == ["network_reconnect"]


def test_unattended_network_recovery_only_reenables_device_autoconnect():
    commands = []

    def runner(command, *, timeout):
        commands.append((list(command), timeout))
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="",
            stderr="",
        )

    results = HOST_HEALTH.execute_actions(
        ["network_reconnect"],
        interface="wlan0",
        mode="unattended",
        dry_run=False,
        runner=runner,
    )

    assert results == {"network_reconnect": 0}
    assert commands == [
        (
            [
                "nmcli",
                "device",
                "set",
                "wlan0",
                "autoconnect",
                "yes",
            ],
            45.0,
        )
    ]
    assert HOST_HEALTH.ACTION_COMMANDS["network_reconnect"] == [
        "nmcli",
        "device",
        "set",
    ]


def test_health_monitor_contains_no_generic_nmcli_device_connect():
    health_source = (
        REPO_ROOT / "tools/host/thesis_host_health.py"
    ).read_text(encoding="utf-8")

    assert '"nmcli", "device", "connect"' not in health_source
    assert "'nmcli', 'device', 'connect'" not in health_source


def test_persistent_network_failure_escalates_to_networkmanager_restart():
    actions = HOST_HEALTH.choose_recovery_actions(
        _snapshot(network_ok=False, tailscale_ok=False),
        _state(network_failures=6, tailscale_failures=6),
        now_epoch=10_000,
        failure_threshold=3,
        cooldown_seconds=900,
    )

    assert actions == ["network_manager_restart"]
    assert HOST_HEALTH.ACTION_COMMANDS["network_manager_restart"] == [
        "systemctl",
        "restart",
        "NetworkManager.service",
    ]


def test_networkmanager_restart_has_independent_cooldown():
    actions = HOST_HEALTH.choose_recovery_actions(
        _snapshot(network_ok=False, tailscale_ok=False),
        _state(
            network_failures=6,
            tailscale_failures=6,
            last_network_recovery_epoch=9_800,
            last_network_manager_recovery_epoch=0,
        ),
        now_epoch=10_000,
        failure_threshold=3,
        cooldown_seconds=900,
    )

    assert actions == ["network_manager_restart"]


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




def test_systemd_units_never_start_thesis_or_aircraft_processes():
    service = (SYSTEMD_ASSET_ROOT / "thesis-host-health.service").read_text(
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
    assert "reboot" not in service.lower()


def test_retention_watchdog_and_restart_limits_are_explicit():
    journal = (
        SYSTEMD_ASSET_ROOT / "journald.conf.d/10-thesis-retention.conf"
    ).read_text(encoding="utf-8")
    watchdog = (
        SYSTEMD_ASSET_ROOT / "system.conf.d/10-thesis-watchdog.conf"
    ).read_text(encoding="utf-8")
    tailscale = (
        SYSTEMD_ASSET_ROOT / "tailscaled.service.d/10-thesis-recovery.conf"
    ).read_text(encoding="utf-8")
    timer = (SYSTEMD_ASSET_ROOT / "thesis-host-health.timer").read_text(
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


def test_installer_persists_field_wifi_as_non_autoconnecting():
    installer = (
        REPO_ROOT / "tools/host/install_unattended_host_recovery.sh"
    ).read_text(encoding="utf-8")

    assert "disable_field_wifi_autoconnect()" in installer
    assert "THESIS_HOST_PIXHAWK_WIFI_CONNECTION" in installer
    assert "THESIS_HOST_PIXHAWK_WIFI_FALLBACK_CONNECTION" in installer
    assert 'connection.autoconnect no' in installer
    assert "source /etc/default/thesis-host-health" in installer
    assert (
        installer.index("source /etc/default/thesis-host-health")
        < installer.index(
            "disable_field_wifi_autoconnect",
            installer.index("source /etc/default/thesis-host-health"),
        )
    )


def test_host_assets_live_with_their_installer_not_in_deploy_tree():
    assert SYSTEMD_ASSET_ROOT.is_dir()
    assert not (REPO_ROOT / "deploy").exists()
    assert {
        "thesis-host-health.default",
        "thesis-host-health.service",
        "thesis-host-health.timer",
    } <= {path.name for path in SYSTEMD_ASSET_ROOT.iterdir()}


def test_live_stack_keeps_field_network_transition_out_of_normal_flight_path():
    live_stack = (REPO_ROOT / "tools/start_live_stack.sh").read_text(
        encoding="utf-8"
    )
    live_cli = (REPO_ROOT / "tools/lib/live_cli.sh").read_text(
        encoding="utf-8"
    )

    field_start = live_cli.index("        --field-record)")
    field_end = live_cli.index("        --record-raw)", field_start)
    field_block = live_cli[field_start:field_end]

    assert "RECORD_MAVROS=1" in field_block
    assert "set_pi_network_mode" not in field_block
    assert "FIELD_MAVROS_RECORD" not in field_block

    # The normal/field flight path must never change host networking during
    # stack startup. The sole retained implicit transition belongs to the
    # isolated legacy source-MAVROS capture path.
    assert live_stack.count(
        'sudo "$THESIS_ROOT/tools/host/set_pi_network_mode.sh" pixhawk'
    ) == 1
    assert '"${SOURCE_MAVROS_RECORD:-0}" -eq 1' in live_stack
    assert "sudo nmcli connection up pixhawk-apm" not in live_stack


def test_network_mode_script_is_fail_closed():
    mode_script = (
        REPO_ROOT / "tools/host/set_pi_network_mode.sh"
    ).read_text(encoding="utf-8")

    carrier_check = 'pixhawk_interface="$(require_pixhawk_carrier)"'
    field_wifi_activation = 'active_wifi="$(activate_field_wifi)"'
    mode_persist = "set_mode pixhawk"
    tailscale_stop = "systemctl disable --now tailscaled.service"

    assert mode_script.index(carrier_check) < mode_script.index(
        field_wifi_activation
    )
    assert (
        mode_script.index(field_wifi_activation)
        < mode_script.index(mode_persist)
    )
    assert (
        mode_script.index(field_wifi_activation)
        < mode_script.index(tailscale_stop)
    )
    assert (
        'for candidate in "$PIXHAWK_WIFI" "$PIXHAWK_WIFI_FALLBACK"'
        in mode_script
    )
    assert "no approved field Wi-Fi profile could be activated" in mode_script
    assert "no physical Pixhawk Ethernet carrier" in mode_script
    assert "connection.autoconnect no" in mode_script
    assert "ipv4.never-default yes ipv6.never-default yes" in mode_script
    assert 'ip route show default dev "$interface"' in mode_script

    ethernet_up = (
        'nmcli connection up "$PIXHAWK_ETHERNET" ifname "$pixhawk_interface"'
    )
    ethernet_verify = 'verify_pixhawk_ethernet_state "$pixhawk_interface"'

    assert ethernet_up in mode_script
    first_verify = mode_script.index(
        ethernet_verify,
        mode_script.index(ethernet_up),
    )
    persist = mode_script.index(mode_persist, first_verify)
    second_verify = mode_script.index(ethernet_verify, persist)

    assert mode_script.index(ethernet_up) < first_verify < persist
    assert persist < second_verify < mode_script.index(
        tailscale_stop,
        second_verify,
    )






def test_network_mode_script_defines_ordered_field_wifi_fallback():
    mode_script = (
        REPO_ROOT / "tools/host/set_pi_network_mode.sh"
    ).read_text(encoding="utf-8")

    assert "THESIS_HOST_PIXHAWK_WIFI_FALLBACK_CONNECTION" in mode_script
    assert 'for candidate in "$PIXHAWK_WIFI" "$PIXHAWK_WIFI_FALLBACK"' in mode_script
    assert "no approved field Wi-Fi profile could be activated" in mode_script



def test_pixhawk_field_wifi_loss_exits_field_mode_instead_of_reconnecting():
    actions = HOST_HEALTH.choose_recovery_actions(
        _snapshot(
            network_ok=False,
            tailscale_ok=False,
            tailscaled_active=False,
            pixhawk_network_valid=True,
        ),
        _state(network_failures=0),
        now_epoch=10_000,
        failure_threshold=3,
        cooldown_seconds=900,
        mode="pixhawk",
    )

    assert actions == ["field_mode_exit"]


def test_execute_actions_refuses_pixhawk_network_reconnect():
    commands = []

    def runner(command, *, timeout):
        commands.append((list(command), timeout))
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="",
            stderr="",
        )

    results = HOST_HEALTH.execute_actions(
        ["network_reconnect"],
        interface="wlan0",
        mode="pixhawk",
        pixhawk_wifi_connection="ISR Aero.Next GCS",
        pixhawk_wifi_fallback_connection="AERONEXT Local Router",
        dry_run=False,
        runner=runner,
    )

    assert results == {"network_reconnect": 1}
    assert commands == []


def test_pixhawk_link_loss_exits_field_mode_immediately_without_threshold():
    actions = HOST_HEALTH.choose_recovery_actions(
        _snapshot(
            network_ok=False,
            tailscale_ok=False,
            tailscaled_active=False,
            pixhawk_network_valid=False,
        ),
        _state(network_failures=0, tailscale_failures=0),
        now_epoch=10_000,
        failure_threshold=3,
        cooldown_seconds=900,
        mode="pixhawk",
    )

    assert actions == ["field_mode_exit"]
    assert HOST_HEALTH.ACTION_COMMANDS["field_mode_exit"] == [
        "systemctl",
        "start",
        "thesis-pixhawk-disconnect.service",
    ]




def test_pixhawk_inspection_requires_carrier_profile_and_no_default_route(
    tmp_path,
):
    def make_runner(carrier):
        def runner(command, *, timeout):
            cmd = list(command)

            if cmd == [
                "nmcli", "-g", "GENERAL.STATE",
                "device", "show", "wlan0",
            ]:
                return subprocess.CompletedProcess(cmd, 0, "100 (connected)\n", "")
            if cmd == [
                "nmcli", "-g", "GENERAL.CONNECTION",
                "device", "show", "wlan0",
            ]:
                return subprocess.CompletedProcess(
                    cmd, 0, "ISR Aero.Next GCS\n", ""
                )
            if cmd == [
                "ip", "route", "show", "default", "dev", "wlan0"
            ]:
                return subprocess.CompletedProcess(
                    cmd, 0, "default via 10.0.0.1 dev wlan0\n", ""
                )
            if cmd == [
                "nmcli", "-g", "connection.interface-name",
                "connection", "show", "pixhawk-apm",
            ]:
                return subprocess.CompletedProcess(cmd, 0, "eth0\n", "")
            if cmd == [
                "nmcli", "-g", "GENERAL.CONNECTION",
                "device", "show", "eth0",
            ]:
                return subprocess.CompletedProcess(cmd, 0, "pixhawk-apm\n", "")
            if cmd == ["cat", "/sys/class/net/eth0/carrier"]:
                return subprocess.CompletedProcess(
                    cmd, 0, f"{carrier}\n", ""
                )
            if cmd == [
                "ip", "route", "show", "default", "dev", "eth0"
            ]:
                return subprocess.CompletedProcess(cmd, 0, "", "")
            if cmd == [
                "systemctl", "is-active", "--quiet",
                "NetworkManager.service",
            ]:
                return subprocess.CompletedProcess(cmd, 0, "", "")
            if cmd == [
                "systemctl", "is-active", "--quiet", "tailscaled.service"
            ]:
                return subprocess.CompletedProcess(cmd, 3, "", "")
            if cmd == [
                "systemctl", "is-active", "--quiet", "ssh.socket"
            ]:
                return subprocess.CompletedProcess(cmd, 0, "", "")
            if cmd == [
                "systemctl", "is-active", "--quiet", "ssh.service"
            ]:
                return subprocess.CompletedProcess(cmd, 3, "", "")

            raise AssertionError(f"unexpected command: {cmd}")

        return runner

    healthy = HOST_HEALTH.inspect_host(
        interface="wlan0",
        mode="pixhawk",
        pixhawk_wifi_connection="ISR Aero.Next GCS",
        pixhawk_ethernet_connection="pixhawk-apm",
        root_path=tmp_path,
        min_free_bytes=1,
        runner=make_runner("1"),
    )
    assert healthy["pixhawk_interface"] == "eth0"
    assert healthy["pixhawk_carrier_present"] is True
    assert healthy["pixhawk_ethernet_active"] is True
    assert healthy["pixhawk_default_route"] is False
    assert healthy["pixhawk_network_valid"] is True
    assert healthy["network_ok"] is True

    unplugged = HOST_HEALTH.inspect_host(
        interface="wlan0",
        mode="pixhawk",
        pixhawk_wifi_connection="ISR Aero.Next GCS",
        pixhawk_ethernet_connection="pixhawk-apm",
        root_path=tmp_path,
        min_free_bytes=1,
        runner=make_runner("0"),
    )
    assert unplugged["pixhawk_carrier_present"] is False
    assert unplugged["pixhawk_network_valid"] is False
    assert unplugged["network_ok"] is False


def test_unattended_mode_rejects_field_wifi_as_maintenance_network(tmp_path):
    def runner(command, *, timeout):
        cmd = list(command)

        if cmd == [
            "nmcli", "-g", "GENERAL.STATE",
            "device", "show", "wlan0",
        ]:
            return subprocess.CompletedProcess(cmd, 0, "100 (connected)\n", "")
        if cmd == [
            "nmcli", "-g", "GENERAL.CONNECTION",
            "device", "show", "wlan0",
        ]:
            return subprocess.CompletedProcess(
                cmd, 0, "ISR Aero.Next GCS\n", ""
            )
        if cmd == [
            "ip", "route", "show", "default", "dev", "wlan0"
        ]:
            return subprocess.CompletedProcess(
                cmd, 0, "default via 10.0.0.1 dev wlan0\n", ""
            )
        if cmd == [
            "nmcli", "-g", "connection.interface-name",
            "connection", "show", "pixhawk-apm",
        ]:
            return subprocess.CompletedProcess(cmd, 0, "eth0\n", "")
        if cmd == [
            "nmcli", "-g", "GENERAL.CONNECTION",
            "device", "show", "eth0",
        ]:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if cmd == ["cat", "/sys/class/net/eth0/carrier"]:
            return subprocess.CompletedProcess(cmd, 0, "0\n", "")
        if cmd == [
            "ip", "route", "show", "default", "dev", "eth0"
        ]:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if cmd == ["ping", "-I", "wlan0", "-c", "1", "-W", "2", "10.0.0.1"]:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if cmd == ["tailscale", "status", "--json"]:
            return subprocess.CompletedProcess(
                cmd,
                0,
                '{"BackendState":"Running","Self":{"Online":true}}\n',
                "",
            )
        if cmd == [
            "systemctl", "is-active", "--quiet",
            "NetworkManager.service",
        ]:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if cmd == [
            "systemctl", "is-active", "--quiet", "tailscaled.service"
        ]:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if cmd == [
            "systemctl", "is-active", "--quiet", "ssh.socket"
        ]:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if cmd == [
            "systemctl", "is-active", "--quiet", "ssh.service"
        ]:
            return subprocess.CompletedProcess(cmd, 3, "", "")

        raise AssertionError(f"unexpected command: {cmd}")

    snapshot = HOST_HEALTH.inspect_host(
        interface="wlan0",
        mode="unattended",
        pixhawk_wifi_connection="ISR Aero.Next GCS",
        pixhawk_ethernet_connection="pixhawk-apm",
        root_path=tmp_path,
        min_free_bytes=1,
        runner=runner,
    )

    assert snapshot["active_wifi_connection"] == "ISR Aero.Next GCS"
    assert snapshot["expected_wifi_active"] is False
    assert snapshot["network_ok"] is False


def test_network_mode_unattended_exit_drops_field_wifi_and_is_serialized():
    mode_script = (
        REPO_ROOT / "tools/host/set_pi_network_mode.sh"
    ).read_text(encoding="utf-8")

    assert 'flock -x 9' in mode_script
    assert "disconnect_active_field_wifi()" in mode_script
    assert "enter_unattended_mode()" in mode_script
    assert mode_script.index("set_mode unattended") < mode_script.index(
        "disconnect_active_field_wifi",
        mode_script.index("enter_unattended_mode()"),
    )
    assert 'nmcli connection down "$PIXHAWK_ETHERNET"' in mode_script
    assert 'nmcli device set "$INTERFACE" autoconnect yes' in mode_script
    assert 'nmcli device connect "$INTERFACE"' not in mode_script


def test_pixhawk_disconnect_dispatcher_can_only_request_unattended_exit():
    dispatcher = (
        REPO_ROOT
        / "tools/host/networkmanager/dispatcher.d"
        / "90-thesis-pixhawk-disconnect"
    ).read_text(encoding="utf-8")

    assert "pre-down|down" in dispatcher
    assert 'THESIS_HOST_MODE:-unattended' in dispatcher
    assert "THESIS_HOST_PIXHAWK_ETHERNET_CONNECTION" in dispatcher
    assert 'connection.interface-name' in dispatcher
    assert "systemctl start --no-block thesis-pixhawk-disconnect.service" in dispatcher
    assert "thesis-network-mode pixhawk" not in dispatcher
    assert "start_live_stack" not in dispatcher.lower()
    assert "mavros" in dispatcher.lower()  # prohibition comment only


def test_pixhawk_disconnect_service_is_host_only_unattended_transition():
    service = (
        SYSTEMD_ASSET_ROOT / "thesis-pixhawk-disconnect.service"
    ).read_text(encoding="utf-8")

    exec_lines = [
        line for line in service.splitlines() if line.startswith("ExecStart=")
    ]
    assert exec_lines == [
        "ExecStart=/usr/local/sbin/thesis-network-mode unattended"
    ]
    assert "THESIS_HOST_SKIP_HEALTH_RECHECK=1" in service
    assert "pixhawk" not in exec_lines[0].split()[-1]
    assert "start_live_stack" not in service
    assert "mavros" not in service.lower()
    assert "control_ref" not in service


def test_installer_deploys_pixhawk_disconnect_guard():
    installer = (
        REPO_ROOT / "tools/host/install_unattended_host_recovery.sh"
    ).read_text(encoding="utf-8")

    assert "thesis-pixhawk-disconnect.service" in installer
    assert "90-thesis-pixhawk-disconnect" in installer
    assert "/etc/NetworkManager/dispatcher.d/" in installer
    assert "flock is required" in installer
