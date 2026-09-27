"""Unit tests for ``CameraBroadcaster`` (hardware mocked).

The broadcaster sits between a single ``FrameSource`` (one ffmpeg opener) and
many HTTP viewers. It runs a background reader thread that keeps only the
*latest* ``(seq, frame)`` and lets each subscriber wait for a frame newer than
the one it last saw — so a slow consumer skips stale frames instead of backing
up the pipeline. None of these tests touch real hardware; a fake in-process
``FrameSource`` drives the broadcaster.

Coverage:
- (a) fast producer + slow consumer => consumer sees the LATEST frame, not
  every frame (frame-dropping proven).
- (b) multiple subscribers all get the latest frame.
- (c) ``start()`` is idempotent (one reader thread / one ``source.start()``).
- (d) ``stop()`` joins the reader thread cleanly (no thread/process leak).
- (Phase 2) auto-restart with backoff: a source that raises once is reopened
  after the backoff; a source that ends is reopened; repeated failures escalate
  and cap the backoff (no hot-loop); a requested stop never triggers a restart.
  Backoff is exercised via an injected ``sleep`` (no real seconds slept).
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator

from app.video.broadcaster import CameraBroadcaster


class FakeSource:
    """A controllable, in-process ``FrameSource`` (no hardware).

    Frames are pushed by the test via :meth:`push`; ``frames()`` blocks until a
    frame is available or the source is stopped, mimicking a live camera whose
    output arrives over time.
    """

    def __init__(self) -> None:
        self.start_count = 0
        self.stop_count = 0
        self._queue: list[bytes] = []
        self._cond = threading.Condition()
        self._stopped = False

    def start(self) -> None:
        with self._cond:
            self.start_count += 1

    def push(self, frame: bytes) -> None:
        with self._cond:
            self._queue.append(frame)
            self._cond.notify_all()

    def frames(self) -> Iterator[bytes]:
        while True:
            with self._cond:
                while not self._queue and not self._stopped:
                    self._cond.wait()
                if self._queue:
                    yield self._queue.pop(0)
                    continue
                if self._stopped:
                    return

    def stop(self) -> None:
        with self._cond:
            self.stop_count += 1
            self._stopped = True
            self._cond.notify_all()


class ListSource:
    """A ``FrameSource`` that yields a fixed list of frames then ends."""

    def __init__(self, frames: list[bytes]) -> None:
        self._frames = frames
        self.start_count = 0
        self.stop_count = 0

    def start(self) -> None:
        self.start_count += 1

    def frames(self) -> Iterator[bytes]:
        yield from self._frames

    def stop(self) -> None:
        self.stop_count += 1


def _wait_until(predicate: object, timeout: float = 2.0) -> bool:
    """Poll ``predicate`` until true or ``timeout`` elapses."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():  # type: ignore[operator]
            return True
        time.sleep(0.005)
    return False


# --- (a) frame-dropping: fast producer, slow consumer -----------------------


def test_slow_consumer_sees_latest_frame_not_every_frame() -> None:
    source = FakeSource()
    caster = CameraBroadcaster(source)
    caster.subscribe()
    try:
        # Produce many frames rapidly before the consumer reads anything.
        for i in range(100):
            source.push(f"frame-{i:03d}".encode())

        # Wait until the reader has stored the final produced frame.
        assert _wait_until(lambda: caster.latest() == (100, b"frame-099"))

        # A slow consumer reading now gets the LATEST frame, having dropped the
        # 99 intermediate ones (not one-frame-per-produced).
        result = caster.wait_for_newer(0, timeout=2.0)
        assert result is not None
        seq, frame = result
        assert frame == b"frame-099"
        assert seq == 100
    finally:
        caster.unsubscribe()


def test_wait_for_newer_blocks_until_a_newer_frame_arrives() -> None:
    source = FakeSource()
    caster = CameraBroadcaster(source)
    caster.subscribe()
    try:
        source.push(b"first")
        assert _wait_until(lambda: caster.latest() is not None)
        first = caster.latest()
        assert first is not None
        first_seq, _ = first

        got: list[tuple[int, bytes]] = []

        def consume() -> None:
            res = caster.wait_for_newer(first_seq, timeout=2.0)
            if res is not None:
                got.append(res)

        t = threading.Thread(target=consume)
        t.start()
        # Give the consumer a moment to block, then produce a newer frame.
        time.sleep(0.05)
        source.push(b"second")
        t.join(timeout=2.0)

        assert not t.is_alive()
        assert len(got) == 1
        assert got[0][1] == b"second"
        assert got[0][0] > first_seq
    finally:
        caster.unsubscribe()


