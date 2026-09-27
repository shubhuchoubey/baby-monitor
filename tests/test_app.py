"""Tests for the Flask app factory and its routes."""

from __future__ import annotations

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
