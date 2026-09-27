#!/usr/bin/env bash
#
# logs.sh — watch the app's log on the Pi live from the Mac.
#
# Reuses scripts/config.sh for connection details, matching deploy.sh/start.sh.
# Reads ~/$PI_APP_DIR/server.log (the same log start.sh writes).
#
# Usage:
#   ./scripts/logs.sh              # follow the live log (tail -f)
#   ./scripts/logs.sh -n N         # print the last N lines, then follow
#   ./scripts/logs.sh --no-follow  # one-shot dump (no follow)
#   ./scripts/logs.sh -h|--help    # this help
#
# Run from anywhere; paths are resolved relative to the repo root.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/config.sh
source "$SCRIPT_DIR/config.sh"

usage() {
  cat <<'EOF'
logs.sh — watch the app's log on the Pi live from the Mac.

Usage:
  ./scripts/logs.sh              # follow the live log (tail -f)
  ./scripts/logs.sh -n N         # print the last N lines, then follow
  ./scripts/logs.sh --no-follow  # one-shot dump (no follow)
  ./scripts/logs.sh -h|--help    # this help
EOF
}

FOLLOW=1
LINES=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    -n)
      [[ $# -ge 2 ]] || { echo "ERROR: -n requires a number" >&2; exit 1; }
      LINES="$2"
      shift 2
      ;;
    --no-follow)
      FOLLOW=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

# Build the remote tail command.
REMOTE_CMD="tail"
[[ -n "$LINES" ]] && REMOTE_CMD+=" -n $LINES"
[[ "$FOLLOW" -eq 1 ]] && REMOTE_CMD+=" -f"
REMOTE_CMD+=" ~/$PI_APP_DIR/server.log"

echo "==> Reading $PI_USER@$PI_HOST:~/$PI_APP_DIR/server.log" >&2
ssh "${SSH_OPTS[@]}" "$PI_USER@$PI_HOST" "$REMOTE_CMD"
