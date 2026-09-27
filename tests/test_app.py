"""Tests for the Flask app factory and its routes."""

from __future__ import annotations

from collections.abc import Iterator

import app as app_pkg
from app import create_app


def test_index_serves_status_page() -> None:
    client = create_app().test_client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Baby Monitor" in resp.get_data(as_text=True)


def test_healthz_returns_ok() -> None:
    client = create_app().test_client()
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.get_data(as_text=True) == "ok"


def test_video_feed_streams_multipart_mjpeg(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """/video_feed returns a multipart MJPEG stream (frame source mocked)."""
    jpeg = b"\xff\xd8DATA\xff\xd9"

    class FakeSource:
        def start(self) -> None: ...
        def frames(self) -> Iterator[bytes]:
            yield jpeg

        def stop(self) -> None: ...

    monkeypatch.setattr(app_pkg, "get_frame_source", lambda: FakeSource())

    resp = create_app().test_client().get("/video_feed")
    assert resp.status_code == 200
    assert resp.mimetype == "multipart/x-mixed-replace"
    body = resp.get_data()
    assert jpeg in body
    assert b"Content-Type: image/jpeg" in body
