"""CLI diagnostic: detect the Brio camera + mic and optionally capture samples.

Usage (on the Pi):
    python -m app.detection                  # detect + capture test frame/audio
    python -m app.detection --no-capture     # detection only (read-only)
    python -m app.detection --name-hint BRIO # match a different device name
    python -m app.detection --out-dir DIR    # where to write samples

By default, captured samples are written to a private, user-owned temporary
directory (created with 0700 permissions) rather than a world-writable location
such as ``/tmp``. Pass ``--out-dir`` to choose your own directory.

Exit code is 0 when both a camera and a microphone are detected, else 1, so the
command is usable as a health gate in scripts.
"""

from __future__ import annotations

import argparse
import sys
import tempfile

from app.detection import (
    DetectionResult,
    capture_test_audio,
    capture_test_frame,
    detect_devices,
)

_SEP = "=" * 40


def _report_detection(result: DetectionResult, name_hint: str) -> None:
    """Print the detected camera and mic (or NOT FOUND)."""
    if result.camera is not None:
        print(f"Camera : {result.camera.device}  ({result.camera.name})")
    else:
        print(f"Camera : NOT FOUND (hint: {name_hint!r})")

    if result.mic is not None:
        print(f"Mic    : {result.mic.alsa_id}  ({result.mic.name})")
    else:
        print(f"Mic    : NOT FOUND (hint: {name_hint!r})")


def _report_captures(result: DetectionResult, out_dir: str) -> None:
    """Capture a test frame and audio clip for whatever was detected."""
    print("-" * 40)
    if result.camera is not None:
        frame_path = f"{out_dir}/brio_test.jpg"
        ok = capture_test_frame(result.camera, frame_path)
        print(f"Frame  : {'OK -> ' + frame_path if ok else 'capture failed'}")
    if result.mic is not None:
        audio_path = f"{out_dir}/brio_test.wav"
        ok = capture_test_audio(result.mic, audio_path)
        print(f"Audio  : {'OK -> ' + audio_path if ok else 'capture failed'}")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="app.detection")
    parser.add_argument("--name-hint", default="BRIO", help="device name to match")
    parser.add_argument(
        "--out-dir",
        default=None,
        help="dir for captured samples (default: a private temp dir)",
    )
    parser.add_argument(
        "--no-capture",
        action="store_true",
        help="detection only; do not open the devices to capture samples",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    result = detect_devices(name_hint=args.name_hint)

    print("Baby Monitor — hardware detection")
    print(_SEP)
    _report_detection(result, args.name_hint)

    if not args.no_capture:
        # Default to a private (0700) temp dir rather than a world-writable one.
        out_dir = args.out_dir or tempfile.mkdtemp(prefix="babymonitor-")
        _report_captures(result, out_dir)

    print(_SEP)
    print(f"Result : {'OK' if result.ok else 'INCOMPLETE'}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
