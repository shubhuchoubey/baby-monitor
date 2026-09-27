"""Hardware detection package.

Public interface for detecting the camera and microphone. Callers import from
``app.detection``; the enumeration/parsing internals live in ``devices`` and
should not be imported directly by other packages.
"""

from __future__ import annotations

from app.detection.devices import (
    CameraDevice,
    DetectionResult,
    MicDevice,
    capture_test_audio,
    capture_test_frame,
    detect_devices,
)

__all__ = [
    "CameraDevice",
    "MicDevice",
    "DetectionResult",
    "detect_devices",
    "capture_test_frame",
    "capture_test_audio",
]
