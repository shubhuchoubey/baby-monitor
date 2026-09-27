# Runbook — Detect & Validate the Camera + Mic

Confirm the USB webcam and microphone are seen by the Pi and can capture. Run
after plugging in the camera, changing USB ports, or swapping the device.

## Confirmed device facts (Logitech Brio on this Pi)

| Property             | Value                                   |
| -------------------- | --------------------------------------- |
| Camera capture node  | `/dev/video0`                           |
| Camera formats       | YUYV 4:2:2 and MJPEG (up to 4K)         |
| Recommended stream   | **1280x720 MJPEG** (efficient on Pi 4)  |
| Mic ALSA id          | `plughw:3,0` (card 3, device 0)         |
| Mic capture format    | 48000 Hz, 16-bit, stereo               |
| Driver               | Standard UVC + USB Audio (no vendor SW) |

## The command that matters

Deploy first (`./scripts/deploy.sh`), then on the Pi:

```bash
cd ~/baby-monitor && ./.venv/bin/python -m app.detection
```

Detects the camera + mic, captures a test frame and 1s audio clip, and prints
`Result : OK` (exit 0) when both are found. Options:

```bash
./.venv/bin/python -m app.detection --no-capture      # detection only (read-only)
./.venv/bin/python -m app.detection --name-hint C920  # match a different webcam
./.venv/bin/python -m app.detection --out-dir /tmp    # where samples are written
```

To eyeball the captured frame, copy it back to the Mac:

```bash
scp -i ~/.ssh/id_ed25519_babymonitor babymonitor@babymonitor.local:/tmp/brio_test.jpg /tmp/
```

## Manual fallback (raw tools, no app)

```bash
v4l2-ctl --list-devices                       # find the camera's /dev/video* node
arecord -l                                    # find the mic's card/device
ffmpeg -f v4l2 -i /dev/video0 -frames:v 1 -y /tmp/frame.jpg   # grab one frame
arecord -D plughw:3,0 -d 1 -f cd /tmp/clip.wav               # record 1s
```

`v4l-utils` (for `v4l2-ctl`) and `ffmpeg` are the only diagnostic extras; no
Logitech software is required.

## ⚠️ To revisit when the real IR (day/night) camera is used

The current detection code is only *softly* coupled to the Brio, but these
POC-specific assumptions should be re-checked when the IR camera is fitted:

1. **Capture-node heuristic.** `parse_v4l2_devices` takes the *first*
   `/dev/video*` node in the matched device group as the capture node. True for
   the Brio and most UVC webcams, but some cameras expose multiple capture nodes
   (e.g. separate MJPEG/metadata/IR nodes) where the first is not the right one.
   If the IR camera misbehaves, select the node that actually advertises the
   `Video Capture` capability (check each node with `v4l2-ctl -d <node> --all`)
   rather than assuming the first.
2. **Name hint.** The default `--name-hint BRIO` must change to the IR camera's
   name (see `v4l2-ctl --list-devices` / `lsusb`). Pass `--name-hint <name>`; no
   code change needed for detection.
3. **Mic address.** `plughw:3,0` is the Brio's mic. A different camera (or USB
   re-enumeration) changes the ALSA card number — detection re-derives it, but
   any hard-coded fallback elsewhere must be updated.
4. **IR-CUT / night mode.** If the IR camera has an automatic or motorised
   IR-CUT filter, add a check that day/night switching works (capture a frame in
   the dark). This is new behaviour with no Brio equivalent.
5. **Unit-test fixtures.** `tests/detection/` uses Brio-shaped `v4l2-ctl` /
   `arecord` output. Add fixtures for the IR camera's output when it arrives.

See the night-vision upgrade task in [`PLAN.md`](../plans/PLAN.md) for the hardware side.
