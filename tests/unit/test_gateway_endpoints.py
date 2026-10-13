"""Integration tests for Backend Gateway endpoints using FastAPI TestClient."""

import pytest
from fastapi.testclient import TestClient

from app.auth import get_auth_service, get_invitation_service
from app.fast_api_app import app
from app.storage.firestore_store import LocalDocumentRepository, set_persistence_repository


@pytest.fixture
def client():
    # Reset storage and add test invitation
    repo = LocalDocumentRepository()
    set_persistence_repository(repo)
    inv_svc = get_invitation_service()
    inv_svc.create_invitation("GATEWAY-TEST-CODE", max_uses=10)
    return TestClient(app)


def test_gateway_registration_requires_invitation(client):
    # Missing / invalid invitation -> 403 Forbidden
    bad_resp = client.post(
        "/api/auth/register",
        json={
            "email": "denied@example.com",
            "password": "Password123!",
            "invitation_code": "WRONG-CODE",
            "business_name": "Denied Corp",
            "industry": "restaurant",
            "business_description": "Italian Trattoria",
            "business_location": "New York, NY",
        },
    )
    assert bad_resp.status_code == 403

    # Valid invitation -> 200 OK
    good_resp = client.post(
        "/api/auth/register",
        json={
            "email": "approved@example.com",
            "password": "Password123!",
            "invitation_code": "GATEWAY-TEST-CODE",
            "business_name": "Bella Cucina",
            "industry": "restaurant",
            "business_description": "Authentic wood-fired pizza and handmade pastas",
            "business_location": "New York, NY",
            "preferred_platforms": ["Instagram", "Facebook"],
        },
    )
    assert good_resp.status_code == 200
    data = good_resp.json()
    assert "token" in data
    assert data["profile"]["business_name"] == "Bella Cucina"
    assert data["profile"]["industry"] == "restaurant"


def test_gateway_unauthenticated_requests_rejected(client):
    # Accessing protected profile without Bearer token -> 401 Unauthorized
    resp = client.get("/api/business/profile")
    assert resp.status_code == 401

    resp2 = client.get("/api/conversations/current", headers={"Authorization": "Bearer badtoken"})
    assert resp2.status_code == 401


def test_returning_business_flow_and_auto_greeting(client):
    # Register business once
    reg = client.post(
        "/api/auth/register",
        json={
            "email": "builder@example.com",
            "password": "Password123!",
            "invitation_code": "GATEWAY-TEST-CODE",
            "business_name": "Apex Civil Constructors",
            "industry": "construction_civil_engineering",
            "business_description": "Heavy civil excavation and bridge engineering",
            "business_location": "Seattle, WA",
            "preferred_platforms": ["LinkedIn"],
        },
    )
    token = reg.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Returning business requests current conversation
    # Must auto-greet with current month's opening without repeating onboarding!
    conv_resp = client.get("/api/conversations/current", headers=headers)
    assert conv_resp.status_code == 200
    conv_data = conv_resp.json()
    assert len(conv_data["messages"]) > 0
    welcome = conv_data["messages"][0]
    assert "What do you have going on for" in welcome["content"]
    assert "Apex Civil Constructors" in welcome["content"]
    assert welcome["card_type"] == "observances"


def test_caption_revision_and_restoration_endpoints(client):
    # Register and get token
    reg = client.post(
        "/api/auth/register",
        json={
            "email": "lawyer@example.com",
            "password": "Password123!",
            "invitation_code": "GATEWAY-TEST-CODE",
            "business_name": "Summit Law Group",
            "industry": "law_office",
            "business_description": "Estate planning and probate law services",
            "business_location": "Boston, MA",
            "preferred_platforms": ["LinkedIn"],
        },
    )
    token = reg.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Send message to generate draft captions
    chat_resp = client.post(
        "/api/chat/message",
        headers=headers,
        json={"message": "Free estate planning seminar on Oct 20th; Will preparation checklist."},
    )
    assert chat_resp.status_code == 200

    # Retrieve captions
    caps_resp = client.get("/api/captions", headers=headers)
    assert caps_resp.status_code == 200
    caps = caps_resp.json()
    assert len(caps) > 0
    cap_id = caps[0]["id"]
    original_text = caps[0]["caption_text"]

    # Revise caption
    rev_resp = client.post(
        f"/api/captions/{cap_id}/revise",
        headers=headers,
        json={
            "new_text": "Updated copy: Secure your family's future with our free seminar on Oct 20.",
            "new_hashtags": ["#EstatePlanning", "#BostonLaw"],
            "note": "Client requested more approachable headline",
        },
    )
    assert rev_resp.status_code == 200
    rev_data = rev_resp.json()
    assert rev_data["current_version"] == 2
    assert "Updated copy" in rev_data["caption_text"]

    # Restore version 1
    restore_resp = client.post(
        f"/api/captions/{cap_id}/restore/1",
        headers=headers,
    )
    assert restore_resp.status_code == 200
    restored_data = restore_resp.json()
    assert restored_data["caption_text"] == original_text
    assert restored_data["current_version"] == 3


def test_news_approval_platform_selection_endpoints(client):
    reg = client.post(
        "/api/auth/register",
        json={
            "email": "charity@example.com",
            "password": "Password123!",
            "invitation_code": "GATEWAY-TEST-CODE",
            "business_name": "Community Table",
            "industry": "nonprofit",
            "business_description": "Food rescue and community pantry network",
            "business_location": "Portland, OR",
            "preferred_platforms": ["Instagram", "Facebook"],
        },
    )
    token = reg.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Seed an article for this business
    from app.storage.firestore_store import get_persistence_repository
    from app.models.news import NewsArticle
    repo = get_persistence_repository()
    art = NewsArticle(
        id="art_api_test_1",
        business_id=reg.json()["user"]["business_id"],
        title="Regional Hunger Relief Grant Awarded",
        source="Northwest Philanthropy",
        url="https://example.com/grant",
        publication_date="2026-10-05",
        summary="Funding expands cold storage food pantries.",
        relevance="Directly supports Community Table infrastructure.",
        industry="nonprofit",
    )
    repo.save_discovered_news(reg.json()["user"]["business_id"], [art])

    # 1. Approve article -> prompts for platforms
    appr_resp = client.post(f"/api/news/art_api_test_1/approve", headers=headers)
    assert appr_resp.status_code == 200
    appr_data = appr_resp.json()
    assert appr_data["status"] == "approved_awaiting_platforms"
    assert "Which social media platform(s)" in appr_data["prompt"]

    # 2. Select platforms -> generates captions
    plat_resp = client.post(
        f"/api/news/art_api_test_1/select-platforms",
        headers=headers,
        json={"platforms": ["Instagram", "Facebook"]},
    )
    assert plat_resp.status_code == 200
    plat_data = plat_resp.json()
    assert plat_data["article"]["approval_status"] == "approved"
    assert len(plat_data["created_captions"]) > 0


def test_account_deletion_cascading(client):
    reg = client.post(
        "/api/auth/register",
        json={
            "email": "wipe@example.com",
            "password": "Password123!",
            "invitation_code": "GATEWAY-TEST-CODE",
            "business_name": "Wipe Target",
            "industry": "restaurant",
            "business_description": "Fine Dining",
            "business_location": "Miami, FL",
        },
    )
    token = reg.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Delete account
    del_resp = client.delete("/api/auth/account", headers=headers)
    assert del_resp.status_code == 200

    # Token is now invalid
    check_resp = client.get("/api/business/profile", headers=headers)
    assert check_resp.status_code == 401
