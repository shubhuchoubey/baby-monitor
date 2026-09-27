# Raspberry Pi Flash & Setup — Task 1

Configuration used to flash and headlessly configure the Raspberry Pi 4 Model B (2GB)
for the baby monitor POC, via **Raspberry Pi Imager (macOS)**.

> Secrets (passwords, WiFi key) are intentionally redacted in this document. Do not commit
> real credentials to source control.

## OS Image
- **Raspberry Pi OS (64-bit)** — Lite is sufficient for a headless monitor.

## OS Customisation Settings

| Setting | Value |
|---|---|
| Hostname | `babymonitor` (reachable as `babymonitor.local`) |
| Username | `babymonitor` |
| Password | _redacted — use a strong passphrase, not a simple one_ |
| Locale / capital city | London |
| Timezone | `Europe/London` |
| Keyboard layout | `gb` |
| WiFi SSID | `NOKIA-9611` |
| WiFi password | _redacted_ |
| WiFi country | GB |

## SSH Configuration
- **Authentication:** Public-key only ("Allow public-key authentication only").
- **Key type:** ed25519, generated on the macOS dev machine:
  ```bash
  ssh-keygen -t ed25519 -C "babymonitor pi - <your_email>"
  ```
- The **public key** (`id_ed25519.pub` / your named key `.pub`) was pasted into the
  Imager's SSH public key field.
- The **private key** stays on the Mac and is never shared.

## First Connection (after boot)
```bash
# Default key location
ssh babymonitor@babymonitor.local

# If you used a dedicated key file (e.g. ~/.ssh/babymonitor)
ssh -i ~/.ssh/babymonitor babymonitor@babymonitor.local
```

## Post-boot Baseline Setup (run on the Pi)
```bash
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y python3 python3-pip python3-venv git
```

## Task 1 Verification Checklist
- [ ] SD card flashed with Raspberry Pi OS (64-bit) via Imager.
- [ ] OS customisation applied (hostname, locale, timezone, keyboard, WiFi).
- [ ] SSH public-key authentication enabled; key generated and pasted into Imager.
- [ ] Pi boots and joins WiFi (`NOKIA-9611`).
- [ ] `ping babymonitor.local` succeeds from the Mac.
- [ ] `ssh babymonitor@babymonitor.local` connects using the key.
- [ ] Internet reachable from the Pi (e.g. `ping -c3 raspberrypi.com`).
- [ ] `python3 --version` reports Python 3.
- [ ] Pi's LAN IP noted for later tasks: `__________`

## Notes
- WiFi credentials are stored on the SD card boot partition by the Imager (normal for
  headless setup).
- Prefer a strong device password even on a local network, since this device has a
  camera and microphone.
