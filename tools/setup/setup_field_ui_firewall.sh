#!/usr/bin/env bash

set +u

printf '\n============================================================\n'
printf 'THESIS FIELD UI — ONE-TIME WLAN FIREWALL SETUP\n'
printf '============================================================\n'

if ! command -v ufw >/dev/null 2>&1; then
    printf '[error] ufw is not installed\n' >&2
    exit 1
fi

FIELD_OPERATOR_SSH_CIDR="${FIELD_OPERATOR_SSH_CIDR:-192.168.8.0/24}"

printf '\nThis allows the field operator services on wlan0:\n'
printf '  22    SSH from approved GCS subnet %s only\n' "$FIELD_OPERATOR_SSH_CIDR"
printf '  5173  frontend\n'
printf '  8080  MJPEG video\n'
printf '  8090  dashboard API\n'
printf '  8765  dashboard WebSocket\n\n'

sudo ufw allow in on wlan0 \
    from "$FIELD_OPERATOR_SSH_CIDR" \
    proto tcp to any port 22 \
    comment "Thesis field operator SSH"
RC=$?

if [ "$RC" -ne 0 ]; then
    printf '[error] failed to install wlan0 SSH rule for %s\n' \
        "$FIELD_OPERATOR_SSH_CIDR" >&2
    exit "$RC"
fi

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

printf '\nPASS: field operator firewall rules installed on wlan0 only\n'
printf 'SSH source restriction: %s\n' "$FIELD_OPERATOR_SSH_CIDR"
