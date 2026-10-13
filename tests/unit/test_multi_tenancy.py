"""Unit tests verifying strict multi-business data isolation and security."""

import pytest
from app.models.caption import CaptionDraft, CaptionSourceType
from app.models.conversation import ChatMessage
from app.models.industry import IndustryType
from app.models.news import ArticleApprovalStatus, NewsArticle
from app.models.profile import BusinessProfile, OnboardingInput
from app.storage.firestore_store import LocalDocumentRepository


@pytest.fixture
def repo():
    return LocalDocumentRepository()


def test_business_profile_isolation(repo):
    biz_a = "biz_construction_111"
    biz_b = "biz_nonprofit_222"

    prof_a = BusinessProfile.create_from_onboarding(
        OnboardingInput(
            business_name="Skyline Civil Group",
            industry=IndustryType.CONSTRUCTION_CIVIL_ENGINEERING,
            business_description="Bridge building and road infrastructure",
            business_location="Austin, TX",
        ),
        business_id=biz_a,
    )
    prof_b = BusinessProfile.create_from_onboarding(
        OnboardingInput(
            business_name="Hope Community Foundation",
            industry=IndustryType.NONPROFIT,
            business_description="Local youth shelter and family grants",
            business_location="Denver, CO",
        ),
        business_id=biz_b,
    )

    repo.save_profile(prof_a)
    repo.save_profile(prof_b)

    # Scoped reads
    retrieved_a = repo.get_profile(biz_a)
    retrieved_b = repo.get_profile(biz_b)

    assert retrieved_a.business_name == "Skyline Civil Group"
    assert retrieved_b.business_name == "Hope Community Foundation"

    # Business A cannot see Business B
    assert repo.get_profile(biz_a).business_id == biz_a
    assert repo.get_profile(biz_b).business_id == biz_b
    assert repo.get_profile("unauthorized_biz") is None


def test_conversation_and_message_isolation(repo):
    biz_a = "biz_law_aaa"
    biz_b = "biz_restaurant_bbb"

    conv_a, _ = repo.get_or_create_monthly_conversation(biz_a, 2026, 10, "October")
    conv_b, _ = repo.get_or_create_monthly_conversation(biz_b, 2026, 10, "October")

    msg_a = ChatMessage(
        id="msg_a_1",
        conversation_id=conv_a.id,
        business_id=biz_a,
        role="user",
        content="Confidential client legal briefing on estate planning.",
    )
    msg_b = ChatMessage(
        id="msg_b_1",
        conversation_id=conv_b.id,
        business_id=biz_b,
        role="user",
        content="Launching our fall pumpkin pasta menu this Friday.",
    )

    repo.append_message(biz_a, 2026, 10, msg_a)
    repo.append_message(biz_b, 2026, 10, msg_b)

    # Check Business A's conversation
    fetch_a = repo.get_monthly_conversation(biz_a, 2026, 10)
    assert len(fetch_a.messages) == 1
    assert "legal briefing" in fetch_a.messages[0].content
    assert "pasta menu" not in fetch_a.messages[0].content

    # Check Business B's conversation
    fetch_b = repo.get_monthly_conversation(biz_b, 2026, 10)
    assert len(fetch_b.messages) == 1
    assert "pasta menu" in fetch_b.messages[0].content
    assert "legal briefing" not in fetch_b.messages[0].content


def test_caption_draft_and_version_isolation(repo):
    biz_a = "biz_corp_a"
    biz_b = "biz_corp_b"

    cap_a = CaptionDraft(
        id="cap_a_1",
        business_id=biz_a,
        month="October",
        year=2026,
        week_number=1,
        suggested_date="2026-10-06",
        platform="LinkedIn",
        caption_text="Civil engineering precision.",
        concept_title="Bridge Milestone",
        source_type=CaptionSourceType.USER_EVENT,
        tone="Authoritative",
        voice="Engineering Leader",
    )
    cap_b = CaptionDraft(
        id="cap_b_1",
        business_id=biz_b,
        month="October",
        year=2026,
        week_number=1,
        suggested_date="2026-10-06",
        platform="Instagram",
        caption_text="Fresh handmade pasta every evening.",
        concept_title="Pasta Special",
        source_type=CaptionSourceType.USER_EVENT,
        tone="Warm and Welcoming",
        voice="Friendly Host",
    )

    repo.save_caption(biz_a, cap_a)
    repo.save_caption(biz_b, cap_b)

    # Business A only sees its own captions
    caps_a = repo.list_captions(biz_a)
    assert len(caps_a) == 1
    assert caps_a[0].id == "cap_a_1"

    caps_b = repo.list_captions(biz_b)
    assert len(caps_b) == 1
    assert caps_b[0].id == "cap_b_1"

    # Business B cannot access or restore Business A's caption
    assert repo.get_caption(biz_b, "cap_a_1") is None
    with pytest.raises(KeyError):
        repo.update_caption_revision(biz_b, "cap_a_1", "Malicious overwrite attempt")


def test_news_approval_and_rejection_isolation(repo):
    biz_a = "biz_npo_1"
    biz_b = "biz_law_2"

    art_shared_topic = NewsArticle(
        id="art_shared_99",
        title="Municipal Grant Program Update",
        source="Civic Gazette",
        url="https://example.com/civic/grants",
        publication_date="2026-10-01",
        summary="City council expands funding criteria.",
        relevance="Relevant to local operations.",
        industry="nonprofit",
    )

    repo.save_discovered_news(biz_a, [art_shared_topic])
    repo.save_discovered_news(biz_b, [art_shared_topic])

    # Business A approves the article
    repo.approve_news_article(biz_a, "art_shared_99")
    # Business B rejects the article
    repo.reject_news_article(biz_b, "art_shared_99")

    # Assert distinct states
    art_a = repo.get_news_article(biz_a, "art_shared_99")
    art_b = repo.get_news_article(biz_b, "art_shared_99")

    assert art_a.approval_status == ArticleApprovalStatus.APPROVED_AWAITING_PLATFORMS
    assert art_b.approval_status == ArticleApprovalStatus.REJECTED

    # Rejection in Business B does not affect Business A
    assert not repo.is_article_rejected(biz_a, "art_shared_99")
    assert repo.is_article_rejected(biz_b, "art_shared_99")


def test_cascading_deletion_isolation(repo):
    biz_a = "biz_delete_target"
    biz_b = "biz_surviving"

    # Setup data for both
    prof_a = BusinessProfile.create_from_onboarding(
        OnboardingInput(
            business_name="Target Corp",
            industry=IndustryType.RESTAURANT,
            business_description="Dining",
            business_location="City A",
        ),
        business_id=biz_a,
    )
    prof_b = BusinessProfile.create_from_onboarding(
        OnboardingInput(
            business_name="Surviving Corp",
            industry=IndustryType.LAW_OFFICE,
            business_description="Law",
            business_location="City B",
        ),
        business_id=biz_b,
    )
    repo.save_profile(prof_a)
    repo.save_profile(prof_b)

    repo.get_or_create_monthly_conversation(biz_a, 2026, 10, "October")
    repo.get_or_create_monthly_conversation(biz_b, 2026, 10, "October")

    # Wipe Business A
    repo.delete_all_business_data(biz_a)

    # Business A data is gone
    assert not repo.exists(biz_a)
    assert repo.get_profile(biz_a) is None
    assert len(repo.list_monthly_conversations(biz_a)) == 0

    # Business B data is 100% intact
    assert repo.exists(biz_b)
    assert repo.get_profile(biz_b) is not None
    assert len(repo.list_monthly_conversations(biz_b)) == 1
