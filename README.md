# Baby Monitor (Raspberry Pi)

A local-network baby monitor running on a Raspberry Pi 4. See `PLAN.md` for the
full build plan. This README covers running the current app (Task 2: Flask
skeleton serving a status page).

## Project layout
```
app/
  __init__.py        # Flask app factory (routes: / and /healthz)
  main.py            # dev server entry point (binds 0.0.0.0:8000)
  templates/
    index.html       # Baby Monitor status page
requirements.txt     # pinned dependencies
```

## Run on the Raspberry Pi

The Pi is reachable at `babymonitor.local` (LAN IP `192.168.18.100`).

### 1. Sync the code from the Mac to the Pi
From the repo root on the Mac:
```bash
rsync -av --exclude '.venv' --exclude '__pycache__' --exclude '.git' \
  -e "ssh -i ~/.ssh/id_ed25519_babymonitor" \
  ./ babymonitor@babymonitor.local:~/baby-monitor/
```

### 2. Create a venv and install deps (on the Pi)
```bash
ssh -i ~/.ssh/id_ed25519_babymonitor babymonitor@babymonitor.local
cd ~/baby-monitor
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Run the server (on the Pi)
```bash
python -m app.main
```

### 4. View it
On any device on the same WiFi, open:
```
http://192.168.18.100:8000/
```
You should see the "Baby Monitor" status page. Health check: `http://192.168.18.100:8000/healthz` returns `ok`.

## Configuration (environment variables)
- `BABYMONITOR_HOST` (default `0.0.0.0`)
- `BABYMONITOR_PORT` (default `8000`)
- `BABYMONITOR_DEBUG` (`1` to enable Flask debug; default off)
