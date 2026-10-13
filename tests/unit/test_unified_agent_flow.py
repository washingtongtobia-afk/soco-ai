"""Unit tests verifying Phase A & Phase B unification of SoCo ADK agent and gateway."""

import os
from pathlib import Path
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from app.auth import get_invitation_service
from app.config.model_config import SOCO_PRIMARY_MODEL, SOCO_FALLBACK_MODEL
from app.fast_api_app import app
from app.storage.firestore_store import LocalDocumentRepository, set_persistence_repository
from app.storage.profile_store import LocalJsonProfileStore, set_default_store
from app.workflow_nodes import soco_entrypoint_node


@pytest.fixture(autouse=True)
def isolated_stores(tmp_path: Path):
    """Ensure each test runs with fresh isolated document and profile stores."""
    profile_store = LocalJsonProfileStore(storage_dir=tmp_path)
    set_default_store(profile_store)
    repo = LocalDocumentRepository()
    set_persistence_repository(repo)
    inv_svc = get_invitation_service()
    inv_svc.create_invitation("SOCO-UNIFIED-TEST-CODE", max_uses=10)
    return profile_store, repo


@pytest.fixture
def clean_client():
    return TestClient(app)


def test_model_configuration_centralization():
    """Verify Gemini 3.8 Flash is configured as default and dynamically configurable."""
    assert SOCO_PRIMARY_MODEL == "gemini-3.8-flash"
    assert SOCO_FALLBACK_MODEL == "gemini-3.5-flash"

    with patch.dict(os.environ, {"SOCO_PRIMARY_MODEL": "gemini-3.8-pro"}):
        import importlib
        from app.config import model_config
        importlib.reload(model_config)
        assert model_config.SOCO_PRIMARY_MODEL == "gemini-3.8-pro"

    # Reset back
    import importlib
    from app.config import model_config
    importlib.reload(model_config)
    assert model_config.SOCO_PRIMARY_MODEL == "gemini-3.8-flash"


def test_unified_adk_agent_direct_node_execution():
    """Verify soco_entrypoint_node directly supports all conversational workflows."""
    import asyncio
    import json

    # 1. Onboarding via node input
    onboard_payload = {
        "business_name": "Harbor Seafood Kitchen",
        "industry": "restaurant",
        "business_description": "Fresh catch seafood and dockside dining",
        "business_location": "Portland, ME",
        "preferred_platforms": ["Instagram", "Facebook"],
    }

    async def run_node(payload):
        return [e async for e in soco_entrypoint_node(payload)]

    # New user with onboarding JSON
    events = asyncio.run(run_node({
        "text": json.dumps(onboard_payload),
        "business_id": "biz_harbor_kitchen",
    }))
    assert any((getattr(e, "output", None) or {}).get("action") == "onboarded" for e in events)

    # 2. Single caption request via node
    cap_events = asyncio.run(run_node({
        "text": "Create an Instagram caption for our clam chowder weekend special",
        "business_id": "biz_harbor_kitchen",
    }))
    cap_action = [e.output for e in cap_events if getattr(e, "output", None) and e.output.get("action") == "caption_drafted"]
    assert len(cap_action) == 1
    assert cap_action[0]["card_type"] == "captions"
    assert len(cap_action[0]["card_data"]["captions"]) == 1

    # 3. Conversational revision via node
    rev_events = asyncio.run(run_node({
        "text": "Make it shorter and punchier",
        "business_id": "biz_harbor_kitchen",
    }))
    rev_action = [e.output for e in rev_events if getattr(e, "output", None) and e.output.get("action") == "caption_revised"]
    assert len(rev_action) == 1
    rev_cap = rev_action[0]["card_data"]["captions"][0]
    assert rev_cap["version_number"] == 2


def test_gateway_chat_message_routes_through_unified_soco_entrypoint_node(clean_client):
    """Verify gateway /api/chat/message delegates directly to soco_entrypoint_node."""
    # Register business
    reg = clean_client.post(
        "/api/auth/register",
        json={
            "email": "chef@example.com",
            "password": "Password123!",
            "invitation_code": "SOCO-UNIFIED-TEST-CODE",
            "business_name": "Trattoria Roma",
            "industry": "restaurant",
            "business_description": "Handmade pasta and authentic Roman pizza",
            "business_location": "Chicago, IL",
            "preferred_platforms": ["Instagram", "Facebook"],
        },
    )
    assert reg.status_code == 200
    token = reg.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Spy on soco_entrypoint_node to confirm it was invoked by gateway
    with patch("app.gateway.gateway_router.soco_entrypoint_node", wraps=soco_entrypoint_node) as spy_node:
        resp = clean_client.post(
            "/api/chat/message",
            headers=headers,
            json={"message": "Draft an Instagram caption for our autumn truffle risotto launch"},
        )
        assert resp.status_code == 200
        assert spy_node.called, "Gateway /api/chat/message MUST invoke soco_entrypoint_node!"
        call_args = spy_node.call_args[0][0]
        assert call_args["text"] == "Draft an Instagram caption for our autumn truffle risotto launch"
        assert call_args["business_id"] == reg.json()["user"]["business_id"]

    data = resp.json()
    assert data["total_captions"] == 1
    assert data["message"]["card_type"] == "captions"
    assert len(data["message"]["card_data"]["captions"]) == 1
