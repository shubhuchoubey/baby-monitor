"""Entry point for running the Baby Monitor dev server.

Binds to 0.0.0.0 so the page is reachable from other devices on the same
WiFi network (e.g. a phone), not just localhost on the Pi.

Usage:
    python -m app.main
"""

from __future__ import annotations

import logging
import os

from app import create_app

app = create_app()


def main() -> None:
    # Configure logging so app-level records — notably ffmpeg capture errors
    # (app.video.sources.ffmpeg_v4l2) and broadcaster auto-restarts
    # (app.video.broadcaster) — are written to stderr, which start.sh redirects
    # into server.log. Without this, only Werkzeug request lines would appear.
    logging.basicConfig(
        level=os.environ.get("BABYMONITOR_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    host = os.environ.get("BABYMONITOR_HOST", "0.0.0.0")
    port = int(os.environ.get("BABYMONITOR_PORT", "8000"))
    # debug is off by default; enable with BABYMONITOR_DEBUG=1 during development.
    debug = os.environ.get("BABYMONITOR_DEBUG", "0") == "1"
    # threaded=True lets the long-lived MJPEG stream run without blocking other
    # requests (status page, health check, a second viewer), and lets a client
    # disconnect promptly trigger the stream generator's cleanup.
    app.run(host=host, port=port, debug=debug, threaded=True)


if __name__ == "__main__":
    main()
