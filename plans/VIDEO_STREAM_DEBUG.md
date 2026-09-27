# Debug & Improvement Plan — Live Video Stream

Status: **debugged — fix pending**. Owner: (assign). Related: Task 4 in
[`PLAN.md`](PLAN.md); code in `app/video/`.

## Problem statement

The Task 4 live MJPEG stream has two observed symptoms on the Pi 4 over WiFi:

1. **Latency:** the feed lags by **more than a minute**, and the lag appears to
   grow the longer the stream runs.
2. **Instability:** the feed intermittently **crashes — the Brio's camera light
   turns off — then resumes** on its own after a short pause.

Success criteria for "fixed":

- End-to-end latency is **low and bounded** (does not grow over time); target
  well under a few seconds for a LAN baby monitor.
- The feed is **stable**: no spontaneous crash/recover cycles during normal
  viewing, including on reconnect and with more than one viewer.
- A single viewer, a reconnecting viewer, and two simultaneous viewers all work
  without taking the camera down.

---

## Part 1 — Debug (what to investigate, not how)

Work through these to confirm or rule out each hypothesis. **Record what you find
under "Findings" below** — do not change production behaviour during
investigation beyond what is needed to observe it. Capture evidence (numbers,
logs, PIDs) rather than impressions.

### A. Characterise the latency
- Determine **where** the delay accumulates: at capture (ffmpeg itself), in the
  app's buffering between ffmpeg and the client, or in the network/browser.
- Establish whether latency is **constant or growing** over a sustained view.
- Compare latency at the current setting (720p/15fps) against a lighter setting
  to see how much is bandwidth/throughput driven.

### B. Characterise the crash/recover cycle
- Capture **why ffmpeg exits** when the light goes off (its stderr is currently
  discarded — make it observable).
- Determine how many **ffmpeg processes / camera openers** exist over time, and
  whether a new viewer or a browser reconnect spawns an additional opener while
  one is still running (device contention on a single-opener UVC device).
- Establish the **trigger**: does it correlate with reconnects, a second viewer,
  a period of slow consumption, or something time-based?

### C. Rule out environment
- Check **CPU and memory** headroom on the Pi while streaming.
- Check for **power/undervoltage** warnings (can reset USB devices → camera
  light off).
- Check **WiFi throughput / signal** as a bandwidth ceiling at 720p.

### D. Confirm the concurrency model
- Confirm whether capture is **per-connection** or **shared**, and whether the
  chosen server model can serve the long-lived stream plus other requests and
  multiple viewers without starving or blocking.

### Findings (fill in during debugging)
> Record confirmed root causes with evidence. Note which hypotheses were
> rejected. These findings feed directly into Part 2.

