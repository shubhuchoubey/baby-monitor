# Deployment Runbook — Run the App on the Pi

How to transfer the app from the Mac to the Raspberry Pi, run it, monitor it,
and stop it. This is the day-to-day dev loop used throughout the project.

## Quick start (helper scripts)

Two scripts in `scripts/` wrap the common flow. They share `scripts/config.sh`
(host, user, SSH key, app dir, port — all overridable via env vars).

```bash
./scripts/deploy.sh              # rsync the repo to the Pi
./scripts/deploy.sh --install    # rsync, then create venv + install deps on the Pi
./scripts/start.sh               # pre-flight checks (ping, SSH, venv), then start
./scripts/start.sh --restart     # stop any running instance, then start fresh
```

`start.sh` refuses to double-start: if the app is already running it reports the
PID(s) and exits; use `--restart` to replace it. The manual commands below are
the same steps the scripts run, for when you need to do something by hand.

## Connection details

- Host: `babymonitor.local` (LAN IP `192.168.18.100`)
- User: `babymonitor`
- SSH key: `~/.ssh/id_ed25519_babymonitor`
- App directory on the Pi: `~/baby-monitor/`
- Default URL: <http://192.168.18.100:8000/>

Optional — add to `~/.ssh/config` on the Mac to connect with just `ssh babymonitor`:

```
Host babymonitor babymonitor.local
    HostName babymonitor.local
    User babymonitor
    IdentityFile ~/.ssh/id_ed25519_babymonitor
    IdentitiesOnly yes
```

## 1. Transfer the code (Mac → Pi)

Run from the repo root on the Mac. Re-run any time you change code locally.

```bash
rsync -av \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude '.git' \
  --exclude '.idea' \
  --exclude '.DS_Store' \
  -e "ssh -i ~/.ssh/id_ed25519_babymonitor -o StrictHostKeyChecking=accept-new" \
  ./ babymonitor@babymonitor.local:~/baby-monitor/
```

## 2. Set up the environment (on the Pi, first time only)

```bash
ssh -i ~/.ssh/id_ed25519_babymonitor babymonitor@babymonitor.local
cd ~/baby-monitor
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Re-run `pip install -r requirements.txt` whenever dependencies change.

## 3. Run the app

### Foreground (interactive; Ctrl+C to stop)

```bash
ssh -i ~/.ssh/id_ed25519_babymonitor babymonitor@babymonitor.local
cd ~/baby-monitor
source .venv/bin/activate
python -m app.main
```

### Background (keeps running after you disconnect)

```bash
ssh -i ~/.ssh/id_ed25519_babymonitor babymonitor@babymonitor.local \
  'cd ~/baby-monitor \
   && (nohup ./.venv/bin/python -m app.main > ~/baby-monitor/server.log 2>&1 &) \
   && sleep 3 && cat ~/baby-monitor/server.log'
```

Expected startup log:

```
 * Serving Flask app 'app'
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:8000
 * Running on http://192.168.18.100:8000
```

### Configuration (environment variables)

```bash
BABYMONITOR_HOST=0.0.0.0   # bind address (default 0.0.0.0)
BABYMONITOR_PORT=8000      # port (default 8000)
BABYMONITOR_DEBUG=1        # enable Flask debug (default off)
```

Example:

```bash
BABYMONITOR_PORT=9000 ./.venv/bin/python -m app.main
```

## 4. Verify it's serving

From the Pi (localhost):

```bash
ssh -i ~/.ssh/id_ed25519_babymonitor babymonitor@babymonitor.local \
  'curl -s -o /dev/null -w "/ -> %{http_code}\n" http://127.0.0.1:8000/ \
   && curl -s http://127.0.0.1:8000/healthz'
```

From the Mac (across the LAN):

```bash
curl -s -o /dev/null -w "/ -> %{http_code}\n" http://192.168.18.100:8000/
curl -s http://192.168.18.100:8000/healthz
```

`/healthz` returns `ok` (HTTP 200) when the server is healthy. Then open
<http://192.168.18.100:8000/> from any device on the same WiFi.

## 5. Monitor

```bash
# Tail the log live
ssh -i ~/.ssh/id_ed25519_babymonitor babymonitor@babymonitor.local \
  'tail -f ~/baby-monitor/server.log'

# Check whether the app process is running
ssh -i ~/.ssh/id_ed25519_babymonitor babymonitor@babymonitor.local \
  'pgrep -af app.main || echo "not running"'

# See what is listening on the port
ssh -i ~/.ssh/id_ed25519_babymonitor babymonitor@babymonitor.local \
  'ss -ltnp | grep :8000 || echo "nothing on :8000"'
```

## 6. Stop / kill

```bash
# Graceful stop of the background server
ssh -i ~/.ssh/id_ed25519_babymonitor babymonitor@babymonitor.local \
  'pkill -f app.main && echo "stopped" || echo "was not running"'

# Force kill if it does not stop
ssh -i ~/.ssh/id_ed25519_babymonitor babymonitor@babymonitor.local \
  'pkill -9 -f app.main'
```

For a foreground run, press `Ctrl+C` in the SSH session instead.

## Verify & lint the code

`make verify` is the single verification gate (see `AGENTS.md`). Run it from the
repo root after changes. It runs, in order: lint → format-check → typecheck → test.

```bash
make install       # first time: create venv + install runtime & dev deps
make verify        # full gate: ruff check, ruff format --check, mypy, pytest
```

Individual targets:

```bash
make lint          # ruff check .
make format        # ruff format .            (auto-fix formatting)
make format-check  # ruff format --check .    (check only, no changes)
make typecheck     # mypy app
make test          # pytest
make clean         # remove venv + caches
make help          # list all targets
```

Notes on `make`:

- On the **Pi**, `make` is GNU make and works out of the box.
- On **macOS**, `make` comes from the Xcode Command Line Tools. If it errors with
  "You have not agreed to the Xcode license agreements", accept the license
  (open the Xcode app and click Agree, or run `sudo xcodebuild -license accept`).
  Alternatively run the underlying tools directly from the venv, e.g.
  `./.venv/bin/ruff check .`, `./.venv/bin/mypy app`, `./.venv/bin/pytest`.

## Notes

- This uses Flask's development server, started manually. Automatic start on
  boot (systemd) is covered separately in `PLAN.md`.
- If SSH warns that the host key changed after reflashing the Pi, clear the old
  entry: `ssh-keygen -R babymonitor.local && ssh-keygen -R 192.168.18.100`.
- **Runbook policy:** whenever a new kind of Pi action is performed for the first
  time (a new provisioning step, service, hardware setup, etc.), document it in a
  runbook under `docs/` so it is repeatable.
