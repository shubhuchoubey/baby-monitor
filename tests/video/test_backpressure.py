"""Tests for the send-buffer cap helper (backpressure for bounded latency).

Capping the socket send buffer means the kernel can only hold ~1 frame of
video; when it's full, the streaming generator's write blocks, and that
backpressure is what makes the broadcaster's latest-frame drop effective under a
slow link (stale frames are skipped instead of queued). See
plans/VIDEO_STREAM_DEBUG.md Phase 6.
"""

from __future__ import annotations

import socket

from app.video.backpressure import cap_send_buffer


def test_cap_send_buffer_sets_sndbuf_smaller() -> None:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1024 * 1024)  # start big
        cap_send_buffer(s, 128 * 1024)
        # The kernel may round the value, but it must not exceed ~2x request and
        # must be well under the original 1 MiB.
        actual = s.getsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF)
        assert actual <= 512 * 1024
    finally:
        s.close()


def test_cap_send_buffer_never_raises_on_bad_socket() -> None:
    # A closed socket must not blow up the request path; the cap is best-effort.
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.close()
    cap_send_buffer(s, 128 * 1024)  # should silently no-op
