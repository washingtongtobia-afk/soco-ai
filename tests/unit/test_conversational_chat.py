"""Unit tests for SoCo conversational chat, single caption generation, and revisions."""

import pytest
from fastapi.testclient import TestClient

from app.auth import get_invitation_service
from app.fast_api_app import app
from app.models.caption import CaptionDraft, CaptionVersion, CaptionStatus, CaptionSourceType
from app.models.industry import IndustryType
from app.models.profile import BusinessProfile, OnboardingInput
from app.planning.caption_generator import CaptionGenerator, detect_missing_event_details
from app.planning.ai_caption_engine import FALLBACK_DRAFT_LABEL, clean_concept_topic
from app.storage.firestore_store import LocalDocumentRepository, set_persistence_repository


@pytest.fixture
def client():
    repo = LocalDocumentRepository()
    set_persistence_repository(repo)
    inv_svc = get_invitation_service()
    inv_svc.create_invitation("SOCO-CHAT-TEST-CODE", max_uses=10)
    return TestClient(app)


def test_caption_model_dump_includes_both_text_and_version_properties():
    """Ensure frontend-compatible text and version aliases are present in model_dump."""
    draft = CaptionDraft(
        id="cap_test_123",
        month="October",
        year=2026,
        week_number=1,
        suggested_date="October 2026",
        platform="Instagram",
        caption_text="Join us for a wonderful community celebration! 🌟",
        hashtags=["#Community", "#LocalPride"],
        concept_title="Community Event",
        source_type=CaptionSourceType.USER_EVENT,
        status=CaptionStatus.DRAFT,
        tone="Warm and engaging",
        voice="Welcoming",
        current_version=1,
    )

    dumped = draft.model_dump()
    assert dumped["caption_text"] == "Join us for a wonderful community celebration! 🌟"
    assert dumped["text"] == "Join us for a wonderful community celebration! 🌟"
    assert dumped["version_number"] == 1
    assert draft.text == "Join us for a wonderful community celebration! 🌟"
    assert draft.version_number == 1

    # Test CaptionVersion serialization
    draft.save_revision(new_text="Shorter copy! 🌟", note="Shortened for clarity")
    assert len(draft.version_history) == 1
    v1_dump = draft.version_history[0].model_dump()
    assert v1_dump["text"] == "Join us for a wonderful community celebration! 🌟"
    assert v1_dump["version_number"] == 1
    assert "saved_at" in v1_dump
    assert v1_dump["change_note"] == "Shortened for clarity"


def test_clean_concept_topic_strips_prompt_prefixes():
    """Ensure user command phrasing is stripped from concept title."""
    assert clean_concept_topic("Create an Instagram caption for our community cleanup") == "Our community cleanup"
    assert clean_concept_topic("write a caption about fall menu launch") == "Fall menu launch"
    assert clean_concept_topic("Can you draft a LinkedIn post on contract dispute tips") == "Contract dispute tips"
    assert clean_concept_topic("Community Harvest Festival") == "Community Harvest Festival"


def test_detect_missing_event_details_identifies_unspecified_fields():
    """Verify missing event operational details trigger clarifying questions."""
    # Vague prompt: missing date/time, venue, and admission
    questions = detect_missing_event_details("Create an Instagram caption for a community event")
    assert len(questions) >= 3
    assert any("When" in q for q in questions)
    assert any("Where" in q for q in questions)
    assert any("admission" in q.lower() or "rsvp" in q.lower() for q in questions)

    # Detailed prompt: has date, location, and cost
    detailed = detect_missing_event_details(
        "Community fair on Saturday Oct 24 at 2pm in Central Park, free admission for all families"
    )
    assert len(detailed) == 0


def test_generate_single_caption_for_community_event():
    """Verify requesting 1 caption produces exactly 1 complete caption with clarifying questions."""
    gen = CaptionGenerator()
    profile = BusinessProfile.create_from_onboarding(OnboardingInput(
        business_name="Beacon Civil Engineering",
        industry=IndustryType.CONSTRUCTION_CIVIL_ENGINEERING,
        business_description="Infrastructure and civil engineering services",
        business_location="Austin, TX",
        preferred_platforms=["Instagram", "LinkedIn"],
    ))

    result = gen.generate_single_caption(
        profile=profile,
        topic="Create an Instagram caption for a community event",
        platform="Instagram",
    )

    cap = result.caption
    assert cap.platform == "Instagram"
    assert cap.concept_title == "A community event"
    # Must NOT repeat full command string as concept title
    assert not cap.concept_title.lower().startswith("create an instagram caption")

    # Character count must be substantial (> 100 characters)
    assert len(cap.caption_text) > 100
    assert len(cap.text) > 100

    # Must contain actual narrative copy, placeholders for missing facts, and meaningful CTA
    assert "Beacon Civil Engineering" in cap.caption_text
    assert "Austin, TX" in cap.caption_text
    assert "📍 Location:" in cap.caption_text
    assert "📅 Date & Time:" in cap.caption_text
    assert len(cap.hashtags) > 0

    # Must have simulation label in local demo mode
    assert FALLBACK_DRAFT_LABEL in cap.caption_text
    assert result.is_simulated is True

    # Must identify missing details
    assert len(result.clarifying_questions) > 0


