"""Backend-agnostic MJPEG streaming.

This module knows nothing about a specific camera. It defines the ``FrameSource``
interface (any capture backend implements it) and turns the latest broadcast
JPEG frames into an HTTP ``multipart/x-mixed-replace`` response body — the
classic "MJPEG over HTTP" format that browsers render in a plain ``<img>`` tag.

``mjpeg_stream`` no longer drives a ``FrameSource`` directly. Instead it
subscribes to a shared broadcaster (see ``broadcaster.py``) and sends only the
*latest* frame to each viewer — so a slow client drops stale frames rather than
backing up the pipeline, and a client disconnect never takes the shared camera
down for other viewers.

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


@runtime_checkable
class FrameBroadcaster(Protocol):
    """The subset of ``CameraBroadcaster`` that a viewer stream depends on.

    A viewer *subscribes*, then repeatedly asks for a frame newer than the last
    ``seq`` it saw. Because only the latest frame is stored, a slow viewer skips
    (drops) intermediate frames instead of backing up the pipeline — this is
    what bounds latency. On disconnect the viewer *unsubscribes*; the shared
    capture stays up for any other viewers.

    Declared structurally (not imported) so ``stream.py`` stays free of a
    dependency on ``broadcaster.py`` (which itself imports ``FrameSource`` from
    here).
    """

    def subscribe(self) -> None:
        """Register this viewer (starts capture on the first subscriber)."""

    def unsubscribe(self) -> None:
        """Deregister this viewer (stops capture on the last subscriber)."""

    def is_running(self) -> bool:
        """Whether the shared capture is active (used to tell stall from stop)."""

    def wait_for_newer(
        self, last_seq: int, timeout: float | None = None
    ) -> tuple[int, bytes] | None:
        """Block for a frame with ``seq > last_seq``; ``None`` if stopped/timed out."""


def _wrap_frame(frame: bytes) -> bytes:
    """Wrap one JPEG frame as a single ``multipart/x-mixed-replace`` part."""
    return (
        (
            f"--{BOUNDARY}\r\nContent-Type: image/jpeg\r\nContent-Length: {len(frame)}\r\n\r\n"
        ).encode()
        + frame
        + b"\r\n"
    )


def mjpeg_stream(broadcaster: FrameBroadcaster) -> Iterator[bytes]:
    """Yield an HTTP ``multipart/x-mixed-replace`` body from a broadcaster.

    Subscribes to the shared ``broadcaster`` (no per-connection capture), then
    yields the *latest* JPEG frame as it arrives, wrapped with the multipart
    boundary and headers. A slow client simply skips stale frames — only the
    newest frame is ever sent, so latency stays bounded. Always unsubscribes
    when iteration ends (error, client disconnect, or broadcaster shutdown), so
    the shared camera stays up for other viewers.
    """
    broadcaster.subscribe()
    try:
        last_seq = 0
        while True:
            # Bounded wait so a viewer thread never blocks forever if frames
            # stall; on timeout we re-check liveness rather than ending. A None
            # result means "no newer frame yet" OR "stopped" — distinguish via
            # is_running() so a transient stall does not end the stream.
            result = broadcaster.wait_for_newer(last_seq, timeout=1.0)
            if result is None:
                if not broadcaster.is_running():
                    # Broadcaster stopped (last subscriber left / shutdown).
                    return
                continue  # just a stall; keep waiting for the next frame
            last_seq, frame = result
            yield _wrap_frame(frame)
    finally:
        broadcaster.unsubscribe()


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
