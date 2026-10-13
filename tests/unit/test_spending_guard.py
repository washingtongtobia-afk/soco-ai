"""Unit tests for spending guard, rate limiting, and automated spending safeguards."""

import pytest
from fastapi.testclient import TestClient

from app.auth import get_invitation_service
from app.billing.spending_guard import SpendingGuard, get_spending_guard, AUTOMATIC_SUSPENSION_USD
from app.fast_api_app import app
from app.storage.firestore_store import LocalDocumentRepository, set_persistence_repository


@pytest.fixture(autouse=True)
def reset_guard():
    guard = get_spending_guard()
    guard.reset_for_testing()
    yield
    guard.reset_for_testing()


@pytest.fixture
def client():
    repo = LocalDocumentRepository()
    set_persistence_repository(repo)
    inv_svc = get_invitation_service()
    inv_svc.create_invitation("SOCO-SPEND-CODE", max_uses=10)
    return TestClient(app)


def test_rate_limiting_sliding_window():
    """Verify that exceeding 5 requests per 60 seconds triggers rate limiting."""
    guard = SpendingGuard()
    biz_id = "biz_test_rate_limit"

    # First 5 requests should pass
    for i in range(5):
        allowed, reason = guard.can_proceed(biz_id)
        assert allowed is True
        assert reason is None

    # 6th request within same minute should be rejected
    allowed, reason = guard.can_proceed(biz_id)
    assert allowed is False
    assert "Rate Limit Exceeded" in reason


def test_daily_and_monthly_request_limits():
    """Verify daily (25) and monthly (250) beta limits are strictly enforced."""
    guard = SpendingGuard()
    biz_id = "biz_test_daily_limit"

    # Simulate 25 daily requests
    for _ in range(25):
        guard.record_usage(biz_id, input_tokens=100, output_tokens=100)

    # Next request should be blocked on daily limit
    allowed, reason = guard.can_proceed(biz_id)
    assert allowed is False
    assert "Daily Limit Reached" in reason


def test_automatic_suspension_at_20_dollar_threshold():
    """Verify automatic suspension triggers when tracked spend reaches $20.00."""
    guard = SpendingGuard()
    biz_id = "biz_test_suspension"

    # Under threshold
    guard.simulate_spending_increase(15.50)
    summary = guard.get_system_summary()
    assert summary.tracked_spending_usd == 15.50
    assert summary.is_suspended is False

    allowed, _ = guard.can_proceed(biz_id)
    assert allowed is True

    # Push over the $20.00 threshold ($5 buffer left on $25 budget)
    guard.simulate_spending_increase(5.00)  # Total 20.50
    summary = guard.get_system_summary()
    assert summary.tracked_spending_usd == 20.50
    assert summary.is_suspended is True

    # New requests must be automatically suspended
    allowed, reason = guard.can_proceed(biz_id)
    assert allowed is False
    assert "Monthly Budget Safeguard Triggered" in reason
    assert "$20.00" in reason


def test_fail_safe_behavior():
    """Verify that fail-safe mode disables billable requests safely."""
    guard = SpendingGuard()
    biz_id = "biz_test_fail_safe"

    guard.set_fail_safe_mode(True)
    allowed, reason = guard.can_proceed(biz_id)
    assert allowed is False
    assert "Fail-Safe Active" in reason

    guard.set_fail_safe_mode(False)
    allowed, reason = guard.can_proceed(biz_id)
    assert allowed is True


def test_spending_guard_api_endpoints(client):
    """Verify /api/business/usage and /api/admin/spending endpoints."""
    # Register test user
    reg = client.post(
        "/api/auth/register",
        json={
            "email": "spend_user@example.com",
            "password": "Password123!",
            "invitation_code": "SOCO-SPEND-CODE",
            "business_name": "Lakeview Law",
            "industry": "law_office",
            "business_description": "Estate planning",
            "business_location": "Chicago, IL",
            "preferred_platforms": ["LinkedIn"],
        },
    )
    assert reg.status_code == 200
    token = reg.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Query business usage
    usage_resp = client.get("/api/business/usage", headers=headers)
    assert usage_resp.status_code == 200
    usage_data = usage_resp.json()
    assert usage_data["daily_requests_limit"] == 25
    assert usage_data["monthly_requests_limit"] == 250
    assert usage_data["daily_requests_remaining"] == 25

    # Query system spending
    admin_resp = client.get("/api/admin/spending", headers=headers)
    assert admin_resp.status_code == 200
    admin_data = admin_resp.json()
    assert admin_data["monthly_target_budget_usd"] == 25.0
    assert admin_data["suspension_threshold_usd"] == 20.0
    assert admin_data["is_suspended"] is False
