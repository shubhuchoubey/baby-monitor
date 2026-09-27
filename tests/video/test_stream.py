"""Unit tests for the video package (hardware mocked).

Covers three units, none of which touch a real camera:
- ``mjpeg_stream``: wraps JPEG frames in a multipart/x-mixed-replace stream.
- ``FrameSource`` contract: a fake source drives the stream generator.
- ``iter_mjpeg_frames``: splits a raw MJPEG byte stream into JPEG frames on
  the SOI (0xFFD8) / EOI (0xFFD9) markers.
"""

from __future__ import annotations

from collections.abc import Iterator

from app.video import BOUNDARY, FrameSource, mjpeg_stream
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


def test_fake_source_satisfies_protocol() -> None:
    src: FrameSource = FakeSource([JPEG_A])
    assert isinstance(src, FrameSource)


# --- mjpeg_stream -----------------------------------------------------------


def test_mjpeg_stream_wraps_each_frame_with_boundary_and_headers() -> None:
    src = FakeSource([JPEG_A, JPEG_B])
    chunks = list(mjpeg_stream(src))
    blob = b"".join(chunks)

    # Boundary appears once per frame.
    assert blob.count(BOUNDARY.encode()) == 2
    # Each part declares the JPEG content type and length.
    assert b"Content-Type: image/jpeg" in blob
    assert b"Content-Length: " + str(len(JPEG_A)).encode() in blob
    # The raw JPEG payloads are present.
    assert JPEG_A in blob
    assert JPEG_B in blob


def test_mjpeg_stream_starts_and_stops_the_source() -> None:
    src = FakeSource([JPEG_A])
    list(mjpeg_stream(src))
    assert src.started is True
    assert src.stopped is True


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
