# Unattended Raspberry Pi Operation Runbook

## Scope and safety boundary

This runbook keeps the thesis Raspberry Pi reachable through Tailscale and SSH.

This mode is only for unattended/bench recovery. When Ethernet is connected to
the Pixhawk 6, switch to the mandatory field mode before starting MAVROS:

    sudo ./tools/host/set_pi_network_mode.sh pixhawk

Field mode requires the `ISR Aero.Next GCS` Wi-Fi profile, uses `eth0` only for
the Pixhawk, and stops/disables Tailscale. Restore this unattended mode after
the Pixhawk is disconnected with:

    sudo ./tools/host/set_pi_network_mode.sh unattended

It does not start the thesis live stack, ROS, MAVROS, control, arming, or any
aircraft-facing service. Host availability and aircraft operation are separate
authority domains.

Remote access remains inside Tailscale. Do not add router port forwarding, a
public SSH listener, Tailscale Funnel, or public dashboard/API exposure.

## Tested host baseline

Baseline captured on 22 July 2026:

- host: Raspberry Pi 5, hostname `fcstpi`
- OS: Ubuntu 24.04.4 LTS (Noble)
- kernel: `6.8.0-1060-raspi`
- systemd: 255 (`255.4-1ubuntu8.16`)
- Tailscale: 1.98.4
- network manager: NetworkManager with autoconnecting `wlan0`
- remote shell: OpenSSH through enabled `ssh.socket`
- watchdog: Raspberry Pi hardware watchdog at `/dev/watchdog0`
- root filesystem: ext4 on `/dev/mmcblk0p2`

The Tailscale node key expiry must be checked immediately before departure. The
22 July audit reported 23 August 2026. Extend or disable key expiry for this node
in the Tailscale admin console if the unattended interval could cross that date.
Never commit a Tailscale auth key or state file.

## Installed host-recovery contract

Install from the repository:

```bash
cd /home/francisco/Desktop/Thesis-Code
sudo ./tools/host/install_unattended_host_recovery.sh --interface wlan0
```

The installer:

- enables NetworkManager, `tailscaled.service`, and `ssh.socket` at boot;
- enables UFW with default-deny inbound, allows services only through
  `tailscale0`, and permits UDP 41641 on Wi-Fi for direct Tailscale transport;
- gives SSH and Tailscale bounded systemd restart policies;
- runs `thesis-host-health.service` from a two-minute persistent timer;
- reconnects only the configured NetworkManager device after three consecutive
  failures and enforces a 15-minute recovery cooldown;
- restarts Tailscale only when the underlying network is healthy;
- restarts the SSH socket only when both socket and service are unavailable;
- warns when root free space falls below 20 GiB, without deleting evidence;
- caps persistent journal storage at 1 GiB while retaining up to 30 days;
- configures systemd to feed the hardware watchdog every 30 seconds after the
  next reboot.

Existing files are backed up below `/var/backups/thesis-host-recovery/` before
replacement. No thesis, ROS, MAVROS, perception, or control service is enabled.

## Pre-departure checklist

Run while another person can still access the Pi physically:

```bash
systemctl is-enabled NetworkManager.service tailscaled.service ssh.socket
systemctl is-enabled thesis-host-health.timer
systemctl is-active NetworkManager.service tailscaled.service ssh.socket
systemctl is-active thesis-host-health.timer
systemctl --failed --no-pager

tailscale status
tailscale status --json | jq '.Self | {HostName, Online, KeyExpiry}'

ip -brief address show wlan0
ip route show default
nmcli -g GENERAL.STATE,GENERAL.CONNECTION device show wlan0

systemctl show systemd -p RuntimeWatchdogUSec -p RebootWatchdogUSec
sudo wdctl /dev/watchdog0

df -h /
df -ih /
journalctl --disk-usage
du -sh /home/francisco/Desktop/Thesis-Code/bags
du -sh /home/francisco/Desktop/Thesis-Code/ros2_ws/log
```

Verify all of the following:

- key-based SSH works from the remote computer;
- the Tailscale key remains valid beyond the return date;
- the root filesystem has at least 20 GiB free;
- no recording or live stack is left running;
- `log/`, `hailort.log`, and `.pytest_cache` do not exist at repository root;
- no router port forwarding exposes TCP 22, 8080, 8090, 8765, or 5173;
- the smart plug or UPS control path works from a different network;
- another person knows where the Pi and power supply are.

## Normal remote connection

```bash
tailscale ping fcstpi
ssh francisco@fcstpi
```

The stable Tailscale IP may be used when MagicDNS is unavailable. Do not fall
back to a public router address.

## Routine service inspection

```bash
systemctl status \
  NetworkManager.service \
  tailscaled.service \
  ssh.socket \
  thesis-host-health.timer \
  thesis-host-health.service \
  --no-pager

journalctl -u thesis-host-health.service --since today --no-pager
journalctl -u tailscaled.service --since today --no-pager
systemctl --failed --no-pager
```

Health-check output is one redacted JSON object. It contains only service,
network, disk, counter, and action state; it does not log peer identities,
credentials, Wi-Fi configuration, or Tailscale keys.

## Normal remote reboot

Before reboot:

```bash
cd /home/francisco/Desktop/Thesis-Code
pgrep -af 'start_live_stack|perception_camera_node|tracker_node|control_ref_node|mavros'
sync
sudo systemctl reboot
```

If the process check returns anything, stop the stack from its interactive
prompt before rebooting. Do not reboot while a bag recorder is still writing.