# --- (b) multiple subscribers all get the latest ----------------------------


def test_multiple_subscribers_all_get_the_latest_frame() -> None:
    source = FakeSource()
    caster = CameraBroadcaster(source)
    caster.subscribe()
    caster.subscribe()
    try:
        source.push(b"latest-frame")
        assert _wait_until(lambda: caster.latest() == (1, b"latest-frame"))

        results: list[tuple[int, bytes] | None] = [None, None]

        def consume(idx: int) -> None:
            results[idx] = caster.wait_for_newer(0, timeout=2.0)

        threads = [threading.Thread(target=consume, args=(i,)) for i in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=2.0)

        assert all(not t.is_alive() for t in threads)
        assert results[0] == (1, b"latest-frame")
        assert results[1] == (1, b"latest-frame")
    finally:
        caster.unsubscribe()
        caster.unsubscribe()


# --- (c) start idempotent ---------------------------------------------------


def test_start_is_idempotent_single_reader_and_single_source_start() -> None:
    source = FakeSource()
    caster = CameraBroadcaster(source)
    caster.start()
    caster.start()
    caster.start()
    try:
        # source.start() called exactly once despite repeated start().
        assert _wait_until(lambda: source.start_count == 1)
        time.sleep(0.05)
        assert source.start_count == 1
        assert caster.is_running() is True
    finally:
        caster.stop()


def test_ref_counting_starts_on_first_and_stops_on_last_subscriber() -> None:
    source = FakeSource()
    caster = CameraBroadcaster(source)

    caster.subscribe()
    assert _wait_until(lambda: source.start_count == 1)
    assert caster.is_running() is True

    caster.subscribe()  # second subscriber must NOT restart the source
    time.sleep(0.05)
    assert source.start_count == 1
    assert caster.is_running() is True

    caster.unsubscribe()  # still one subscriber -> keep running
    time.sleep(0.05)
    assert caster.is_running() is True
    assert source.stop_count == 0

    caster.unsubscribe()  # last subscriber -> stop
    assert _wait_until(lambda: caster.is_running() is False)
    assert source.stop_count == 1


# --- (d) stop joins the reader thread cleanly (no leak) ---------------------


def test_stop_joins_reader_thread_and_stops_source() -> None:
    source = FakeSource()
    threads_before = threading.active_count()
    caster = CameraBroadcaster(source)
    caster.start()
    assert _wait_until(lambda: source.start_count == 1)
    assert threading.active_count() > threads_before

    caster.stop()

    assert caster.is_running() is False
    assert source.stop_count == 1
    # The reader thread must be joined: active thread count returns to baseline.
    assert _wait_until(lambda: threading.active_count() == threads_before)


def test_stop_is_idempotent() -> None:
    source = FakeSource()
    caster = CameraBroadcaster(source)
    caster.start()
    assert _wait_until(lambda: source.start_count == 1)
    caster.stop()
    caster.stop()  # second stop is a no-op, must not raise
    assert caster.is_running() is False
    assert source.stop_count == 1


def test_reader_survives_source_that_ends_without_crashing() -> None:
    # A source whose frames() ends should leave the broadcaster stoppable and
    # its stored frame readable. With Phase 2 auto-restart, the source is
    # reopened after backoff; we assert a frame is stored, then stop cleanly.
    source = ListSource([b"only-frame"])
    caster = CameraBroadcaster(source, restart_backoff=0.01, sleep=lambda _s: None)
    caster.start()
    try:
        assert _wait_until(lambda: caster.latest() is not None)
        latest = caster.latest()
        assert latest is not None
        assert latest[1] == b"only-frame"
    finally:
        caster.stop()
    assert caster.is_running() is False


# --- Phase 2: auto-restart with backoff + observable errors -----------------


