"""Static safety and behavior contract for the macOS field connector."""

from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools/mac/thesis_field_connect.sh"
SOURCE = SCRIPT.read_text(encoding="utf-8")


def test_shell_syntax_and_fixed_identity_contract():
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True)
    assert 'PI_ADDRESS="192.168.8.174"' in SOURCE
    assert 'PI_USER="francisco"' in SOURCE
    assert 'PI_HOSTNAME="fcstpi"' in SOURCE
    assert 'REMOTE_REPOSITORY="/home/francisco/Desktop/Thesis-Code"' in SOURCE


def test_helper_never_changes_network_or_uses_privilege():
    forbidden = (
        "sudo",
        "networksetup -set",
        "ifconfig",
        "route add",
        "route delete",
        "nmcli",
        "systemctl",
        "tailscale up",
        "tailscale down",
    )
    for token in forbidden:
        assert token not in SOURCE.lower()


def test_wifi_interface_is_discovered_and_route_is_fail_closed():
    assert "networksetup -listallhardwareports" in SOURCE
    assert 'ipconfig getifaddr "$WIFI_INTERFACE"' in SOURCE
    assert 'route -n get "$PI_ADDRESS"' in SOURCE
    assert '"$route_interface" == "$WIFI_INTERFACE"' in SOURCE
    assert '"$route_flags" != *GATEWAY*' in SOURCE
    assert "100\\.[0-9]+" in SOURCE


def test_check_mode_does_not_open_interactive_ssh():
    assert "--check) CHECK_ONLY=1" in SOURCE
    success = SOURCE.split("if [[ \"$FAILURES\" -ne 0 ]]", 1)[1]
    assert 'if [[ "$CHECK_ONLY" -eq 1 ]]; then' in success
    assert success.index('if [[ "$CHECK_ONLY" -eq 1 ]]') < success.index("open_remote_shell")


def test_normal_mode_opens_only_after_checks_pass_and_prints_handoff():
    main = SOURCE.split("main() {", 1)[1]
    assert main.index("run_checks") < main.index('MAC/GCS LINK: READY')
    assert main.index('MAC/GCS LINK: READY') < main.index("open_remote_shell")
    assert "tools/flight/field_preflight_check.sh" in SOURCE
    assert "tools/flight/field_preflight_check.sh --passive-live-gate" in SOURCE
    assert "export GIT_PAGER=cat" in SOURCE
    assert "export GH_PAGER=cat" in SOURCE


def test_passwordless_probe_and_interactive_commands_are_distinct():
    assert "-o BatchMode=yes -o ConnectTimeout=5 -o ConnectionAttempts=1" in SOURCE
    assert "exec ssh -t -o BatchMode=yes" in SOURCE
    check_function = SOURCE.split("check_ssh_identity() {", 1)[1].split("run_checks() {", 1)[0]
    assert "ssh -t" not in check_function