Wait two to five minutes, then reconnect through Tailscale. If the node is not
back after ten minutes, use the external power path once. Do not power-cycle
repeatedly because that increases filesystem-corruption risk.

## Tailscale recovery

If LAN or physical-console access is available:

```bash
systemctl status tailscaled.service --no-pager
journalctl -u tailscaled.service -b -n 200 --no-pager
sudo systemctl restart tailscaled.service
tailscale status
```

Do not run `tailscale up --reset` unattended. It can discard required settings
or require new authentication. If the node key expired, renew it through the
Tailscale admin console or with a person physically present.

## SSH recovery

From a physical console or another already-open shell:

```bash
sudo sshd -t
systemctl status ssh.socket ssh.service --no-pager
sudo systemctl restart ssh.socket
```

Do not change authentication or firewall rules until a second working session
has verified the replacement path.

## Network recovery

Inspect without exposing saved Wi-Fi credentials:

```bash
nmcli -t -f NAME,TYPE,AUTOCONNECT,DEVICE connection show
nmcli -g GENERAL.STATE,GENERAL.CONNECTION device show wlan0
ip route show default
journalctl -u NetworkManager.service -b -n 200 --no-pager
```

Conservative reconnect:

```bash
sudo nmcli device connect wlan0
```

The automatic health check uses this same action only after three failed checks
and then waits at least 15 minutes before another attempt. It does not restart
the whole host or loop rapidly while the router is unavailable.

## Disk and log inspection

```bash
df -h /
df -ih /
sudo journalctl --disk-usage
du -sh /home/francisco/Desktop/Thesis-Code/{bags,ros2_ws/log,reports}
find /home/francisco/Desktop/Thesis-Code/bags -mindepth 1 -maxdepth 2 \
  -type d -printf '%TY-%Tm-%Td %p\n' | sort
```

Never automatically delete reference, source, raw-image, ground-truth, or
promoted evidence bags. Stop new recording before storage becomes critical,
copy retained evidence elsewhere, verify the copy, and only then remove an
explicitly selected disposable run.

The host monitor warns below 20 GiB free. Because no thesis runtime starts
automatically, bags cannot grow while the Pi is merely left powered and idle.

## Crash and previous-boot inspection

```bash
journalctl --list-boots
journalctl -b -1 -p warning..alert --no-pager
journalctl -k -b -1 --no-pager
last -x reboot shutdown | head -20
systemctl --failed --no-pager
```

Persistent journal storage is capped at 1 GiB and 30 days. This bounds growth
while retaining recent previous-boot diagnostics.

## Watchdog validation

After a controlled reboot, verify that PID 1 is feeding the watchdog:

```bash
systemctl show systemd -p RuntimeWatchdogUSec -p RebootWatchdogUSec
sudo wdctl /dev/watchdog0
journalctl -b | rg -i watchdog
```

Do not use SysRq crash, kill PID 1, fork bombs, or I/O starvation as remote
tests. A destructive simulated kernel hang is accepted only with a local
operator, a verified backup, cleanly stopped recording, `sync`, and a working
smart plug or UPS. When those safeguards are unavailable, record the limitation
and validate the independent power-control path instead.

## Power loss and restoration

The Pi boots when input power returns; no aircraft service is enabled at boot.
For a storage-safe power-restoration test:

1. stop all recording and live-stack processes;
2. run `sync` and `sudo systemctl poweroff`;
3. wait until activity LEDs stop;
4. remove input power;
5. restore power once;
6. verify Tailscale and SSH recovery from a different network;
7. inspect `journalctl --list-boots` and filesystem state.

Use a reputable UPS or remotely controlled smart plug. A UPS reduces unsafe
power cuts; a smart plug recovers from software states where normal SSH is gone.
Do not connect aircraft propulsion power for unattended host testing.

## Emergency shutdown

```bash
sync
sudo systemctl poweroff
```

If the host is unreachable, use the smart plug only after allowing time for any
possible write activity to finish. Physical power removal is the final option.

## Failure ownership matrix

| Failure | Automatic recovery | External/physical requirement |
| --- | --- | --- |
| `tailscaled` crash | systemd restart; health-check fallback | none if network is healthy |
| SSH daemon crash | socket activation; health-check fallback | physical/LAN shell if configuration is invalid |
| Wi-Fi disconnect | NetworkManager autoconnect; bounded device reconnect | router intervention if AP remains unavailable |
| Internet outage | services wait; reconnect after upstream returns | ISP/router recovery |
| Ordinary userspace stall | affected service restart | operator diagnosis |
| Kernel hang | hardware watchdog after configuration/reboot | smart plug or UPS if watchdog cannot recover |
| Complete power loss | boots when power returns | external power restoration |
| SD-card corruption | none | physical repair, restore, or replacement |
| Power-supply failure | none | physical replacement |
| Router failure | none on Pi | router power/control or physical access |
| Expired Tailscale key | none | admin-console renewal or physical access |

## Rollback

The installer prints its backup directory. To disable the new monitor without
affecting SSH or Tailscale:

```bash
sudo systemctl disable --now thesis-host-health.timer
```

To fully roll back, restore the matching files from the printed directory below
`/var/backups/thesis-host-recovery/<timestamp>/`, then run:

```bash
sudo systemctl daemon-reload
sudo systemctl restart systemd-journald.service
sudo systemctl reboot
```

Keep `ssh.socket` and `tailscaled.service` enabled until remote access has been
verified after rollback.