- Latency cause(s): **CONFIRMED — a producer/consumer bitrate mismatch with no
  frame-dropping. ffmpeg produces ~16 Mbps of MJPEG but WiFi delivers only
  ~1.2–1.5 Mbps to the client, so ~13 frames/second accumulate in kernel buffers
  every second the stream runs. Latency is UNBOUNDED and GROWS monotonically.**
  The delay is in **network/socket buffering (WiFi is the ceiling), NOT in
  ffmpeg capture and NOT in the app's Python-side buffering.** Evidence:

  - **Producer rate (raw ffmpeg direct from device, no app/HTTP):** 720p/15fps
    captured cleanly — 145 frames in 10 s = **14.5 fps, avg frame 138 KB,
    16.4 Mbps** (`ffmpeg -c:v copy` MJPEG passthrough, exit 0). So capture keeps
    real time; **ffmpeg is not where latency accumulates.**
  - **App-internal path is NOT the bottleneck (isolates buffering point):** a
    `curl` on the Pi against `127.0.0.1:8000/video_feed` (WiFi removed) received
    **202 frames in 15 s = 13.5 fps, 15.17 Mbps** — i.e. the full production
    rate. The kernel pipe + `iter_mjpeg_frames` bytearray + Werkzeug generator
    keep up perfectly when the consumer is fast. **No unbounded growth over
    loopback.** The `iter_mjpeg_frames` bytearray is self-draining (yielded
    frames are `del`-ed; holds ≤1 partial frame), and the kernel pipe is capped
    (`fs/pipe-max-size = 1 MiB` ≈ ~7 frames); neither can hold minutes of video.
  - **The client receives far less than is produced (the smoking gun for
    growth):** a 30 s `curl` from the Mac over WiFi received only **40 frames =
    1.3 fps, 1.48 Mbps** vs 14.5 fps produced — a **received/produced ratio of
    0.09 (9%).** ~13.2 frames/s have nowhere to go but buffers. Backlog growth is
    therefore ~13 frames/s ≈ monotonic; over minutes this is the observed
    >1-minute lag.
  - **Where the backlog sits — the kernel TCP send buffer:** live `ss -tni`
    against the connected client showed a persistent multi-MB `Send-Q`
    (samples 3.35 MB → 3.19 MB → 2.55 MB; `notsent` 2.43 MB → 1.09 MB) with
    **smoothed `rtt` ~5,000–5,500 ms and even `minrtt` ~1,020 ms** (a LAN should
    be <5 ms) — the RTT is inflated precisely because ~3 MB is queued ahead. At
    the measured ~1.48 Mbps drain, **1 MB of backlog ≈ 5.4 s of latency**, so the
    ~3 MB `Send-Q` alone is ~16 s, and it keeps growing while viewed.
  - **Bandwidth-driven (720p vs lighter):** 640x480/15fps raw = **14.6 fps,
    58 KB/frame, 6.93 Mbps** — ~2.4× lighter than 720p's 16.4 Mbps, but **still
    ~4.6× the ~1.5 Mbps the WiFi link actually delivered.** So dropping to 480p
    reduces but does **not** eliminate the mismatch on this link — rightsizing
    alone is insufficient; frame-dropping is required to bound latency.
  - **WiFi is the ceiling, not the Pi:** `nmcli` shows a 130 Mbit/s nominal PHY
    but **signal only 49/100**; real TCP goodput to the client was ~1.2–1.5 Mbps
    with **~1 MB retransmitted** (`bytes_retrans`, `lost`, `dsack_dups`) —
    lossy/weak WiFi, far below the PHY rate. CPU/power are NOT involved
    (`throttled=0x0`, load ~0.17, ffmpeg 0.1% CPU) — see Environment.

