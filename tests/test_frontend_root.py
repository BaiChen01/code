from __future__ import annotations

from fastapi.testclient import TestClient

from app.app import create_app


def test_root_serves_frontend_html() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Game Intel Agent Console" in response.text


def test_static_assets_are_served() -> None:
    client = TestClient(create_app())

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
