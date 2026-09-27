"""Unit tests for the video streaming layer (hardware mocked).

Covers three units, none of which touch a real camera:
- ``mjpeg_stream``: subscribes to a ``CameraBroadcaster`` and wraps its latest
  frames in a multipart/x-mixed-replace HTTP body (dropping stale frames).
- ``FrameSource`` contract: a fake source still satisfies the protocol.
- ``iter_mjpeg_frames``: splits a raw MJPEG byte stream into JPEG frames on
  the SOI (0xFFD8) / EOI (0xFFD9) markers.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator

from app.video import BOUNDARY, FrameSource, mjpeg_stream
from app.video.broadcaster import CameraBroadcaster
from app.video.stream import iter_mjpeg_frames

# A tiny valid-ish JPEG: SOI ... EOI. Content between markers is irrelevant here.
JPEG_A = b"\xff\xd8" + b"AAAA" + b"\xff\xd9"
JPEG_B = b"\xff\xd8" + b"BBBB" + b"\xff\xd9"


class FakeSource:
    """A FrameSource that yields a fixed list of frames (no hardware)."""

    def __init__(self, frames: list[bytes]) -> None:
        self._frames = frames
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def frames(self) -> Iterator[bytes]:
        yield from self._frames

    def stop(self) -> None:
        self.stopped = True


class PushSource:
    """A controllable FrameSource whose frames are pushed by the test."""

    def __init__(self) -> None:
        self.start_count = 0
        self.stop_count = 0
        self._queue: list[bytes] = []
        self._cond = threading.Condition()
        self._stopped = False

    def start(self) -> None:
        with self._cond:
            self.start_count += 1
            self._stopped = False

    def push(self, frame: bytes) -> None:
        with self._cond:
            self._queue.append(frame)
            self._cond.notify_all()

    def frames(self) -> Iterator[bytes]:
        while True:
            with self._cond:
                while not self._queue and not self._stopped:
                    self._cond.wait(timeout=0.5)
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


def _wait_until(predicate: object, timeout: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():  # type: ignore[operator]
            return True
        time.sleep(0.005)
    return False


def test_fake_source_satisfies_protocol() -> None:
    src: FrameSource = FakeSource([JPEG_A])
    assert isinstance(src, FrameSource)


# --- mjpeg_stream (broadcaster subscription) --------------------------------


def test_mjpeg_stream_wraps_each_frame_with_boundary_and_headers() -> None:
    source = PushSource()
    caster = CameraBroadcaster(source)
    caster.subscribe()
    try:
        gen = mjpeg_stream(caster)
        parts: list[bytes] = []
        # Interleave pushes with reads: because the broadcaster keeps only the
        # LATEST frame, a subscriber must read each frame before the next is
        # pushed to observe both (this is the drop-stale contract).
        for frame in (JPEG_A, JPEG_B):
            source.push(frame)
            parts.append(next(gen))
        gen.close()
    finally:
        caster.unsubscribe()

    blob = b"".join(parts)
    # Boundary appears once per frame.
    assert blob.count(BOUNDARY.encode()) == 2
    # Each part declares the JPEG content type and length.
    assert b"Content-Type: image/jpeg" in blob
    assert b"Content-Length: " + str(len(JPEG_A)).encode() in blob
    # Both raw JPEG payloads are present (each read before the next push).
    assert JPEG_A in blob
    assert JPEG_B in blob


def test_mjpeg_stream_subscribes_and_unsubscribes_the_broadcaster() -> None:
    source = PushSource()
    caster = CameraBroadcaster(source)
    source_frame = JPEG_A

    def _drive() -> list[bytes]:
        gen = mjpeg_stream(caster)
        first = next(gen)  # subscribes, then yields the first frame
        gen.close()  # closing the generator must unsubscribe (finally)
        return [first]

    # Push a frame slightly after the consumer subscribes.
    def _feed() -> None:
        assert _wait_until(lambda: caster.is_running())
        source.push(source_frame)

    feeder = threading.Thread(target=_feed)
    feeder.start()
    out = _drive()
    feeder.join(timeout=2.0)

    assert source_frame in b"".join(out)
    # After the single consumer disconnects, the last-unsubscribe stops capture.
    assert _wait_until(lambda: not caster.is_running())
    assert source.stop_count >= 1


def test_mjpeg_stream_drops_stale_frames_for_a_slow_consumer() -> None:
    source = PushSource()
    caster = CameraBroadcaster(source)
    caster.subscribe()
    try:
        for i in range(50):
            source.push(f"\xff\xd8{i:03d}\xff\xd9".encode("latin-1"))
        last = f"\xff\xd8{49:03d}\xff\xd9".encode("latin-1")
        assert _wait_until(lambda: caster.latest() == (50, last))

        gen = mjpeg_stream(caster)
        first_part = next(gen)
        gen.close()
    finally:
        caster.unsubscribe()

    # A slow consumer that reads once gets the LATEST frame, not frame 0.
    assert last in first_part
    assert b"\xff\xd8000\xff\xd9" not in first_part


# --- iter_mjpeg_frames ------------------------------------------------------


def test_iter_mjpeg_frames_splits_concatenated_jpegs() -> None:
    raw = iter([JPEG_A + JPEG_B])  # both frames in one chunk
    frames = list(iter_mjpeg_frames(raw))
    assert frames == [JPEG_A, JPEG_B]


def test_iter_mjpeg_frames_reassembles_across_chunk_boundaries() -> None:
    # A frame split across two byte chunks must still be reassembled.
    mid = len(JPEG_A) // 2
    b_mid = len(JPEG_B) // 2
    raw = iter([JPEG_A[:mid], JPEG_A[mid:] + JPEG_B[:b_mid], JPEG_B[b_mid:]])
    frames = list(iter_mjpeg_frames(raw))
    assert frames == [JPEG_A, JPEG_B]


def test_iter_mjpeg_frames_ignores_leading_garbage_before_first_soi() -> None:
    raw = iter([b"junk-bytes" + JPEG_A])
    frames = list(iter_mjpeg_frames(raw))
    assert frames == [JPEG_A]
