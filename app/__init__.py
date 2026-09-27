"""Baby Monitor Flask application.

Serves the status page, a health check, and the live MJPEG video feed. Video
capture sits behind the ``app.video`` interface (swappable camera backends).
"""

from __future__ import annotations

from flask import Flask, Response, render_template

from app.video import MJPEG_CONTENT_TYPE, get_frame_source, mjpeg_stream


def create_app() -> Flask:
    """Application factory. Returns a configured Flask app."""
    app = Flask(__name__)

    @app.route("/")
    def index() -> str:
        return render_template("index.html", title="Baby Monitor")

    @app.route("/healthz")
    def healthz() -> tuple[str, int]:
        """Lightweight health check for quick reachability tests."""
        return "ok", 200

    @app.route("/video_feed")
    def video_feed() -> Response:
        """Live MJPEG stream from the configured camera backend."""
        return Response(
            mjpeg_stream(get_frame_source()),
            mimetype=MJPEG_CONTENT_TYPE,
        )

    return app
