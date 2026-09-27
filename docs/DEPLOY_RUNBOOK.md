# Deployment Runbook — Run the App on the Pi

Day-to-day loop: deploy the app to the Pi, run it, monitor it, stop it. Use the
scripts in `scripts/`; the manual equivalents are at the end for when you need
to do a step by hand.

## Connection details

- Host: `babymonitor.local` (LAN IP `192.168.18.100`), user `babymonitor`
- SSH key: `~/.ssh/id_ed25519_babymonitor`, app dir on Pi: `~/baby-monitor/`
- Default URL: <http://192.168.18.100:8000/>

Config for all scripts lives in `scripts/config.sh` (host, user, key, app dir,
port), overridable via env vars.

Optional `~/.ssh/config` on the Mac for `ssh babymonitor`:

```
Host babymonitor babymonitor.local
    HostName babymonitor.local
    User babymonitor
    IdentityFile ~/.ssh/id_ed25519_babymonitor
    IdentitiesOnly yes
```

## Deploy, run, monitor, stop (scripts)

```bash
# Deploy (Mac -> Pi)
./scripts/deploy.sh              # rsync the repo to the Pi
./scripts/deploy.sh --install    # rsync, then create venv + install deps on the Pi

# Run
./scripts/start.sh               # pre-flight checks (ping, SSH, venv), then start
./scripts/start.sh --restart     # stop any running instance, then start fresh
```

`start.sh` won't double-start: if the app is running it prints the PID(s) and
exits; use `--restart` to replace it. On success it prints the startup log and
the URL.

Monitor and stop (over SSH):

```bash
# Tail the log
ssh -i ~/.ssh/id_ed25519_babymonitor babymonitor@babymonitor.local 'tail -f ~/baby-monitor/server.log'
# Is it running?
ssh -i ~/.ssh/id_ed25519_babymonitor babymonitor@babymonitor.local 'pgrep -af app.main || echo "not running"'
# Stop it
ssh -i ~/.ssh/id_ed25519_babymonitor babymonitor@babymonitor.local 'pkill -f app.main'
```

## Verify it's serving

```bash
curl -s -o /dev/null -w "/ -> %{http_code}\n" http://192.168.18.100:8000/
curl -s http://192.168.18.100:8000/healthz     # -> ok
```

Then open <http://192.168.18.100:8000/> from any device on the same WiFi.

## Configuration (environment variables)

Read by the app; `APP_PORT` in `scripts/config.sh` maps to `BABYMONITOR_PORT`.

- `BABYMONITOR_HOST` — bind address (default `0.0.0.0`)
- `BABYMONITOR_PORT` — port (default `8000`)
- `BABYMONITOR_DEBUG` — `1` to enable Flask debug (default off)

## Verify & lint the code (`make verify`)

The single verification gate (see `AGENTS.md`): lint → format-check → typecheck → test.

```bash
make install   # first time: venv + runtime & dev deps
make verify    # ruff check, ruff format --check, mypy, pytest
```

Other targets: `make lint`, `make format`, `make format-check`, `make typecheck`,
`make test`, `make clean`, `make help`.

macOS `make` note: it comes from the Xcode Command Line Tools. If it errors with
"You have not agreed to the Xcode license agreements", accept the license (open
Xcode and click Agree, or `sudo xcodebuild -license accept`), or run the venv
tools directly (`./.venv/bin/ruff check .`, `./.venv/bin/mypy app`,
`./.venv/bin/pytest`). On the Pi, `make` works out of the box.

## Manual equivalents (when doing a step by hand)

These are the same steps the scripts run.

```bash
# Deploy
rsync -av --exclude '.venv' --exclude '__pycache__' --exclude '.git' \
  --exclude '.idea' --exclude '.DS_Store' \
  -e "ssh -i ~/.ssh/id_ed25519_babymonitor -o StrictHostKeyChecking=accept-new" \
  ./ babymonitor@babymonitor.local:~/baby-monitor/

# First-time env setup (on the Pi)
cd ~/baby-monitor && python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt

# Run in the background (on the Pi)
cd ~/baby-monitor && (nohup ./.venv/bin/python -m app.main > server.log 2>&1 &)

# Run in the foreground (on the Pi)
cd ~/baby-monitor && ./.venv/bin/python -m app.main   # Ctrl+C to stop
```

## Notes

- This uses Flask's development server, started manually. Auto-start on boot
  (systemd) is a later task in [`PLAN.md`](../plans/PLAN.md).
- If SSH warns the host key changed after reflashing the Pi, clear it:
  `ssh-keygen -R babymonitor.local && ssh-keygen -R 192.168.18.100`.
- **Runbook policy:** when a new kind of Pi action is done for the first time
  (new provisioning step, service, hardware setup), document it in a `docs/`
  runbook so it's repeatable.