class RestartableSource:
    """A ``FrameSource`` whose ``frames()`` can end or raise per invocation.

    ``behaviours`` is a list applied one per ``frames()`` call: an item is
    either a list of frames to yield then end, or an ``Exception`` to raise
    after yielding nothing. Once exhausted, ``frames()`` blocks (like a healthy
    live source) until ``stop()`` is called.
    """

    def __init__(self, behaviours: list[list[bytes] | Exception]) -> None:
        self._behaviours = list(behaviours)
        self.start_count = 0
        self.stop_count = 0
        self._call = 0
        self._cond = threading.Condition()
        self._stopped = False

    def start(self) -> None:
        with self._cond:
            self.start_count += 1
            self._stopped = False

    def frames(self) -> Iterator[bytes]:
        idx = self._call
        self._call += 1
        if idx < len(self._behaviours):
            behaviour = self._behaviours[idx]
            if isinstance(behaviour, Exception):
                raise behaviour
            yield from behaviour
            return
        # Exhausted the scripted behaviours: act like a healthy source that
        # keeps running until stopped.
        while True:
            with self._cond:
                if self._stopped:
                    return
                self._cond.wait(timeout=0.05)

    def stop(self) -> None:
        with self._cond:
            self.stop_count += 1
            self._stopped = True
            self._cond.notify_all()


def test_source_that_raises_once_triggers_restart_after_backoff() -> None:
    # First frames() raises; the reader must reap (stop) and reopen (start).
    source = RestartableSource([RuntimeError("ffmpeg died")])
    sleeps: list[float] = []
    caster = CameraBroadcaster(
        source,
        restart_backoff=4.0,
        sleep=lambda s: sleeps.append(s),
    )
    caster.start()
    try:
        # start() once initially, then start() again after the restart backoff.
        assert _wait_until(lambda: source.start_count == 2)
        # The old process must be reaped (stop) before reopening.
        assert source.stop_count >= 1
        # Backoff was applied via the injected sleep, using the configured value.
        assert sleeps and sleeps[0] == 4.0
    finally:
        caster.stop()
    assert caster.is_running() is False


def test_source_whose_frames_end_is_reopened() -> None:
    # frames() yields one frame then ends; the reader must restart the source.
    source = RestartableSource([[b"f1"]])
    caster = CameraBroadcaster(
        source,
        restart_backoff=0.0,
        sleep=lambda _s: None,
    )
    caster.start()
    try:
        assert _wait_until(lambda: caster.latest() == (1, b"f1"))
        assert _wait_until(lambda: source.start_count == 2)
        assert source.stop_count >= 1
    finally:
        caster.stop()
    assert caster.is_running() is False


def test_backoff_grows_and_is_capped_on_repeated_failures() -> None:
    # Every frames() call raises: backoff must escalate (no hot-loop) and cap.
    behaviours: list[list[bytes] | Exception] = [RuntimeError(f"boom-{i}") for i in range(6)]
    source = RestartableSource(behaviours)
    sleeps: list[float] = []
    caster = CameraBroadcaster(
        source,
        restart_backoff=4.0,
        max_backoff=16.0,
        sleep=lambda s: sleeps.append(s),
    )
    caster.start()
    try:
        # Wait for several restart cycles to accumulate.
        assert _wait_until(lambda: len(sleeps) >= 4)
    finally:
        caster.stop()
    # Backoff is non-decreasing (escalates to avoid hot-looping a dead device).
    assert sleeps[0] == 4.0
    assert all(b >= a for a, b in zip(sleeps, sleeps[1:], strict=False))
    # And it never exceeds the configured cap.
    assert max(sleeps) <= 16.0


def test_no_restart_after_stop_is_requested() -> None:
    # If frames() ends because we asked it to stop, do NOT restart the source.
    source = RestartableSource([])  # healthy: blocks until stopped
    starts: list[float] = []
    caster = CameraBroadcaster(
        source,
        restart_backoff=0.0,
        sleep=lambda s: starts.append(s),
    )
    caster.start()
    assert _wait_until(lambda: source.start_count == 1)
    caster.stop()
    # After stop, the source is opened exactly once (no restart) and no backoff.
    time.sleep(0.05)
    assert source.start_count == 1
    assert starts == []
    assert caster.is_running() is False
