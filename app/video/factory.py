"""Frame-source factory.

Selects a camera backend from configuration so the rest of the app never
hard-codes a specific camera. Backend is chosen by the ``BABYMONITOR_CAMERA``
env var: ``usb`` (default, Logitech Brio via ffmpeg/V4L2) or ``csi`` (OV5647 via
libcamera — not implemented yet).
"""

from __future__ import annotations

import os

from app.video.sources.ffmpeg_v4l2 import FfmpegV4L2Source
from app.video.stream import FrameSource


def get_frame_source() -> FrameSource:
    """Return a ``FrameSource`` for the configured camera backend."""
    backend = os.environ.get("BABYMONITOR_CAMERA", "usb").lower()
    width = int(os.environ.get("BABYMONITOR_VIDEO_WIDTH", "1280"))
    height = int(os.environ.get("BABYMONITOR_VIDEO_HEIGHT", "720"))
    fps = int(os.environ.get("BABYMONITOR_VIDEO_FPS", "15"))

    if backend == "usb":
        device = os.environ.get("BABYMONITOR_VIDEO_DEVICE", "/dev/video0")
        return FfmpegV4L2Source(device=device, width=width, height=height, fps=fps)
    if backend == "csi":
        # Imported lazily so the unimplemented stub never affects the USB path.
        from app.video.sources.libcamera import LibcameraSource

        return LibcameraSource(width=width, height=height, fps=fps)
    raise ValueError(f"Unknown BABYMONITOR_CAMERA={backend!r}; expected 'usb' or 'csi'.")
