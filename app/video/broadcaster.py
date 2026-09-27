"""Single app-owned capture broadcaster (latest-frame store + lifecycle).

Why this exists
---------------
The Task 4 stream opened one ffmpeg *per HTTP connection* against a
single-opener UVC device (the Brio), so a second viewer or a browser reconnect
collided on ``/dev/video0`` (EBUSY) and took the camera down. And because no
layer dropped frames, a slow WiFi viewer let ~13 frames/second pile up in kernel
socket buffers, so latency grew without bound. See
``plans/VIDEO_STREAM_DEBUG.md`` for the confirmed root causes.

``CameraBroadcaster`` fixes both at the capture layer, leaving the
``FrameSource`` interface untouched:

- It owns **one** ``FrameSource`` for the whole process. A background reader
  thread runs ``source.start()`` then, for every frame from ``source.frames()``,
  stores only the **latest** ``(seq, frame)`` (a monotonically increasing
  sequence number). Nothing queues, so nothing backs up.
- Viewers **subscribe** and wait (via a :class:`threading.Condition`) for a
  frame newer than the one they last saw. A slow viewer simply skips the
  intermediate frames — this is what bounds latency.
- Subscribers are **ref-counted**: the reader starts on the first subscriber and
  stops+joins on the last. ``start()``/``stop()`` are idempotent.
- If the source dies (``frames()`` ends or raises), the reader **auto-restarts**
  it: it reaps the old process (``source.stop()``) and reopens (``source.start()``)
  after a backoff (default 4 s, > the measured ~1.7–3 s device-release lag so
  the single-opener Brio is free before retrying). The backoff **escalates**
  (doubles) on consecutive failures up to a cap (default 60 s) so a permanently
  missing device does not hot-loop, and **resets** once frames flow again.
  Restarts are logged (via :mod:`logging`) so they show up in the app log.

The future CSI/libcamera backend drops in unchanged: the broadcaster depends
only on ``FrameSource``.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

from app.video.stream import FrameSource

_log = logging.getLogger(__name__)

# Default restart backoff. Part 1 measured the Brio's device-release lag at
# ~1.7 s (up to ~3 s given the source's stop() wait(timeout=3)); a 4 s floor
# ensures the old ffmpeg is fully reaped and the device reopenable before the
# reader retries, so a restart does not re-hit EBUSY.
_DEFAULT_RESTART_BACKOFF = 4.0
# Cap so a permanently-missing device backs off instead of hot-looping.
_DEFAULT_MAX_BACKOFF = 60.0


class CameraBroadcaster:
    """Own a single ``FrameSource`` and broadcast its latest frame to viewers."""

    def __init__(
        self,
        source: FrameSource,
        *,
        restart_backoff: float = _DEFAULT_RESTART_BACKOFF,
        max_backoff: float = _DEFAULT_MAX_BACKOFF,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._source = source
        # Restart tuning. ``restart_backoff`` is the initial wait after a source
        # death before reopening; it doubles per consecutive failure up to
        # ``max_backoff`` and resets to the initial value once a frame flows
        # again. ``sleep`` is injectable so tests never sleep real seconds.
        self._restart_backoff = restart_backoff
        self._max_backoff = max(max_backoff, restart_backoff)
        self._sleep = sleep
        # Guards all mutable state below and signals new frames / lifecycle.
        self._cond = threading.Condition()
        self._latest: tuple[int, bytes] | None = None
        self._seq = 0
        self._reader: threading.Thread | None = None
        self._running = False
        self._subscribers = 0

    # --- lifecycle ---------------------------------------------------------

    def start(self) -> None:
        """Start the background reader thread. Idempotent."""
        with self._cond:
            if self._running:
                return
            self._running = True
            self._reader = threading.Thread(
                target=self._run,
                name="camera-broadcaster",
                daemon=True,
            )
            self._reader.start()

    def stop(self) -> None:
        """Stop the source and join the reader thread. Idempotent."""
        with self._cond:
            if not self._running:
                return
            self._running = False
            reader = self._reader
            self._reader = None
            self._cond.notify_all()
        # Ask the source to unblock frames(); done outside the lock so the
        # reader thread can reacquire it as it winds down.
        self._source.stop()
        if reader is not None and reader is not threading.current_thread():
            reader.join()

    def is_running(self) -> bool:
        """Whether the reader thread is active."""
        with self._cond:
            return self._running

    # --- ref-counted subscription -----------------------------------------

    def subscribe(self) -> None:
        """Register a viewer; starts the reader on the first subscriber."""
        with self._cond:
            self._subscribers += 1
            first = self._subscribers == 1
        if first:
            self.start()

    def unsubscribe(self) -> None:
        """Deregister a viewer; stops the reader on the last subscriber."""
        with self._cond:
            if self._subscribers > 0:
                self._subscribers -= 1
            last = self._subscribers == 0
        if last:
            self.stop()

    # --- frame access ------------------------------------------------------

    def latest(self) -> tuple[int, bytes] | None:
        """Return the most recent ``(seq, frame)``, or ``None`` if none yet."""
        with self._cond:
            return self._latest

    def wait_for_newer(
        self, last_seq: int, timeout: float | None = None
    ) -> tuple[int, bytes] | None:
        """Block until a frame with ``seq > last_seq`` exists, then return it.

        Returns the ``(seq, frame)`` newer than ``last_seq``. Returns ``None`` if
        the wait times out or the broadcaster stops before a newer frame
        arrives. A caller loops passing back the ``seq`` it just saw, always
        receiving the latest frame and skipping any it missed while busy.
        """
        with self._cond:

            def has_newer() -> bool:
                return (self._latest is not None and self._seq > last_seq) or (not self._running)

            if not self._cond.wait_for(has_newer, timeout=timeout):
                return None  # timed out
            if self._latest is not None and self._seq > last_seq:
                return self._latest
            return None  # stopped without a newer frame

    # --- reader thread -----------------------------------------------------

    def _run(self) -> None:
        """Reader loop: capture frames, restarting the source on death.

        A single pass consumes ``source.frames()`` until it ends or raises.
        Whenever it dies while the broadcaster is still running, the source is
        fully reaped (``stop()``) and reopened (``start()``) after a backoff
        that escalates on consecutive failures (capped at ``max_backoff``) so a
        permanently-missing device does not hot-loop. The backoff resets once a
        frame flows again.
        """
        backoff = self._restart_backoff
        first_pass = True
        while True:
            with self._cond:
                if not self._running:
                    break
            if first_pass:
                # Phase 1 semantics: the initial start() happens here so the
                # very first open is not delayed by a backoff.
                first_pass = False
            else:
                # Reap the dead source before reopening so the single-opener
                # device (Brio) is released; then wait out the backoff.
                try:
                    self._source.stop()
                except Exception:  # pragma: no cover - defensive
                    _log.exception("camera-broadcaster: error stopping source before restart")
                with self._cond:
                    if not self._running:
                        break
                _log.warning("camera-broadcaster: restarting capture source in %.1fs", backoff)
                self._sleep(backoff)
                with self._cond:
                    if not self._running:
                        break
                backoff = min(
                    backoff * 2 if backoff > 0 else self._restart_backoff,
                    self._max_backoff,
                )

            try:
                self._source.start()
                got_frame = False
                for frame in self._source.frames():
                    with self._cond:
                        if not self._running:
                            break
                        self._seq += 1
                        self._latest = (self._seq, frame)
                        self._cond.notify_all()
                    got_frame = True
                if got_frame:
                    # Healthy capture that then ended: reset the backoff so a
                    # transient blip does not inherit an escalated delay.
                    backoff = self._restart_backoff
            except Exception:
                _log.exception("camera-broadcaster: capture source raised; will restart")

            with self._cond:
                if not self._running:
                    break
            # Source ended/raised while still running: loop to restart it.

        # Stopped: wake any waiters so they don't block forever.
        with self._cond:
            self._cond.notify_all()
