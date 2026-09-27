"""Video package — live MJPEG streaming with swappable camera backends.

Design philosophy — the capture layer is an interface, not a camera
--------------------------------------------------------------------
Cameras differ in how you talk to them (USB/UVC via ffmpeg+V4L2; CSI via
libcamera; ...), but the rest of the app should not care. So capture is modelled
as a small ``FrameSource`` interface — ``start() / frames() / stop()`` yielding
JPEG frames — and everything above it (the MJPEG stream framing, the
``/video_feed`` route, the page) depends only on that interface.

- **Backends are swappable and isolated.** Each concrete backend lives in
  ``sources/`` and is the *only* place that knows about a specific camera or
  library (ffmpeg/V4L2, libcamera, ...). The Brio uses ``FfmpegV4L2Source``
  (MJPEG passthrough — low CPU); the future OV5647 IR camera will use
  ``LibcameraSource`` (currently a stub).
- **Selection is by configuration, not import.** ``get_frame_source()`` picks
  the backend from ``BABYMONITOR_CAMERA`` (``usb`` default, ``csi`` later).
  Callers never import a backend directly.
- **Adding a camera = one new file + a config value**, not a rewrite. Swapping
  the Brio for the CSI IR camera means implementing ``sources/libcamera.py`` and
  setting ``BABYMONITOR_CAMERA=csi``; ``stream.py`` and the web layer are
  untouched. See ``docs/CAMERA_MIC_RUNBOOK.md`` for the hardware caveats.

Public interface. Callers use:
- ``FrameSource``   — the capture-backend interface (protocol).
- ``get_frame_source`` — factory returning the configured backend.
- ``CameraBroadcaster`` — single app-owned capture (one ffmpeg) that stores the
  latest frame and broadcasts it to many viewers, dropping stale frames. The
  app builds one and every ``/video_feed`` request subscribes to it.
- ``mjpeg_stream``  — turn a broadcaster *subscription* into an HTTP multipart
  MJPEG body (latest-frame only; unsubscribes on disconnect).
- ``BOUNDARY``, ``MJPEG_CONTENT_TYPE`` — for building the HTTP response.

Concrete backends (``sources/``) are internal; select them via configuration
through ``get_frame_source`` rather than importing them directly.
"""

from __future__ import annotations

from app.video.broadcaster import CameraBroadcaster
from app.video.factory import get_frame_source
from app.video.stream import BOUNDARY, FrameSource, mjpeg_stream

# The Content-Type header value for an MJPEG-over-HTTP response.
MJPEG_CONTENT_TYPE = f"multipart/x-mixed-replace; boundary={BOUNDARY}"

__all__ = [
    "FrameSource",
    "mjpeg_stream",
    "get_frame_source",
    "CameraBroadcaster",
    "BOUNDARY",
    "MJPEG_CONTENT_TYPE",
]
