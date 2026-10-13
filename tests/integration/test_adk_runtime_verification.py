"""Integration tests verifying Google ADK execution interface and Vertex AI Agent Runtime compatibility."""

import pytest
from agentplatform.agent_engines.templates.adk import AdkApp
from google.adk.events import Event
from google.genai import types

from app.agent import app as adk_app
from app.app_utils import services
from app.models.industry import IndustryType
from app.models.profile import BusinessProfile, OnboardingInput
from app.storage.firestore_store import LocalDocumentRepository, set_persistence_repository


@pytest.mark.asyncio
async def test_adk_app_stream_query_full_conversational_workflow():
    """Verify ADK execution interface executes end-to-end multi-turn session with revisions."""
    repo = LocalDocumentRepository()
    set_persistence_repository(repo)

    # 1. Register business profile under tenant ID
    biz_id = "biz_adk_runtime_test"
    prof = BusinessProfile.create_from_onboarding(
        OnboardingInput(
            business_name="Vertex Civil Engineering",
            industry=IndustryType.CONSTRUCTION_CIVIL_ENGINEERING,
            business_description="Bridge design and municipal infrastructure",
            business_location="Charleston, SC",
            preferred_platforms=["LinkedIn", "Instagram"],
        ),
        business_id=biz_id,
    )
    repo.save_profile(prof)

    # 2. Initialize AdkApp (Vertex AI Reasoning Engine template runtime)
    runtime = AdkApp(
        app=adk_app,
        session_service_builder=services.get_session_service,
        artifact_service_builder=services.get_artifact_service,
    )
    runtime.set_up()

    # 3. Create session via ADK session service
    session = await runtime.async_create_session(user_id=biz_id)
    assert session and session.get("id")
    session_id = session["id"]

    # 4. Turn 1: Single caption request via ADK async_stream_query
    events_t1 = []
    async for event in runtime.async_stream_query(
        user_id=biz_id,
        session_id=session_id,
        message="Create an Instagram caption for our harbour bridge seismic retrofitting",
    ):
        events_t1.append(event)

    assert len(events_t1) >= 1
    # Check text part
    t1_text = " ".join([
        p.get("text", "")
        for e in events_t1
        if "content" in e
        for p in e["content"].get("parts", [])
    ])
    assert "Vertex Civil Engineering" in t1_text
    assert "Charleston, SC" in t1_text

    # Check structured UI card output
    t1_output = [e["output"] for e in events_t1 if "output" in e and e["output"].get("action") == "caption_drafted"]
    assert len(t1_output) == 1
    assert t1_output[0]["card_type"] == "captions"
    cap_v1 = t1_output[0]["card_data"]["captions"][0]
    assert cap_v1["version_number"] == 1

    # 5. Turn 2: Conversational revision in the same session
    events_t2 = []
    async for event in runtime.async_stream_query(
        user_id=biz_id,
        session_id=session_id,
        message="Make it shorter and add #CharlestonEngineering",
    ):
        events_t2.append(event)

    t2_output = [e["output"] for e in events_t2 if "output" in e and e["output"].get("action") == "caption_revised"]
    assert len(t2_output) == 1
    assert t2_output[0]["card_type"] == "captions"
    cap_v2 = t2_output[0]["card_data"]["captions"][0]
    assert cap_v2["version_number"] == 2
    assert len(cap_v2["version_history"]) == 1
    assert cap_v2["version_history"][0]["caption_text"] == cap_v1["caption_text"]
