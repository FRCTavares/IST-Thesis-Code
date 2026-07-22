# P0.24 unattended Pi host-recovery validation

Date: 22 July 2026

Issue: [#51](https://github.com/FRCTavares/IST-Thesis-Code/issues/51)

## Status

Implementation and all software-controlled host tests pass. Issue #51 remains
open pending the physical power-removal/restoration test, external-network
reconnection, confirmation of the independent power/watchdog mitigation, and
the physical AERONEXT/Pixhawk mode check.

## Safety boundary

The deployment enables only NetworkManager, Tailscale, the SSH socket, UFW, and
the host-health timer. It does not enable or start ROS, MAVROS, perception,
tracking, TIM, control, arming, recording, or any aircraft-facing service.
Tailscale is required only in unattended mode. Pixhawk mode instead requires
`ISR Aero.Next GCS` on `wlan0`, reserves `eth0` for `pixhawk-apm`, and keeps
Tailscale stopped.

## Audited baseline

- Ubuntu 24.04.4 LTS
- kernel `6.8.0-1060-raspi`
- systemd 255 (`255.4-1ubuntu8.16`)
- Tailscale 1.98.4
- NetworkManager-managed `wlan0`, saved profile set to autoconnect indefinitely
- `tailscaled.service` enabled and active
- `ssh.socket` enabled and active
- Raspberry Pi hardware watchdog available at `/dev/watchdog0`
- ext4 root filesystem: 229 GiB total, 46% used before implementation
- repository bags: 26 GiB; ROS logs: 75 MiB
- no failed systemd units
- no thesis, MAVROS, or control service enabled at boot

Initial gaps:

- hardware watchdog present but not fed by systemd;
- journal used 2.1 GiB with no explicit cap;
- Tailscale/SSH restart delays were 100 ms with small default start limits;
- UFW was inactive while SSH listened on all IPv4/IPv6 interfaces;
- no conservative host-health timer or recorder free-space refusal gate.

The Tailscale node was online, but its key expiry was
`2026-08-23T10:49:07Z`. An unattended interval that crosses that date requires
an admin-console expiry change or renewal before departure.

## Implemented repository contract

- `tools/host/thesis_host_health.py`
  - checks NetworkManager, default route, Tailscale, SSH, and free storage;
  - acts only after consecutive failures and a recovery cooldown;
  - reconnects only the configured NetworkManager interface;
  - restarts Tailscale only when the underlying network is healthy;
  - restarts only `ssh.socket` when SSH is unavailable;
  - emits redacted JSON and never logs credentials or Tailscale peer data.
  - in Pixhawk mode, rejects every Wi-Fi profile except `ISR Aero.Next GCS`,
    requires its default route through `wlan0`, and stops rather than restarts
    Tailscale.
- `tools/host/set_pi_network_mode.sh`
  - switches explicitly between `unattended` and `pixhawk` modes;
  - proves AERONEXT Wi-Fi is active before persisting field mode or stopping
    Tailscale;
  - activates `pixhawk-apm` with IPv4/IPv6 default routes disabled;
  - fails before changing mode if either required NetworkManager profile is
    absent or AERONEXT cannot connect.
- `tools/host/install_unattended_host_recovery.sh`
  - validates and backs up system files before installation;
  - installs the host-only systemd, watchdog, journal, and firewall contract;
  - never enables an aircraft-facing service.
- `tools/host/systemd/`
  - two-minute persistent health timer;
  - Tailscale 10-second restart with bounded start limits;
  - SSH 5-second restart with bounded start limits;
  - 30-second hardware-watchdog feed and 10-minute shutdown watchdog;
  - persistent journal capped at 1 GiB and 30 days.
- `tools/lib/live_storage.sh`
  - refuses video or dataset recording below 20 GiB free;
  - does not delete or rotate any bag.
- `docs/debug/UNATTENDED_PI_OPERATION.md`
  - complete pre-departure, remote-operation, recovery, power, failure, and
    rollback runbook.

Installed-system backup:

Latest: `/var/backups/thesis-host-recovery/20260722T174731Z`

## Automated validation

```text
focused host/network tests: 11 passed
complete tools suite in sourced ROS environment: 79 passed
bash syntax: passed
Python byte compilation: passed
systemd-analyze verify: passed
installer dry-run: passed
git diff --check: passed
```

The simulated disk-pressure test reported `disk_ok=false`, and the live recorder
guard returned 1 with `recording refused` below the 20 GiB threshold. No real
disk space was consumed.

## Installed service validation

After installation:

- NetworkManager, `tailscaled.service`, `ssh.socket`, and
  `thesis-host-health.timer` were enabled and active;
- the health service completed with status 0 and all checks healthy;
- Tailscale restart policy: `Restart=always`, `RestartSec=10s`, 10 starts per
  five-minute limit window;
- SSH restart policy: `Restart=on-failure`, `RestartSec=5s`, 10 starts per
  five-minute limit window;
- journald storage fell from 2.1 GiB to approximately 1.0 GiB;
- UFW became active with default-deny inbound, Tailnet service access only on
  `tailscale0`, UDP 41641 allowed on `wlan0` for direct Tailscale transport, and
  Pixhawk MAVLink UDP 14550 allowed only on `eth0`;
- a new key-based SSH connection through the Tailscale address passed after the
  firewall change;
- `tailscale serve status` reported no public serve configuration;
- no thesis or aircraft service appeared in enabled system service units.

## Controlled recovery tests

### Tailscale process termination

- action: killed only the `tailscaled.service` main process with SIGKILL;
- observed: systemd recorded exit at 18:10:36 and scheduled restart at 18:10:47;
- recovery: `NRestarts=1`, backend `Running`, node online, SSH reachable;
- result: PASS.

### SSH listener termination

- action: killed only the `ssh.service` main listener with SIGKILL;
- observed: exit at 18:11:58 and scheduled restart at 18:12:03;
- recovery: `NRestarts=1`, `ssh.socket` and `ssh.service` active, a new key-based
  SSH connection passed;
- result: PASS.

### Normal reboot and watchdog activation

- pre-reboot epoch: `1784740360`;
- first successful Tailscale SSH epoch: `1784740407`;
- remote recovery time: 47 seconds;
- NetworkManager, Tailscale, SSH socket, and health timer all active after boot;
- systemd reported `RuntimeWatchdogUSec=30s` and
  `RebootWatchdogUSec=10min`;
- boot journal confirmed systemd was feeding the Broadcom BCM2835 watchdog with
  a 30-second timeout;
- previous-boot journal remained readable;
- result: PASS.

### Wi-Fi device loss

- safety: a three-minute independent reconnect fallback was scheduled first;
- action: disconnected `wlan0` through NetworkManager;
- test thresholds: one failure and 60-second cooldown, restored afterward to
  three failures and 900 seconds;
- health action: `network_reconnect=0`, followed by `tailscale_restart=0` while
  the overlay network recovered;
- Tailscale SSH reachable again after 28 seconds;
- independent fallback cancelled;
- result: PASS.

### Default internet-route loss

- safety: a three-minute independent route fallback was scheduled first;
- action: removed only the default route through `wlan0`;
- health action: `network_reconnect=0`;
- DHCP default route restored after 42 seconds and Tailscale returned to
  `Running`;
- production thresholds restored and fallback cancelled;
- result: PASS.

### Health-check service failure

- action: replaced only the installed monitor payload with an invalid temporary
  payload under a trap-protected backup;
- injected invocation: failed with status 1 as expected;
- payload restored immediately, failed state reset, next invocation status 0;
- final service result: success;
- result: PASS.

### Pixhawk field-mode policy dry-run

- installed mode before test: `unattended`, home Wi-Fi active, Tailscale active;
- non-mutating invocation: Pixhawk mode, one-failure threshold, dry-run;
- observed: the home Wi-Fi profile was rejected (`expected_wifi_active=false`)
  even though the interface and a default route were present;
- selected recovery actions: exact AERONEXT connection recovery and
  `tailscale_stop`; no action was executed in the dry-run;
- live-stack field and source paths now invoke the fail-closed mode switch
  instead of activating `pixhawk-apm` directly;
- result: SOFTWARE POLICY PASS; physical link/profile check remains open.

## Diagnostics and cleanliness

- recent previous-boot journal is available;
- journal growth is bounded to 1 GiB/30 days with 10 GiB kept free;
- root free space remained approximately 120 GiB;
- repository-root `log/`, `hailort.log`, and `.pytest_cache` were removed or
  absent after validation;
- no credentials, SSH keys, Wi-Fi secrets, Tailscale keys, or Tailscale state
  were added to the repository.

## Remaining physical/external gates

Do not close Issue #51 until all of these are recorded:

1. storage-safe poweroff, physical power removal, restoration, and automatic
   Tailscale/SSH recovery;
2. a fresh Tailscale SSH connection while the operator computer is outside the
   home network (for example, on a phone hotspot);
3. confirmation that a tested smart plug or UPS is available, or a locally
   supervised destructive watchdog-recovery test with the runbook safeguards;
4. confirmation that the unattended interval ends before 23 August 2026, or
   that Tailscale key expiry was extended/disabled for this node;
5. with the Pixhawk connected to `eth0`, locally confirm `pixhawk-apm` is active,
   `ISR Aero.Next GCS` is the active `wlan0` profile and default route, and
   `tailscaled.service` is disabled/inactive.
