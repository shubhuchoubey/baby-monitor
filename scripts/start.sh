#!/usr/bin/env bash
#
# start.sh — check the Pi is reachable, then start the app in the background.
#
# Checks performed before starting:
#   1. Pi responds to ping
#   2. SSH connects with the key
#   3. App directory and venv exist on the Pi
# If the app is already running it is left as-is (use --restart to replace it).
#
# Usage:
#   ./scripts/start.sh            # check + start if not already running
#   ./scripts/start.sh --restart  # stop any running instance, then start fresh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/config.sh
source "$SCRIPT_DIR/config.sh"

RESTART=0
[[ "${1:-}" == "--restart" ]] && RESTART=1

fail() { echo "ERROR: $*" >&2; exit 1; }

echo "==> [1/4] Pinging $PI_HOST"
ping -c 2 "$PI_HOST" >/dev/null 2>&1 || fail "$PI_HOST is not reachable (ping failed)."
echo "    reachable."

echo "==> [2/4] Checking SSH"
ssh "${SSH_OPTS[@]}" "$PI_USER@$PI_HOST" 'true' 2>/dev/null \
  || fail "SSH to $PI_USER@$PI_HOST failed (check key: $PI_SSH_KEY)."
echo "    SSH OK."

echo "==> [3/4] Checking app directory and venv"
ssh "${SSH_OPTS[@]}" "$PI_USER@$PI_HOST" \
  "test -d ~/$PI_APP_DIR && test -x ~/$PI_APP_DIR/.venv/bin/python" \
  || fail "App dir or venv missing on the Pi. Run: ./scripts/deploy.sh --install"
echo "    present."

echo "==> [4/4] Starting the app"
ssh "${SSH_OPTS[@]}" "$PI_USER@$PI_HOST" "BABYMONITOR_PORT='$APP_PORT' RESTART='$RESTART' bash -s" <<'REMOTE'
set -euo pipefail
cd ~/baby-monitor

if pgrep -f 'app.main' >/dev/null 2>&1; then
  if [[ "${RESTART:-0}" -eq 1 ]]; then
    echo "    restart requested: stopping existing instance"
    pkill -f 'app.main' || true
    sleep 1
  else
    echo "    already running (use --restart to replace). PID(s): $(pgrep -f app.main | tr '\n' ' ')"
    exit 0
  fi
fi

BABYMONITOR_PORT="${BABYMONITOR_PORT:-8000}" \
  nohup ./.venv/bin/python -m app.main > ~/baby-monitor/server.log 2>&1 &
sleep 3
echo "    --- server.log ---"
tail -n 8 ~/baby-monitor/server.log
REMOTE

echo "==> App should be live at http://$PI_HOST:$APP_PORT/  (LAN IP works too)"
