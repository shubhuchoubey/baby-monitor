"""Unit tests for the hardware detection module.

Hardware is mocked: we feed the parsers the exact text shapes emitted by
`v4l2-ctl --list-devices` and `arecord -l` on the Pi, so the suite runs on the
dev machine (macOS) with no Pi or Brio attached.
"""

from __future__ import annotations

from app.detection import CameraDevice, MicDevice, detect_devices
from app.detection.devices import parse_arecord, parse_v4l2_devices

# --- Real output samples captured from the Pi (Logitech BRIO) ---------------

V4L2_LIST_DEVICES = """\
bcm2835-isp (platform:bcm2835-isp):
\t/dev/video13
\t/dev/video14

Logitech BRIO (usb-0000:01:00.0-1):
\t/dev/video0
\t/dev/video1
\t/dev/video2
\t/dev/video3
\t/dev/media4

bcm2835-codec (vchiq:bcm2835-codec):
\t/dev/media1
"""

ARECORD_L = """\
**** List of CAPTURE Hardware Devices ****
card 3: BRIO [Logitech BRIO], device 0: USB Audio [USB Audio]
  Subdevices: 1/1
  Subdevice #0: subdevice #0
"""


# --- parse_v4l2_devices -----------------------------------------------------


def test_parse_v4l2_finds_brio_capture_node() -> None:
    cam = parse_v4l2_devices(V4L2_LIST_DEVICES, name_hint="BRIO")
    assert cam is not None
    # The first /dev/video* node of the Brio group is the capture node.
    assert cam.device == "/dev/video0"
    assert "BRIO" in cam.name


def test_parse_v4l2_returns_none_when_camera_absent() -> None:
    text = "bcm2835-isp (platform:bcm2835-isp):\n\t/dev/video13\n"
    assert parse_v4l2_devices(text, name_hint="BRIO") is None


# --- parse_arecord ----------------------------------------------------------


def test_parse_arecord_finds_brio_mic() -> None:
    mic = parse_arecord(ARECORD_L, name_hint="BRIO")
    assert mic is not None
    assert mic.card == 3
    assert mic.device == 0
    assert mic.alsa_id == "plughw:3,0"
    assert "BRIO" in mic.name


def test_parse_arecord_returns_none_when_mic_absent() -> None:
    text = "**** List of CAPTURE Hardware Devices ****\n"
    assert parse_arecord(text, name_hint="BRIO") is None


# --- detect_devices (public interface, subprocess mocked) -------------------


def test_detect_devices_reports_camera_and_mic(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def fake_run(cmd: list[str]) -> str:
        if cmd[0] == "v4l2-ctl":
            return V4L2_LIST_DEVICES
        if cmd[0] == "arecord":
            return ARECORD_L
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr("app.detection.devices._run", fake_run)

    result = detect_devices(name_hint="BRIO")
    assert isinstance(result.camera, CameraDevice)
    assert isinstance(result.mic, MicDevice)
    assert result.camera.device == "/dev/video0"
    assert result.mic.alsa_id == "plughw:3,0"
    assert result.ok is True


def test_detect_devices_ok_false_when_nothing_found(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("app.detection.devices._run", lambda cmd: "")
    result = detect_devices(name_hint="BRIO")
    assert result.camera is None
    assert result.mic is None
    assert result.ok is False
