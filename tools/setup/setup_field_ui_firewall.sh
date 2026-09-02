#!/usr/bin/env bash

set +u

printf '\n============================================================\n'
printf 'THESIS FIELD UI — ONE-TIME WLAN FIREWALL SETUP\n'
printf '============================================================\n'

if ! command -v ufw >/dev/null 2>&1; then
    printf '[error] ufw is not installed\n' >&2
    exit 1
fi

printf '\nThis allows only the four field-UI TCP services on wlan0:\n'
printf '  5173  frontend\n'
printf '  8080  MJPEG video\n'
printf '  8090  dashboard API\n'
printf '  8765  dashboard WebSocket\n\n'

for PORT in 5173 8080 8090 8765; do
    sudo ufw allow in on wlan0 proto tcp to any port "$PORT" \
        comment "Thesis field UI ${PORT}"
    RC=$?

    if [ "$RC" -ne 0 ]; then
        printf '[error] failed to install wlan0 rule for TCP %s\n' "$PORT" >&2
        exit "$RC"
    fi
done

printf '\n===== RESULTING FIREWALL =====\n'
sudo ufw status numbered

printf '\nPASS: field UI firewall rules installed on wlan0 only\n'
