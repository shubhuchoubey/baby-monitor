"""Internal hardware-detection module.

Wraps V4L2 (camera) and ALSA (microphone) enumeration behind a small,
testable interface. The rest of the app depends on the public names re-exported
from ``app.detection`` (see ``__init__.py``), not on this module directly.

Detection strategy (read-only; no device is opened here):
- Camera: parse ``v4l2-ctl --list-devices`` to find the group whose header
  matches the name hint (e.g. "BRIO"), and take its first ``/dev/video*`` node
  as the capture node.
- Microphone: parse ``arecord -l`` for a capture device whose description
  matches the name hint, and derive its ``plughw:<card>,<device>`` ALSA id.

``_run`` is the single subprocess seam; unit tests monkeypatch it so the suite
runs without a Pi or a Brio attached.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass

# External command names (hoisted to avoid duplicated string literals — Sonar S1192).
_ARECORD = "arecord"
_V4L2_CTL = "v4l2-ctl"
_FFMPEG = "ffmpeg"

__all__ = [
    "CameraDevice",
    "MicDevice",
    "DetectionResult",
    "detect_devices",
    "parse_v4l2_devices",
    "parse_arecord",
    "capture_test_frame",
    "capture_test_audio",
]


@dataclass(frozen=True)
class CameraDevice:
    """A detected video-capture device."""

    device: str  # e.g. "/dev/video0"
    name: str  # e.g. "Logitech BRIO (usb-...)"


@dataclass(frozen=True)
class MicDevice:
    """A detected audio-capture device."""

    card: int  # ALSA card number, e.g. 3
    device: int  # ALSA device number, e.g. 0
    alsa_id: str  # e.g. "plughw:3,0"
    name: str  # e.g. "BRIO [Logitech BRIO]"


@dataclass(frozen=True)
class DetectionResult:
    """Outcome of a detection pass."""

    camera: CameraDevice | None
    mic: MicDevice | None

    @property
    def ok(self) -> bool:
        """True when both a camera and a microphone were found."""
        return self.camera is not None and self.mic is not None


def _run(cmd: list[str]) -> str:
    """Run a command and return its stdout (subprocess seam).

    Returns an empty string if the command is missing or fails; detection then
    reports the device as absent rather than raising.
    """
    try:
        # Safe: fixed argument list, no shell, no user-interpolated input.
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return ""
    return proc.stdout or ""


def parse_v4l2_devices(text: str, name_hint: str) -> CameraDevice | None:
    """Find the capture node of the device whose header matches ``name_hint``.

    ``v4l2-ctl --list-devices`` groups nodes under an unindented header line;
    the node paths follow, indented. We match the header against the hint and
    return its first ``/dev/video*`` node (the capture node on UVC webcams).
    """
    hint = name_hint.lower()
    current_header: str | None = None
    for raw_line in text.splitlines():
        if not raw_line.strip():
            continue
        if not raw_line[0].isspace():
            # Unindented line: a device group header.
            current_header = raw_line.strip().rstrip(":")
            continue
        node = raw_line.strip()
        if (
            current_header is not None
            and hint in current_header.lower()
            and node.startswith("/dev/video")
        ):
            return CameraDevice(device=node, name=current_header)
    return None


# Linear parsing of an `arecord -l` capture line, which looks like:
#     card 3: BRIO [Logitech BRIO], device 0: USB Audio [USB Audio]
# Simple anchored regexes (digits only, no variable-length groups) extract the
# card and device numbers; the name is taken by splitting on the fixed
# ", device " delimiter. This avoids any regex backtracking (Sonar S8786).
_ARECORD_CARD_RE = re.compile(r"^card\s+(\d+):\s+")
_ARECORD_DEVICE_RE = re.compile(r"^(\d+):")
_DEVICE_DELIM = ", device "


def parse_arecord(text: str, name_hint: str) -> MicDevice | None:
    """Find a capture device whose line matches ``name_hint`` in ``arecord -l``.

    Matching lines look like:
        card 3: BRIO [Logitech BRIO], device 0: USB Audio [USB Audio]
    """
    hint = name_hint.lower()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        card_match = _ARECORD_CARD_RE.match(line)
        if card_match is None or _DEVICE_DELIM not in line:
            continue
        if hint not in line.lower():
            continue

        # Everything between "card N: " and ", device ..." is the device name.
        after_card = line[card_match.end() :]
        name, _, after_delim = after_card.partition(_DEVICE_DELIM)
        device_match = _ARECORD_DEVICE_RE.match(after_delim)
        if device_match is None:
            continue

        card = int(card_match.group(1))
        device = int(device_match.group(1))
        return MicDevice(
            card=card,
            device=device,
            alsa_id=f"plughw:{card},{device}",
            name=name.strip(),
        )
    return None


def detect_devices(name_hint: str = "BRIO") -> DetectionResult:
    """Detect the camera and microphone matching ``name_hint``.

    Read-only: enumerates devices via ``v4l2-ctl`` and ``arecord`` but does not
    open or capture from them.
    """
    camera = parse_v4l2_devices(_run([_V4L2_CTL, "--list-devices"]), name_hint)
    mic = parse_arecord(_run([_ARECORD, "-l"]), name_hint)
    return DetectionResult(camera=camera, mic=mic)


def _run_status(cmd: list[str], timeout: float) -> bool:
    """Run a command for its side effect; return True on success (exit 0).

    Used by the capture helpers. Never raises: a missing tool, timeout, or
    non-zero exit returns False so the diagnostic degrades gracefully.
    """
    try:
        # Safe: fixed argument list, no shell, no user-interpolated input.
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


def capture_test_frame(camera: CameraDevice, out_path: str, timeout: float = 15.0) -> bool:
    """Best-effort: grab a single JPEG frame from ``camera`` using ffmpeg.

    Returns True if a non-empty file was written. Does not raise.
    """
    ok = _run_status(
        [
            _FFMPEG,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "v4l2",
            "-i",
            camera.device,
            "-frames:v",
            "1",
            "-y",
            out_path,
        ],
        timeout=timeout,
    )
    return ok and _nonempty(out_path)


def capture_test_audio(
    mic: MicDevice, out_path: str, seconds: int = 1, timeout: float = 15.0
) -> bool:
    """Best-effort: record a short WAV clip from ``mic`` using arecord.

    Returns True if a non-empty file was written. Does not raise.
    """
    ok = _run_status(
        [
            _ARECORD,
            "-D",
            mic.alsa_id,
            "-d",
            str(seconds),
            "-f",
            "cd",
            out_path,
        ],
        timeout=timeout,
    )
    return ok and _nonempty(out_path)


def _nonempty(path: str) -> bool:
    try:
        return os.path.getsize(path) > 0
    except OSError:
        return False
