"""Backend-agnostic MJPEG streaming.

This module knows nothing about a specific camera. It defines the ``FrameSource``
interface (any capture backend implements it) and turns a stream of JPEG frames
into an HTTP ``multipart/x-mixed-replace`` response body — the classic
"MJPEG over HTTP" format that browsers render in a plain ``<img>`` tag.

``iter_mjpeg_frames`` is a helper for backends whose underlying tool emits a
continuous MJPEG byte stream (e.g. ffmpeg): it splits that stream into discrete
JPEG frames on the SOI/EOI markers, reassembling across chunk boundaries.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Protocol, runtime_checkable

# Multipart boundary token used to separate JPEG frames in the HTTP stream.
BOUNDARY = "babymonitorframe"

# JPEG markers: Start Of Image / End Of Image.
_SOI = b"\xff\xd8"
_EOI = b"\xff\xd9"


@runtime_checkable
class FrameSource(Protocol):
    """A source of JPEG frames from a camera backend.

    Implementations wrap a specific capture mechanism (USB/V4L2, CSI/libcamera,
    ...) behind this interface so the streaming and web layers stay
    backend-agnostic.
    """

    def start(self) -> None:
        """Begin capturing (open the device / spawn the capture process)."""

    def frames(self) -> Iterator[bytes]:
        """Yield complete JPEG frames until the source is exhausted/stopped."""

    def stop(self) -> None:
        """Stop capturing and release resources."""


def mjpeg_stream(source: FrameSource) -> Iterator[bytes]:
    """Yield an HTTP ``multipart/x-mixed-replace`` body from ``source``.

    Starts the source, wraps each JPEG frame with the multipart boundary and
    headers, and always stops the source when iteration ends (even on error or
    client disconnect).
    """
    source.start()
    try:
        for frame in source.frames():
            yield (
                (
                    f"--{BOUNDARY}\r\n"
                    f"Content-Type: image/jpeg\r\n"
                    f"Content-Length: {len(frame)}\r\n\r\n"
                ).encode()
                + frame
                + b"\r\n"
            )
    finally:
        source.stop()


def iter_mjpeg_frames(chunks: Iterable[bytes]) -> Iterator[bytes]:
    """Split a raw MJPEG byte stream into individual JPEG frames.

    Accepts an iterable of arbitrary byte chunks (as produced by reading a
    subprocess pipe) and yields one ``bytes`` object per complete JPEG frame,
    delimited by SOI (0xFFD8) ... EOI (0xFFD9). Bytes before the first SOI are
    discarded; a partial trailing frame is not yielded.
    """
    buffer = bytearray()
    for chunk in chunks:
        buffer.extend(chunk)
        while True:
            start = buffer.find(_SOI)
            if start == -1:
                # No frame start yet; drop everything (leading garbage).
                buffer.clear()
                break
            if start > 0:
                # Discard bytes before the frame start.
                del buffer[:start]
            end = buffer.find(_EOI, len(_SOI))
            if end == -1:
                break  # frame not complete yet; wait for more chunks
            end += len(_EOI)
            yield bytes(buffer[:end])
            del buffer[:end]
