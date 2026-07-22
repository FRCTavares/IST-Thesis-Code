#!/usr/bin/env bash

# Resolve the closest existing parent without creating recording directories.
recording_storage_probe_path() {
    local path="$1"
    while [[ ! -e "$path" && "$path" != "/" ]]; do
        path="$(dirname "$path")"
    done
    printf '%s\n' "$path"
}

ensure_recording_storage_available() {
    local output_root="$1"
    local minimum_free_gib="$2"
    local probe_path available_kib required_kib

    if ! [[ "$minimum_free_gib" =~ ^[1-9][0-9]*$ ]]; then
        echo "[error] RECORDING_MIN_FREE_GIB must be a positive integer"
        return 2
    fi

    probe_path="$(recording_storage_probe_path "$output_root")"
    available_kib="$(df -Pk -- "$probe_path" | awk 'NR == 2 {print $4}')"
    if ! [[ "$available_kib" =~ ^[0-9]+$ ]]; then
        echo "[error] could not determine free space for $output_root"
        return 1
    fi

    required_kib=$((minimum_free_gib * 1024 * 1024))
    if (( available_kib < required_kib )); then
        echo "[error] recording refused: less than ${minimum_free_gib} GiB free for $output_root"
        echo "[hint] preserve/copy required evidence, then remove only explicitly disposable runs"
        return 1
    fi

    return 0
}
