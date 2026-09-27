"""Tests for the Flask app factory and its routes.

The mechanical streaming behaviours (latest-frame drop, single shared opener,
multi-subscriber, disconnect-keeps-others, restart/backoff) are unit-tested
directly against ``CameraBroadcaster`` and ``mjpeg_stream`` in
``tests/video/`` — those do not need Flask. Here we only verify that the
routes are wired correctly.

Note: ``/video_feed`` is an *infinite* MJPEG generator in production. To test
the route without hanging, we inject a **finite** fake broadcaster that yields a
couple of frames and then reports "stopped", so ``mjpeg_stream`` terminates and
the Flask test client can safely drain the response.
"""

from __future__ import annotations

from app import create_app


class FakeBroadcaster:
    """A finite, thread-free ``FrameBroadcaster`` for route wiring tests.

    Serves a fixed list of frames via ``wait_for_newer`` and then reports it is
    no longer running, so the ``mjpeg_stream`` generator ends deterministically.
    """

    def __init__(self, frames: list[bytes]) -> None:
        self._frames = frames
        self.subscribed = 0
        self.unsubscribed = 0

    def subscribe(self) -> None:
        self.subscribed += 1

    def unsubscribe(self) -> None:
        self.unsubscribed += 1

    def is_running(self) -> bool:
        # Reports "stopped" once all frames have been served, ending the stream.
        return False

    def wait_for_newer(
        self, last_seq: int, timeout: float | None = None
    ) -> tuple[int, bytes] | None:
        if last_seq < len(self._frames):
            return last_seq + 1, self._frames[last_seq]
        return None  # no newer frame + is_running() False => generator ends


def _iter_body(resp: object) -> bytes:
    out = bytearray()
    for chunk in resp.response:  # type: ignore[attr-defined]
        out.extend(chunk)
    return bytes(out)


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


def test_video_feed_is_wired_to_the_broadcaster() -> None:
    """/video_feed returns a multipart MJPEG response fed by the app broadcaster."""
    jpeg_a = b"\xff\xd8AAAA\xff\xd9"
    jpeg_b = b"\xff\xd8BBBB\xff\xd9"
    caster = FakeBroadcaster([jpeg_a, jpeg_b])
    app = create_app(broadcaster=caster)

    resp = app.test_client().get("/video_feed", buffered=False)
    assert resp.status_code == 200
    assert resp.mimetype == "multipart/x-mixed-replace"

    body = _iter_body(resp)
    # Both frames are wrapped as multipart parts with JPEG headers.
    assert jpeg_a in body
    assert jpeg_b in body
    assert b"Content-Type: image/jpeg" in body
    # The route subscribed to the shared broadcaster (not a per-request source)
    # and unsubscribed when the stream ended.
    assert caster.subscribed == 1
    assert caster.unsubscribed == 1


def test_video_feed_matches_frame_source_protocol_shape() -> None:
    """FakeBroadcaster stands in for CameraBroadcaster's viewer-facing API."""
    from app.video.stream import FrameBroadcaster

    caster = FakeBroadcaster([])
    assert isinstance(caster, FrameBroadcaster)


def test_iter_body_yields_multipart_frames() -> None:
    """mjpeg_stream via the route emits one multipart part per frame."""
    frame = b"\xff\xd8ONE\xff\xd9"
    caster = FakeBroadcaster([frame])
    app = create_app(broadcaster=caster)
    resp = app.test_client().get("/video_feed", buffered=False)
    body = _iter_body(resp)
    from app.video import BOUNDARY

    assert body.count(BOUNDARY.encode()) == 1
    assert b"Content-Length: " + str(len(frame)).encode() in body
