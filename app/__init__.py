"""Baby Monitor Flask application.

Serves the status page, a health check, and the live MJPEG video feed.

Video capture is **shared**: the app owns a single :class:`CameraBroadcaster`
(one ffmpeg opener for the whole process) built from the configured
``FrameSource``. The ``/video_feed`` route *subscribes* to that broadcaster per
request rather than opening a camera per connection — so a second viewer or a
browser reconnect never collides on the single-opener Brio, and a slow WiFi
client drops stale frames instead of backing up the pipeline. A client
disconnect simply unsubscribes; the camera stays up for any other viewers. See
``plans/VIDEO_STREAM_DEBUG.md`` for the confirmed root causes.
"""

from __future__ import annotations

from flask import Flask, Response, render_template

from app.video import (
    MJPEG_CONTENT_TYPE,
    CameraBroadcaster,
    get_frame_source,
    mjpeg_stream,
)


def create_app(broadcaster: CameraBroadcaster | None = None) -> Flask:
    """Application factory. Returns a configured Flask app.

    ``broadcaster`` is the single app-owned capture broadcaster. It is created
    once here (wrapping the configured ``FrameSource``) and stored on the app
    object as ``app.camera_broadcaster``; every ``/video_feed`` request
    subscribes to this same instance. Tests may inject a broadcaster wrapping a
    fake source.
    """
    app = Flask(__name__)

    if broadcaster is None:
        broadcaster = CameraBroadcaster(get_frame_source())
    # Store on the app object so the route (and app shutdown) can reach the
    # single shared instance.
    app.camera_broadcaster = broadcaster  # type: ignore[attr-defined]

    @app.route("/")
    def index() -> str:
        return render_template("index.html", title="Baby Monitor")

    @app.route("/healthz")
    def healthz() -> tuple[str, int]:
        """Lightweight health check for quick reachability tests."""
        return "ok", 200

    @app.route("/video_feed")
    def video_feed() -> Response:
        """Live MJPEG stream — subscribes to the shared camera broadcaster.

        No ffmpeg is spawned per connection: every viewer reads the latest frame
        from the single app-owned broadcaster. Disconnecting just unsubscribes.
        """
        return Response(
            mjpeg_stream(app.camera_broadcaster),  # type: ignore[attr-defined]
            mimetype=MJPEG_CONTENT_TYPE,
        )

    return app
