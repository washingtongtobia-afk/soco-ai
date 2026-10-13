"""Unit & Integration tests for SoCo frontend route serving and sample invitation endpoint."""

import pytest
from fastapi.testclient import TestClient

from app.auth import get_invitation_service
from app.fast_api_app import app
from app.storage.firestore_store import LocalDocumentRepository, set_persistence_repository


@pytest.fixture
def client():
    repo = LocalDocumentRepository()
    set_persistence_repository(repo)
    inv_svc = get_invitation_service()
    inv_svc.create_invitation("FRONTEND-TEST-KEY", max_uses=5)
    return TestClient(app)


def test_serve_soco_html(client):
    """Verify that /soco serves the modern chat frontend HTML."""
    resp = client.get("/soco")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Meet SoCo, your monthly social media strategist" in resp.text
    assert "Construction / Civil Engineering" in resp.text
    assert "Nonprofit & Philanthropy" in resp.text
    assert "Restaurant & Food Service" in resp.text
    assert "Law Office & Legal Practice" in resp.text


def test_serve_app_html(client):
    """Verify that /app serves the same single page application."""
    resp = client.get("/app")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "id=\"workspace-view\"" in resp.text


def test_serve_frontend_static_assets(client):
    """Verify static CSS and JS are correctly mounted and served."""
    css_resp = client.get("/frontend-static/index.css")
    assert css_resp.status_code == 200
    assert "text/css" in css_resp.headers["content-type"]
    assert "--coral-primary" in css_resp.text
    assert "--peach-surface" in css_resp.text

    js_resp = client.get("/frontend-static/app.js")
    assert js_resp.status_code == 200
    assert "javascript" in js_resp.headers["content-type"]
    assert "initApp" in js_resp.text
    assert "handleSendMessage" in js_resp.text


def test_sample_invitation_code_endpoint(client):
    """Verify that /api/auth/invitation/sample returns a valid high-entropy beta key in local dev."""
    resp = client.get("/api/auth/invitation/sample")
    assert resp.status_code == 200
    data = resp.json()
    assert "code" in data
    assert data["code"].startswith("SOCO-") or data["code"] == "FRONTEND-TEST-KEY"


def test_sample_invitation_code_blocked_in_production(client, monkeypatch):
    """Verify that /api/auth/invitation/sample returns 404 in production environments."""
    # Test ENVIRONMENT=production
    monkeypatch.setenv("ENVIRONMENT", "production")
    resp_prod = client.get("/api/auth/invitation/sample")
    assert resp_prod.status_code == 404

    # Test K_SERVICE set (Google Cloud Run environment)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("K_SERVICE", "soco-agent-service")
    resp_cloud = client.get("/api/auth/invitation/sample")
    assert resp_cloud.status_code == 404


def test_demo_login_endpoint(client):
    """Verify that /api/auth/demo-login enables instant functional testing without manual registration."""
    resp = client.post("/api/auth/demo-login", json={"industry": "construction_civil_engineering"})
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert data["profile"]["business_name"] == "Skyline Civil Constructors"
    assert data["profile"]["industry"] == "construction_civil_engineering"


def test_demo_login_blocked_in_production(client, monkeypatch):
    """Verify that demo-login returns 404 in production."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    resp_prod = client.post("/api/auth/demo-login", json={"industry": "construction_civil_engineering"})
    assert resp_prod.status_code == 404


