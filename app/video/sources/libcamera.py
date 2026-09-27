"""CSI camera frame source (libcamera) — STUB for the future IR camera.

Placeholder backend for a CSI camera such as the OV5647 night-vision module
(connected via the CSI ribbon, not USB). Unlike UVC webcams, CSI cameras use
the libcamera stack (``rpicam-vid`` / ``picamera2``) and do not emit MJPEG
natively, so this backend will encode frames to JPEG when implemented.

Not implemented yet: the project runs the Brio (USB) for the POC. This module
exists so the swappable-backend seam is visible now; fill it in when the CSI
camera is fitted. See ``docs/CAMERA_MIC_RUNBOOK.md`` (IR-camera section) and the
night-vision task in ``plans/PLAN.md``.
"""

from __future__ import annotations

from collections.abc import Iterator


class LibcameraSource:
    """CSI/libcamera frame source. Placeholder — raises until implemented."""

    def __init__(self, width: int = 1280, height: int = 720, fps: int = 15) -> None:
        self.width = width
        self.height = height
        self.fps = fps

    def start(self) -> None:
        raise NotImplementedError(
            "CSI/libcamera backend is not implemented yet. The POC uses the USB "
            "backend (BABYMONITOR_CAMERA=usb). Implement this when the OV5647 "
            "camera is fitted."
        )

    def frames(self) -> Iterator[bytes]:
        raise NotImplementedError
        yield b""  # pragma: no cover  (marks this as a generator for typing)

    def stop(self) -> None:
        return