def test_conversational_revision_flow():
    """Verify conversational revisions preserve version history and apply instruction."""
    gen = CaptionGenerator()
    profile = BusinessProfile.create_from_onboarding(OnboardingInput(
        business_name="Bella Italia Ristorante",
        industry=IndustryType.RESTAURANT,
        business_description="Authentic Tuscan dining",
        business_location="Seattle, WA",
        preferred_platforms=["Instagram"],
    ))

    res = gen.generate_single_caption(
        profile=profile,
        topic="Create an Instagram caption for our pasta making workshop",
        platform="Instagram",
    )
    cap = res.caption
    initial_text = cap.caption_text
    assert cap.current_version == 1

    # Revision 1: Make it shorter
    revised_short = gen.revise_caption(profile, cap, "Make it shorter and punchier")
    assert revised_short.current_version == 2
    assert len(revised_short.version_history) == 1
    assert revised_short.version_history[0].caption_text == initial_text
    # Should be shorter than initial draft
    assert len(revised_short.caption_text) < len(initial_text)

    # Revision 2: Make it more exciting
    revised_exciting = gen.revise_caption(profile, revised_short, "Make it more exciting!")
    assert revised_exciting.current_version == 3
    assert len(revised_exciting.version_history) == 2
    assert "🔥" in revised_exciting.caption_text


def test_gateway_chat_message_single_caption_vs_monthly_strategy(client):
    """Test full API request flow: single caption returns 1 caption card, monthly strategy returns plan."""
    # Register test user
    reg = client.post(
        "/api/auth/register",
        json={
            "email": "community_founder@example.com",
            "password": "Password123!",
            "invitation_code": "SOCO-CHAT-TEST-CODE",
            "business_name": "Oak & Iron Construction",
            "industry": "construction_civil_engineering",
            "business_description": "Residential timber framing and commercial builds",
            "business_location": "Denver, CO",
            "preferred_platforms": ["Instagram", "LinkedIn"],
        },
    )
    assert reg.status_code == 200
    token = reg.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Single Caption Request: "Create an Instagram caption for a community event"
    single_req = client.post(
        "/api/chat/message",
        headers=headers,
        json={"message": "Create an Instagram caption for our community event"},
    )
    assert single_req.status_code == 200
    single_data = single_req.json()
    assert single_data["total_captions"] == 1
    msg = single_data["message"]
    assert msg["card_type"] == "captions"
    assert "captions" in msg["card_data"]
    assert len(msg["card_data"]["captions"]) == 1
    # Check that clarifying questions are included in conversational message
    assert "confirm a few details" in msg["content"]
    assert "Date and start/end time" in msg["content"]
    # Check caption card content
    cap_item = msg["card_data"]["captions"][0]
    assert len(cap_item["caption_text"]) > 100
    assert len(cap_item["hashtags"]) > 0

    # 2. Conversational Revision: "Make it shorter"
    rev_req = client.post(
        "/api/chat/message",
        headers=headers,
        json={"message": "Make it shorter"},
    )
    assert rev_req.status_code == 200
    rev_data = rev_req.json()
    assert rev_data["total_captions"] == 1
    rev_msg = rev_data["message"]
    assert "v2" in rev_msg["content"]
    rev_cap = rev_msg["card_data"]["captions"][0]
    assert rev_cap["version_number"] == 2
    assert len(rev_cap["version_history"]) == 1

    # 3. Explicit Monthly Strategy Request
    plan_req = client.post(
        "/api/chat/message",
        headers=headers,
        json={"message": "Please generate our full monthly content plan for this month"},
    )
    assert plan_req.status_code == 200
    plan_data = plan_req.json()
    # Monthly plan must generate full multi-concept strategy (>= 4 drafts)
    assert plan_data["total_captions"] >= 4
    plan_msg = plan_data["message"]
    assert "plan" in plan_msg["card_data"]
    assert "captions_by_week" in plan_msg["card_data"]["plan"]

    # 4. General conversational chat inquiry
    faq_req = client.post(
        "/api/chat/message",
        headers=headers,
        json={"message": "Hello SoCo"},
    )
    assert faq_req.status_code == 200
    faq_data = faq_req.json()
    assert faq_data["total_captions"] == 0
    assert faq_data["message"]["card_type"] is None
