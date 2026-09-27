"""Tests for the frame-source factory (config-driven backend + right-sizing)."""

from __future__ import annotations

import pytest

from app.video.factory import get_frame_source
from app.video.sources.ffmpeg_v4l2 import FfmpegV4L2Source


def test_usb_backend_defaults_are_right_sized(monkeypatch: pytest.MonkeyPatch) -> None:
    # Clear any env so we observe the built-in defaults.
    for var in (
        "BABYMONITOR_CAMERA",
        "BABYMONITOR_VIDEO_WIDTH",
        "BABYMONITOR_VIDEO_HEIGHT",
        "BABYMONITOR_VIDEO_FPS",
        "BABYMONITOR_VIDEO_DEVICE",
    ):
        monkeypatch.delenv(var, raising=False)

    src = get_frame_source()
    assert isinstance(src, FfmpegV4L2Source)
    assert src.device == "/dev/video0"
    assert (src.width, src.height) == (1280, 720)
    # Default fps lowered to 10 to cut bitrate for weak links (Phase 6).
    assert src.fps == 10


def test_usb_backend_reads_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BABYMONITOR_CAMERA", "usb")
    monkeypatch.setenv("BABYMONITOR_VIDEO_WIDTH", "640")
    monkeypatch.setenv("BABYMONITOR_VIDEO_HEIGHT", "480")
    monkeypatch.setenv("BABYMONITOR_VIDEO_FPS", "15")
    monkeypatch.setenv("BABYMONITOR_VIDEO_DEVICE", "/dev/video2")

    src = get_frame_source()
    assert isinstance(src, FfmpegV4L2Source)
    assert src.device == "/dev/video2"
    assert (src.width, src.height, src.fps) == (640, 480, 15)


def test_unknown_backend_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BABYMONITOR_CAMERA", "bogus")
    with pytest.raises(ValueError, match="Unknown BABYMONITOR_CAMERA"):
        get_frame_source()
