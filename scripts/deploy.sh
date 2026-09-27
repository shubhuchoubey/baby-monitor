#!/usr/bin/env bash
#
# deploy.sh — sync the app from the Mac to the Pi.
#
# Usage:
#   ./scripts/deploy.sh          # sync code to the Pi
#   ./scripts/deploy.sh --install # sync, then (re)install deps in the Pi venv
#
# Run from anywhere; paths are resolved relative to the repo root.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=scripts/config.sh
source "$SCRIPT_DIR/config.sh"

INSTALL_DEPS=0
[[ "${1:-}" == "--install" ]] && INSTALL_DEPS=1

echo "==> Deploying $REPO_ROOT -> $PI_USER@$PI_HOST:~/$PI_APP_DIR/"

rsync -av \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude '.git' \
  --exclude '.idea' \
  --exclude '.DS_Store' \
  --exclude '.mypy_cache' \
  --exclude '.pytest_cache' \
  --exclude '.ruff_cache' \
  -e "ssh ${SSH_OPTS[*]}" \
  "$REPO_ROOT/" "$PI_USER@$PI_HOST:~/$PI_APP_DIR/"

if [[ "$INSTALL_DEPS" -eq 1 ]]; then
  echo "==> Creating venv (if needed) and installing dependencies on the Pi"
  ssh "${SSH_OPTS[@]}" "$PI_USER@$PI_HOST" \
    "cd ~/$PI_APP_DIR \
     && python3 -m venv .venv \
     && ./.venv/bin/pip install --quiet --upgrade pip \
     && ./.venv/bin/pip install --quiet -r requirements.txt"
  echo "==> Dependencies installed."
fi

echo "==> Deploy complete."
