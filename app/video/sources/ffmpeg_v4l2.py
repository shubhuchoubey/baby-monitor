"""USB webcam frame source (ffmpeg + V4L2).

Backend for UVC webcams such as the Logitech Brio. The Brio outputs MJPEG
natively, so ffmpeg copies the MJPEG stream straight from the device to stdout
with no re-encoding (low CPU on the Pi 4). The raw stream is split into JPEG
frames by ``iter_mjpeg_frames``.

This is the only module that knows about ffmpeg/V4L2 or ``/dev/video*``; the
rest of the app depends on the ``FrameSource`` interface.
"""

from __future__ import annotations

import io
import subprocess
from collections.abc import Iterator

from app.video.stream import iter_mjpeg_frames

_FFMPEG = "ffmpeg"
_READ_CHUNK = 65536


class FfmpegV4L2Source:
    """Capture MJPEG frames from a V4L2 device via an ffmpeg subprocess."""

    def __init__(
        self,
        device: str = "/dev/video0",
        width: int = 1280,
        height: int = 720,
        fps: int = 15,
    ) -> None:
        self.device = device
        self.width = width
        self.height = height
        self.fps = fps
        self._proc: subprocess.Popen[bytes] | None = None

    def _command(self) -> list[str]:
        return [
            _FFMPEG,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "v4l2",
            "-input_format",
            "mjpeg",
            "-video_size",
            f"{self.width}x{self.height}",
            "-framerate",
            str(self.fps),
            "-i",
            self.device,
            "-c:v",
            "copy",  # MJPEG passthrough — no re-encode
            "-f",
            "mjpeg",
            "pipe:1",
        ]

    def start(self) -> None:
        if self._proc is not None:
            return
        # Safe: fixed argument list, no shell, no user-interpolated input.
        self._proc = subprocess.Popen(
            self._command(),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )

    def frames(self) -> Iterator[bytes]:
        if self._proc is None or self._proc.stdout is None:
            return
        # Popen with stdout=PIPE (binary) yields a BufferedReader, which exposes
        # read1(); narrow the type so mypy accepts it.
        stdout = self._proc.stdout
        assert isinstance(stdout, io.BufferedReader)

        def read_chunks() -> Iterator[bytes]:
            # read1() returns whatever is currently available in one syscall
            # (up to _READ_CHUNK) instead of blocking until the buffer is full,
            # so JPEG frames flow as ffmpeg produces them.
            while True:
                chunk = stdout.read1(_READ_CHUNK)
                if not chunk:
                    return  # ffmpeg exited / pipe closed
                yield chunk

        yield from iter_mjpeg_frames(read_chunks())

    def stop(self) -> None:
        if self._proc is None:
            return
        proc = self._proc
        self._proc = None
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
