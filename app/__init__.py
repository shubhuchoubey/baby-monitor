"""Baby Monitor Flask application.

Task 2 scope: serve a single status page over the local network. Video, audio,
and sound-detection features are added in later tasks.
"""

from __future__ import annotations

from flask import Flask, render_template


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

    return app