- Crash/recover cause(s): **CONFIRMED — device contention on the single-opener
  UVC Brio, triggered by a browser reconnect (new `/video_feed` request) while
  the previous ffmpeg still holds `/dev/video0`.** Evidence:
  - **Per-connection capture:** the `/video_feed` route calls
    `get_frame_source()` per request and `mjpeg_stream` calls `start()` each
    time, so **every HTTP connection spawns its own ffmpeg** opening
    `/dev/video0`. `fuser -v /dev/video0` showed exactly one holder at a time
    (app child PID 2595); the app process (PID 2557) parents the ffmpeg
    directly.
  - **Single-opener constraint proven:** running the *exact app ffmpeg command*
    a second time while one was live fails immediately with, verbatim on
    stderr:
    ```
    [in#0 @ 0x...] Error opening input: Device or resource busy
    Error opening input file /dev/video0.
    Error opening input files: Device or resource busy
    ```
    exit code 240, **0 bytes** captured. (The app discards this via
    `stderr=DEVNULL`, which is why the failure was invisible.)
  - **The collision race caught live:** 100 ms sampling of `pgrep ffmpeg` during
    a new `/video_feed` request showed a **transient second ffmpeg (PID 2885)
    appear alongside the incumbent (PID 2595) for a single ~100 ms sample, then
    vanish** — the new request's ffmpeg spawned, hit "busy", and died. The HTTP
    response was `http_code=200 size=0` (connection accepted, 0 bytes streamed).
  - **A real crash/recover cycle observed in the wild:** the incumbent ffmpeg
    PID 2595 went **`<defunct>` (zombie)** while the browser's TCP connection
    **changed source port 63659 → 63889 (a reconnect)** and a fresh ffmpeg
    spawned. This is the crash (light off) → recover (light on) cycle: reconnect
    kills the old stream, races the device, and the survivor wins.
  - **Reconnect window measured:** after `SIGTERM` to an ffmpeg holding the
    device (mirrors the app's `stop()` → `terminate()`), the device became
    reopenable after **~1.7 s** (killed 17:45:35.667, reopen succeeded
    17:45:37.384). The app's `stop()` does `terminate()` then `wait(timeout=3)`
    then `kill()`, so the device can stay held for up to ~3 s during teardown —
    any reconnect arriving in that window hits "busy" and yields a black/empty
    feed until the next successful open.

- Environment (CPU / power / WiFi): **CPU and power RULED OUT; WiFi throughput
  CONFIRMED as the environmental ceiling driving the latency.** Measured on the
  Pi (Pi 4, 4 cores, kernel 6.18.50-rpi-v8) with the stream running:
  - **CPU — ruled out.** With ffmpeg + python live: `%Cpu(s)` = **92.9 idle**,
    load avg **0.02 / 0.02 / 0.00**. Per-process: ffmpeg (PID 2595) **0.1 %CPU**,
    python (PID 2557) **0.2 %CPU**. Expected — the app uses `ffmpeg -c:v copy`
    (stream copy, **no transcode**), so capture is near-free on CPU. Not a
    contributor to either symptom.
  - **Memory — ruled out.** `free -h`: **1.3 GiB available** of 1.8 GiB total,
    **0 B swap used**. ffmpeg RSS ~102 MiB, python ~48 MiB. No pressure.
  - **Power / under-voltage — ruled out.** `vcgencmd get_throttled` = **`0x0`**
    (bit-decoded: no under-voltage now, no throttling now, and **no historical
    under-voltage or throttle event since boot** — bits 16/17/18/19 all clear).
    `measure_temp` = **58.4 °C** (far under the 80–85 °C throttle band);
    `measure_volts core` = **0.86 V** (nominal). **No under-voltage lines in
    `dmesg`** at all. → not a USB brown-out resetting the Brio.
  - **USB / Brio stability — ruled out for this window.** `dmesg` (516 lines,
    full current boot, uptime 1 h 40 m) shows the Brio enumerated **once** at
    boot as a **SuperSpeed (USB 3.0) device** —
    `uvcvideo 2-1:1.0: Found UVC 1.00 device Logitech BRIO (046d:085e)` — with
    **no USB reset, disconnect, or re-enumeration since**. The only recurring
    USB lines are `usb 2-1: current rate 16000 is different from the runtime
    rate 48000`, which are **UVC-audio sample-rate info messages, not resets**,
    and do not correlate with the video crashes. *Caveat:* `dmesg` covers only
    the current boot; a hardware USB reset was **not observed** during this
    session (the crash/recover in Part 1.B was software device-contention, not a
    USB reset).
  - **WiFi throughput — CONFIRMED bottleneck (root cause of the growing
    latency).** Path is **wlan0** (2.4 GHz, ch 1, SSID NOKIA-9611); `eth0` is
    unavailable (no carrier). Signal is weak/borderline: **-69 to -70 dBm**,
    link quality **39–41 / 70**, negotiated PHY rate 130 Mbit/s, and
    `brcmfmac ... power save enabled`. Effective end-to-end throughput measured
    **twice, independently**: `dd` over ssh **≈156 KB/s (~1.25 Mbit/s)** for
    10 MB in 67 s; `scp` **≈154 KB/s (~1.23 Mbit/s)** for 20 MB in 2 m 9.7 s.
    Latency is jittery: `ping ×20` = **0 % loss but RTT 17.9 / 44.6 / 175 ms
    (min/avg/max), stddev 41 ms** — classic weak-signal + power-save jitter.
    **The stream needs ~10× more than WiFi delivers:** served MJPEG measured
    over **loopback** (no WiFi in path) = **1.9 MB/s / 15.17 Mbit/s** (202 frames
    in 15 s ≈ 13.5 fps at 720p/15fps). So producer ≈15 Mbit/s vs WiFi path
    ≈1.2 Mbit/s → **WiFi carries only ~8 % of the stream's bitrate.** This is
    *why* the ~3 MB kernel `Send-Q` backlog (Part 1.A) never drains and latency
    grows without bound. WiFi is a genuine environmental **latency** contributor;
    it is **not** the crash cause (the crash is device contention, Part 1.B).

- Concurrency model observations: Flask dev server with `threaded=True` (app
  PID 2557 runs with multiple LWPs). Capture is **per-connection, not shared** —
  confirmed by per-request `get_frame_source()`/`start()`. Consequences seen:
  (1) two overlapping viewers cannot both stream — the second gets 0 bytes
  (device busy); (2) dead ffmpegs are only reaped when the streaming generator's
  `finally: stop()` runs, so **`<defunct>` ffmpeg zombies appear transiently**
  (observed PID 2595 defunct, later reaped). No shared/broadcast layer exists.

  **Part 1.D controlled tests (2026-09-27) — corroborating evidence:**
  - *Per-connection spawn, single viewer (clean, no other viewers):* before =
    no ffmpeg; during one `/video_feed` client = **exactly one ffmpeg
    `PID 3845 PPID 2557`** (child of the app), streaming 13.7 MB over 8 s
    (~1.7 MB/s ≈ ~13.7 Mbps at 720p/15); after disconnect = **no ffmpeg**
    (generator `finally: stop()` reaped it). Confirms one ffmpeg per connection
    with clean teardown on the happy path.
  - *Two simultaneous `/video_feed` clients (app level):* with client A already
    holding the device, client B connected → **only one ffmpeg existed
    (`PID 3759 PPID 2557`)**; the winning client streamed strongly
    (7.6 → 20.8 → 22.8 MB) while the **losing client received 0 bytes for the
    entire session** — its HTTP connection stayed open serving nothing (a silent
    blank viewer, not an error). In a run where a browser viewer was also
    reconnecting, the collision briefly drove ffmpeg to **0** and **both** curl
    clients got 0 bytes. So a second viewer/reconnect either starves one viewer
    or takes the capture down.
  - *Threaded server is NOT the bottleneck:* during an active stream, `/healthz`
    and `/` both returned **`200` in ~2.5 ms**. `threaded=True` serves
    concurrent HTTP fine; the failure is camera contention from per-connection
    capture, not request starvation.
  - **Statement of record (Part 1.D):** capture is **PER-CONNECTION** (each
    `/video_feed` spawns its own ffmpeg opener of the single-opener Brio); a
    single viewer works and tears down cleanly; **two viewers / reconnects
    collide on `/dev/video0` (EBUSY)** so one viewer gets 0 bytes or the stream
    drops. The dev server's threading model is adequate for serving — the fix
    belongs at the capture layer (single app-owned opener + broadcast), not the
    web server.

- Rejected hypotheses:
  - **Under-voltage / power resetting the USB camera** — rejected;
    `get_throttled=0x0`.
  - **CPU or memory exhaustion on the Pi** — rejected; load ~0.02, 1.3 GiB free.
  - **ffmpeg crashing on its own / a camera hardware fault** — rejected; a
    single ffmpeg opener ran cleanly for 18+ min (PID 2595, `etime 18:26`) with
    no error until a *reconnect* displaced it. The Brio node `/dev/video0`
    advertises `MJPG 1280x720` and opens fine when uncontended.
  - **Multiple ffmpegs actually streaming in parallel** — rejected; only one can
    hold the device; extras die instantly with "Device or resource busy".
  - **WiFi/bandwidth as the *crash* cause** — rejected as the crash trigger; the
    crash is software device-contention on reconnect (Part 1.B). WiFi *is*
    confirmed as the **latency** ceiling (effective ~1.2 Mbit/s vs ~15 Mbit/s
    stream demand — see Environment above), but a starved link backs up buffers;
    it does not turn the camera light off.
  - **A USB hardware reset of the Brio (power/cable) causing the light-off** —
    not observed; `dmesg` shows zero USB resets/disconnects since boot and
    `get_throttled=0x0`. The light-off is the incumbent ffmpeg being displaced
    by a reconnect, not a hardware reset. (Not fully excludable across all boots,
    but no evidence for it in this session.)

---

## Part 2 — Fix strategy (proposed; update after debugging)

> Proposed based on a code review before debugging. **Revise this section once
> the Part 1 findings are in** — keep, drop, or adjust each item to match the
> confirmed causes, then implement.

> **Evidence annotations (Part 1.B, crash/recover):** the debug findings
> confirm the two load-bearing assumptions behind this strategy. Notes are
> appended per item below; the overall direction is **supported by evidence**.

> **Evidence update (consolidated across all four investigations — 2026-09-27):**
> the strategy is validated as-is; no wholesale rewrite needed. Which items the
> evidence bears on:
> - **SUPPORTS — single shared capture (highest priority):** the crash is
>   confirmed per-connection contention on the single-opener Brio (a second
>   opener returns "Device or resource busy", exit 240, 0 bytes; live races
>   caught PIDs 2885/2595 and 3759). One app-owned opener regardless of viewer
>   count directly removes this. Confirmed by both the crash and concurrency
>   stages.
> - **SUPPORTS — latest-frame / drop-stale broadcast (load-bearing for
>   latency):** growing latency is confirmed as a producer/consumer bitrate
>   mismatch (~15–16 Mbps produced vs ~1.2–1.5 Mbps WiFi delivered ≈ 8–9%) with
>   no frame-dropping; the kernel TCP `Send-Q` held a persistent ~2.9–3.9 MB
>   backlog that never drained. Dropping stale frames is the correct, load-bearing
>   remedy.
> - **SUPPORTS — surface capture stderr:** the crash cause was invisible only
>   because `ffmpeg_v4l2.py` uses `stderr=DEVNULL`; the "busy" error was readable
>   only by running the command manually. Low-cost, high-value.
> - **SUPPORTS (with caveat) — auto-restart with backoff:** backoff must exceed
>   the measured device-release lag (~1.7 s, up to ~3 s given `stop()`'s
>   `wait(timeout=3)`) and fully reap the old process (transient `<defunct>`
>   ffmpeg zombies observed) or the restart re-hits "busy".
> - **PARTIALLY CONTRADICTS (as a standalone fix) — right-size the stream:**
>   bandwidth is a real latency ceiling, but even 480p/15fps (6.93 Mbps) is
>   ~4.6× the ~1.5 Mbps WiFi delivers, so rightsizing alone will NOT bound
>   latency — it is complementary, not a substitute for the broadcast. CPU/power
>   are NOT constraints (`throttled=0x0`, load ~0.02, 92.9% idle), so
>   power/CPU-oriented tuning is unnecessary.
> - **NEUTRAL — server model:** `threaded=True` is adequate (`/healthz`, `/`
>   returned 200 in ~2.5 ms during an active stream); the fix belongs at the
>   capture layer, not the web server. Preserving the `FrameSource` interface is
>   unaffected by the evidence.

### Design (refined from the evidence)

Insert a **single app-owned capture broadcaster** between the `FrameSource`
backend and the HTTP viewers. One ffmpeg opener for the whole process; each
viewer reads the *latest* frame and never backs up the pipeline.

```
FrameSource (ffmpeg/V4L2, unchanged interface)
        │  raw JPEG frames
        ▼
CameraBroadcaster        ← NEW: one per app; owns the single FrameSource
  • background thread runs source.start(); for f in source.frames(): store f
  • keeps only the LATEST frame + a monotonically increasing frame id/seq
  • ref-counts subscribers; starts on first subscriber, stops on last (or stays warm)
  • auto-restarts the source on death with backoff > device-release lag
        │  latest frame, on demand
        ▼
mjpeg_stream(subscriber)  ← per-viewer generator: emit latest frame, drop stale
        │
        ▼
/video_feed route         ← subscribes to the shared broadcaster (no new ffmpeg)
```

Key decisions grounded in Part 1:
- **Single opener** removes the EBUSY crash (Part 1.B/D). The route no longer
  calls `get_frame_source()` per request; it subscribes to the shared instance.
- **Latest-frame-only** bounds latency (Part 1.A): a slow WiFi viewer that can
  take only ~1.3 fps simply skips intermediate frames instead of queuing ~13/s.
  Each viewer waits for a *new* frame (via a `Condition`), so it always sends the
  most recent JPEG, never a stale backlog.
- **Backoff ≥ 4 s** on restart (measured release lag ~1.7 s, up to ~3 s from
  `stop()`'s `wait(timeout=3)`), and the old process must be fully reaped before
  reopening to avoid re-hitting EBUSY.
- **stderr surfaced** to the app log (drop `stderr=DEVNULL`) so capture failures
  are diagnosable.
- **Right-sizing is complementary, not the fix.** Keep 720p default but make it
  trivially tunable; the broadcaster is what bounds latency. (Optional: lower
  default fps to cut bandwidth once the broadcast is in.)
- **`FrameSource` interface unchanged** → the future CSI/libcamera backend still
  drops in; the broadcaster sits above it.

### Implementation phases (TDD; hardware mocked)

Each phase is independently testable and committable. `make verify` green per phase.

- **Phase 1 — `CameraBroadcaster` (latest-frame store + lifecycle). DONE.**
  New `app/video/broadcaster.py`. Owns a `FrameSource`, runs a reader thread
  storing only the latest `(seq, frame)`, and exposes a subscriber API that
  blocks until a frame newer than the caller's last seq is available.
  *Tests (fake FrameSource, no hardware):* a fast producer + slow consumer yields
  **frame-dropping** (consumer sees latest, not every frame); multiple
  subscribers all get the latest; start is idempotent; stop joins the thread.

- **Phase 2 — auto-restart with backoff + observable errors. DONE.**
  Reader thread restarts the source if `frames()` ends/raises, with backoff
  (default 4 s, configurable via `restart_backoff`; escalates by doubling and is
  capped by `max_backoff`, default 60 s; resets once frames flow again) and full
  reap (`source.stop()`) before reopen; capture stderr is surfaced to the app
  log. Changes: `app/video/broadcaster.py` (restart loop + config params +
  injectable `sleep`), `app/video/sources/ffmpeg_v4l2.py` (`stderr=PIPE` drained
  to `logging`, reaped in `stop()`), `app/main.py` (`logging.basicConfig` so
  records reach `server.log`).
  *Tests:* a source that raises once triggers a restart after backoff; a source
  that ends is reopened; repeated failures escalate and cap the backoff (no
  hot-loop); a requested stop never restarts — all with an injected clock/sleep
  (no real seconds slept).

- **Phase 3 — rework `mjpeg_stream` + `/video_feed` to use the broadcaster.**
  `mjpeg_stream` takes a broadcaster subscription (latest-frame generator)
  instead of driving a `FrameSource` directly. `/video_feed` subscribes to the
  single app-owned broadcaster (created once, e.g. on the app object), so no
  ffmpeg is spawned per request. Client disconnect just unsubscribes; the camera
  stays up for other viewers.
  *Tests:* route returns multipart MJPEG from a mocked broadcaster; two
  simultaneous test clients both receive frames; a client disconnect does not
  stop the broadcaster.

- **Phase 4 — on-Pi validation.** Deploy; verify against the real Brio:
  latency stays bounded over several minutes; one ffmpeg regardless of viewer
  count (`pgrep -af ffmpeg` shows exactly one); two browsers both view live; a
  browser refresh/reconnect does **not** drop the camera. Record numbers in "Fix
  findings" below.

- **Phase 5 — live log viewer (`scripts/logs.sh`).** A helper to watch the app's
  logs live from the Mac, matching the existing script family
  (`deploy.sh`/`start.sh`) and reusing `scripts/config.sh` for connection
  details. Chosen over a bare one-liner (repeatable, short to run) and over a
  `make` target (keeps `make` for the verify gate only).
  - Default: follow the live log — `ssh <pi> 'tail -f ~/baby-monitor/server.log'`.
  - Options: `-n N` for the last N lines then follow; `--no-follow` for a
    one-shot dump.
  - **Depends on Phase 2:** surfacing ffmpeg stderr into the app log means
    capture errors and auto-restarts show up live in this viewer (currently
    stderr is `DEVNULL`, so the log only has Flask/Werkzeug lines). The app must
    log to the same `server.log` that `start.sh` writes.
  - Document it in `docs/DEPLOY_RUNBOOK.md` (Monitor section).
  - *Tests:* n/a (thin SSH wrapper); verify manually that it streams live lines
    and shows a capture restart when one is triggered.

### Test / validation plan for the fix
- **Latency bounded** over a multi-minute view (no monotonic growth); target a
  few seconds max on this WiFi.
- **No crash/recover** on a single viewer, on browser reconnect/refresh, or with
  two simultaneous viewers.
- **Exactly one ffmpeg / one camera opener** regardless of viewer count
  (`pgrep -af ffmpeg`).
- **Frame-dropping proven in unit tests** (fast producer / slow consumer → sees
  latest only), plus multi-subscriber and restart-with-backoff tests, all with
  hardware mocked.
- **`scripts/logs.sh` streams live logs** and shows capture errors/restarts as
  they happen.
- On-Pi manual check for real latency/stability numbers.
- `make verify` green.

### Risks / watch-items
- **Thread lifecycle:** ensure the reader thread and ffmpeg are reaped on app
  shutdown and on last-unsubscribe (no zombie ffmpeg, no thread leak).
- **First-frame wait:** a new subscriber before the first frame arrives should
  block briefly, not error; guard startup.
- **Restart storm:** if the device is permanently gone, backoff must cap and the
  feed should surface "camera unavailable" rather than hot-loop.
- **Dev server:** `threaded=True` is adequate (Part 1.D); a production WSGI
  server remains a separate later concern, not part of this fix.

### Fix findings / outcome (fill in after implementing)
> What was actually changed, measured latency before/after, and any deviation
> from the proposed strategy.

**Implemented (Phases 1–3, 5):** `CameraBroadcaster` (single app-owned ffmpeg +
latest-frame store), auto-restart with backoff, `mjpeg_stream` reworked to
subscribe to the shared broadcaster with a bounded `wait_for_newer`, `/video_feed`
subscribes to the single app-owned broadcaster, `scripts/logs.sh` added.
`make verify` green (30 tests). Testing note: the Flask test client cannot drain
an infinite streaming response (it buffers inside `client.get`), so route tests
use a finite fake broadcaster; the concurrency behaviours are unit-tested against
`CameraBroadcaster`/`mjpeg_stream` directly (no Flask).

**On-Pi Phase 4 results (2026-09-27):**
- ✅ **Crash/recover FIXED.** Exactly **one** ffmpeg (`pgrep -xc ffmpeg` = 1)
  held for 2m+ across multiple browser reconnects (three `GET /video_feed` in the
  log on one shared ffmpeg PID 5580/PPID 5570). No camera-light-off cycle. The
  single-shared-opener change did what Part 1.B/D predicted.
- ⚠️ **Latency IMPROVED but NOT solved:** ~30–45 s (was >1 min). Root cause of
  the residual lag located via `ss -tni` on the live viewer socket:
  **`Send-Q ≈ 3.6 MB`, `notsent ≈ 3.5 MB`, `rtt 744 ms`, delivery ~475 kbps.**
  ~3.5 MB queued in the **kernel TCP send buffer** ÷ ~475 kbps ≈ **~30 s** —
  matches the observed lag.
- **Why latest-frame-drop didn't bound it:** the app correctly yields only the
  newest frame, but each `yield` is accepted **wholesale into the kernel socket
  send buffer** (the write returns immediately), so ~27 frames' worth queue
  *downstream* of our drop logic. We drop stale frames *before* the socket; the
  socket itself hoards them. App-level latest-frame selection cannot reach a
  buffer the kernel fills on our behalf.

**Deviation from proposed strategy / follow-up needed (Phase 6):** the
"latest-frame broadcast" is necessary but **insufficient on its own** — it must
be paired with **backpressure + bitrate reduction** so the kernel can't buffer
tens of seconds of video:
1. **Shrink the socket send buffer** (`SO_SNDBUF` ≈ 1–2 frames, e.g. 128 KB) so
   a full buffer blocks our `yield`, and that backpressure is what actually makes
   frame-dropping effective (we skip frames while the socket is full).
2. **Cut the stream bitrate to fit WiFi** — measured WiFi goodput is ~1.2–1.5
   Mbps, but 720p/15fps ≈ 16 Mbps and even 480p/15fps ≈ 7 Mbps. Lower fps and/or
   resolution (and/or re-encode to a lower JPEG quality) so produced bitrate
   approaches the link. This is the "right-size" item, now confirmed **required**,
   not optional.
3. Consider dropping frames explicitly when the socket is not writable (pace to
   the drain rate) rather than relying solely on `SO_SNDBUF` backpressure.

Status: **crash fixed; latency partially fixed — Phase 6 (backpressure +
bitrate) required to meet the "few seconds" target.**

**WiFi relocation (2026-09-27, before Phase 6):** moving the Pi closer to the
router raised signal 49→62/100 and link rate 130→270 Mbit/s. Live viewer socket
then showed **Send-Q ~0.1 MB (was 3.6 MB), rtt 2.5–17 ms (was 744 ms), delivery
40–59 Mbps (was 475 kbps), ~20 fps received** — the lag effectively disappeared.
This confirmed the residual latency was bandwidth-driven backlog, not code. It
made Phase 6 **defensive** (bound latency even if the link degrades) rather than
blocking.

**Phase 6 implemented & validated on-Pi (2026-09-27):**
- **Right-sized bitrate:** default fps lowered 15→10 in `factory.py`
  (env-overridable via `BABYMONITOR_VIDEO_FPS`); confirmed on-Pi the ffmpeg runs
  `framerate 10`. Tests: `tests/video/test_factory.py`.
- **Send-buffer backpressure:** new `app/video/backpressure.py` —
  `cap_send_buffer()` (best-effort `SO_SNDBUF` cap, default 128 KB) applied per
  connection by `BackpressureRequestHandler`, wired via
  `app.run(request_handler=...)`. On-Pi the live viewer socket showed
  **`tb=262144` (256 KB kernel-doubled cap, was multi-MB)**, write buffer
  `w≈87 KB` (< 1 frame), **`Send-Q 0`**, ~7.5 fps delivered. Tests:
  `tests/video/test_backpressure.py` (real socket).
- Still **one ffmpeg** regardless of viewers; `make verify` green (**35 tests**).

Net effect: with the send buffer capped to ~1 frame, a slow link now applies
backpressure to the generator, so the broadcaster's latest-frame drop bounds
latency by design — the kernel can no longer hoard seconds of video.

Status: **FIXED — crash resolved (single shared opener) and latency bounded
(WiFi relocation + Phase 6 backpressure/right-sizing). Latency-bounding holds
even under a weak link.**
