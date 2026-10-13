"""Unit tests for SoCo ADK 2.0 Graph Workflow integration."""

import json
from pathlib import Path
import pytest
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.agent import app as adk_app, root_agent
from app.models.industry import IndustryType
from app.storage.profile_store import LocalJsonProfileStore, set_default_store


@pytest.fixture(autouse=True)
def isolated_profile_store(tmp_path: Path):
    """Ensure each test runs with a clean, isolated profile store."""
    store = LocalJsonProfileStore(storage_dir=tmp_path)
    set_default_store(store)
    return store


def test_workflow_new_user_prompt(isolated_profile_store: LocalJsonProfileStore):
    """Test that a new user without a profile receives onboarding instructions."""
    session_service = InMemorySessionService()
    session = session_service.create_session_sync(user_id="user_1", app_name="app")
    runner = Runner(app=adk_app, session_service=session_service)

    events = list(runner.run(
        new_message=types.Content(role="user", parts=[types.Part.from_text(text="Hi there!")]),
        user_id="user_1",
        session_id=session.id,
    ))

    text_parts = [
        p.text for e in events if e.content and e.content.parts for p in e.content.parts if p.text
    ]
    combined_text = " ".join(text_parts)
    assert "Welcome to SoCo" in combined_text
    assert "Business Name" in combined_text
    assert "Industry" in combined_text


def test_workflow_onboarding_and_returning_user_greeting(isolated_profile_store: LocalJsonProfileStore):
    """Test onboarding and automatic conversational greeting for returning users."""
    session_service = InMemorySessionService()
    session = session_service.create_session_sync(user_id="user_2", app_name="app")
    runner = Runner(app=adk_app, session_service=session_service)

    # 1. Provide onboarding payload
    payload = json.dumps({
        "business_name": "Pacific Coast Engineering",
        "industry": IndustryType.CONSTRUCTION_CIVIL_ENGINEERING.value,
        "business_description": "Coastal structural engineering and maritime foundations",
        "business_location": "San Diego, CA",
        "preferred_platforms": ["LinkedIn", "Instagram"],
    })

    onboard_events = list(runner.run(
        new_message=types.Content(role="user", parts=[types.Part.from_text(text=payload)]),
        user_id="user_2",
        session_id=session.id,
    ))

    onboard_text = " ".join([
        p.text for e in onboard_events if e.content and e.content.parts for p in e.content.parts if p.text
    ])
    assert "Welcome to SoCo, Pacific Coast Engineering" in onboard_text
    assert "Professional, confident, and informative" in onboard_text
    assert "What do you have going on for" in onboard_text

    # Verify persistent store has profile
    assert isolated_profile_store.exists("default")

    # 2. Returning user greeted naturally with current month
    returning_events = list(runner.run(
        new_message=types.Content(role="user", parts=[types.Part.from_text(text="Hello again")]),
        user_id="user_2",
        session_id=session.id,
    ))

    returning_text = " ".join([
        p.text for e in returning_events if e.content and e.content.parts for p in e.content.parts if p.text
    ])
    assert "Hello again, **Pacific Coast Engineering**!" in returning_text
    assert "What do you have going on for" in returning_text


@pytest.mark.asyncio
async def test_workflow_production_rejects_missing_business_id(monkeypatch):
    """In production mode, agent entrypoint strictly rejects missing business_id."""
    from app.workflow_nodes import soco_entrypoint_node
    monkeypatch.setenv("ENVIRONMENT", "production")

    events = [e async for e in soco_entrypoint_node("Hi there without business_id")]
    error_events = [e for e in events if getattr(e, "output", None) and e.output.get("action") == "error"]
    assert len(error_events) == 1
    assert "Missing required business_id" in error_events[0].output["error"]
