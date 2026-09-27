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
`Result : OK` (exit 0) when both are found. By default the samples are written
to a private, user-owned temp directory (e.g. `/tmp/babymonitor-XXXXXX/`); the
exact paths are printed in the `Frame`/`Audio` lines. Options:

```bash
./.venv/bin/python -m app.detection --no-capture         # detection only (read-only)
./.venv/bin/python -m app.detection --name-hint C920     # match a different webcam
./.venv/bin/python -m app.detection --out-dir ~/samples  # choose your own output dir
```

To eyeball the captured frame, copy it back to the Mac (use the path printed by
the command, or set a known `--out-dir` first):

```bash
# Example: pin the output dir, then copy that file back
ssh -i ~/.ssh/id_ed25519_babymonitor babymonitor@babymonitor.local \
  'cd ~/baby-monitor && ./.venv/bin/python -m app.detection --out-dir ~/samples'
scp -i ~/.ssh/id_ed25519_babymonitor \
  babymonitor@babymonitor.local:~/samples/brio_test.jpg /tmp/
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
6. **New capture backend (not just detection).** A CSI camera is not a UVC
   webcam: it uses the **libcamera** stack (`rpicam-vid` / `picamera2`), not
   ffmpeg-on-`/dev/video0`, and does not emit MJPEG natively (frames must be
   JPEG-encoded). This is exactly why the video layer is built around the
   swappable `FrameSource` interface — implement `app/video/sources/libcamera.py`
   (currently a stub) and select it with `BABYMONITOR_CAMERA=csi`. The streaming
   and web layers do not change.

### ⚠️ Verify before you buy (IR/night-vision modules)

The candidate module is an **OV5647 CSI** camera with IR-CUT + IR LEDs. Confirm
these with the seller before purchase, as they affect whether "automatic
day/night" is truly automatic:

- **Interface is CSI, not USB.** It connects via the 15-pin CSI ribbon (needs a
  Pi camera port + correct cable), and requires a **different capture backend**
  (libcamera) — see point 6 above. Budget time for that backend, not just a swap.
- **IR-CUT / IR-LED control is often manual via GPIO.** Many of these modules
  power the IR LEDs (and sometimes the IR-CUT solenoid) from a **GPIO pin**, not
  fully automatically. The product notes literally say *"Connect the power supply
  to GPIO, then the LED light will be on only when the camera is turned on."* So
  "automatic day/night" may need a **small GPIO control script** (toggle the IR
  LEDs / IR-CUT based on ambient light), plus wiring. Confirm: does day/night
  switch on its own, or does it expect a GPIO to be driven?
- **Focus is manual (adjustable).** The lens is manually focused — fine for a
  fixed cot view, but there's no autofocus.
- **IR LEDs need a light source in the dark.** NoIR sensors see nothing in true
  darkness without the IR illuminators actually working — verify the LEDs are
  included and functional (the notes mention common "LED doesn't work" issues
  fixed by tightening the bolts).

Practical check when it arrives: `rpicam-hello --list-cameras` should show the
sensor; capture a frame in a dark room to confirm the IR LEDs illuminate it.

See the night-vision upgrade task in [`PLAN.md`](../plans/PLAN.md) for the hardware side.
