#!/usr/bin/env bash
# Shared configuration for the Baby Monitor helper scripts.
# Override any of these via environment variables if your setup differs.

PI_HOST="${PI_HOST:-babymonitor.local}"
PI_USER="${PI_USER:-babymonitor}"
PI_SSH_KEY="${PI_SSH_KEY:-$HOME/.ssh/id_ed25519_babymonitor}"
PI_APP_DIR="${PI_APP_DIR:-baby-monitor}"          # relative to the Pi user's home
APP_PORT="${APP_PORT:-8000}"

# Assembled SSH command used by the scripts.
SSH_OPTS=(-i "$PI_SSH_KEY" -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new)
