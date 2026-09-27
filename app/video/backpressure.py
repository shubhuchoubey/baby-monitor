"""Socket backpressure for bounded video latency.

Root cause of residual lag (see plans/VIDEO_STREAM_DEBUG.md, Phase 4/6): even
with the broadcaster dropping stale frames, each frame we ``yield`` is accepted
*wholesale* into the kernel TCP send buffer. On a slow link that buffer can hold
tens of seconds of video downstream of our drop logic, so latency grows.

Fix: cap the send buffer to ~1 frame. When it is full, the streaming write
blocks, applying **backpressure** to the generator — which then simply waits for
and sends the *latest* frame, skipping the ones produced meanwhile. That is what
makes latest-frame dropping actually bound latency on a slow link.

``cap_send_buffer`` is best-effort and never raises: failing to tune a socket
must never break a request.
"""

from __future__ import annotations

import logging
import socket

from werkzeug.serving import WSGIRequestHandler

_log = logging.getLogger(__name__)

# ~1-2 JPEG frames at the streamed resolution. Small enough that the kernel
# cannot hoard seconds of video, large enough not to fragment a single frame.
DEFAULT_SEND_BUFFER_BYTES = 128 * 1024


def cap_send_buffer(sock: socket.socket, size: int = DEFAULT_SEND_BUFFER_BYTES) -> None:
    """Best-effort: cap a socket's ``SO_SNDBUF`` to ``size`` bytes.

    Never raises — a closed/invalid socket or an OS that rejects the option is
    silently ignored (the stream still works, just without the cap).
    """
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, size)
    except OSError:
        _log.debug("cap_send_buffer: could not set SO_SNDBUF", exc_info=True)


class BackpressureRequestHandler(WSGIRequestHandler):
    """Dev-server request handler that caps each connection's send buffer.

    Passed to ``app.run(request_handler=...)`` so every client socket (including
    the long-lived ``/video_feed`` stream) gets a small send buffer, giving the
    streaming generator backpressure instead of unbounded kernel buffering.
    """

    def setup(self) -> None:
        super().setup()
        cap_send_buffer(self.connection)
