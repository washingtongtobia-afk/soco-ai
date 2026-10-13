"""Unit tests for the news approval workflow with mandatory platform selection before caption generation."""

import pytest
from app.models.industry import IndustryType
from app.models.news import ArticleApprovalStatus, NewsArticle
from app.models.profile import BusinessProfile, OnboardingInput
from app.planning.caption_generator import CaptionGenerator
from app.planning.multi_tenant_approval import MultiTenantApprovalManager
from app.storage.firestore_store import LocalDocumentRepository, set_persistence_repository


@pytest.fixture
def clean_env():
    repo = LocalDocumentRepository()
    set_persistence_repository(repo)
    mgr = MultiTenantApprovalManager()
    return repo, mgr


def test_approval_prompts_for_platforms_before_caption_generation(clean_env):
    repo, mgr = clean_env
    biz_id = "biz_news_workflow_1"

    profile = BusinessProfile.create_from_onboarding(
        OnboardingInput(
            business_name="Beacon Legal Partners",
            industry=IndustryType.LAW_OFFICE,
            business_description="Corporate compliance and employment law advisory",
            business_location="Chicago, IL",
            preferred_platforms=["LinkedIn", "X"],
        ),
        business_id=biz_id,
    )
    repo.save_profile(profile)

    article = NewsArticle(
        id="art_law_888",
        business_id=biz_id,
        title="State Department Issues New Paid Leave Guidelines",
        source="Illinois Legal Gazette",
        url="https://example.com/law/paid-leave-2026",
        publication_date="2026-10-02",
        summary="Updated workplace compliance requirements take effect next quarter.",
        relevance="Directly impacts corporate employment compliance clients.",
        industry="law_office",
        law_status="effective",
    )
    mgr.register_articles(biz_id, [article])

    # 1. Initial State: Pending
    assert mgr.get_article(biz_id, "art_law_888").approval_status == ArticleApprovalStatus.PENDING

    # 2. Approve: Must NOT generate captions immediately; must transition to awaiting platforms and prompt
    approved_art, prompt = mgr.approve_article(biz_id, "art_law_888")
    assert approved_art.approval_status == ArticleApprovalStatus.APPROVED_AWAITING_PLATFORMS
    assert "Which social media platform(s)" in prompt
    assert len(mgr.list_captions(biz_id)) == 0  # No captions generated yet!

    # 3. Select Platforms: Transitions to APPROVED and enables caption generation
    updated_art = mgr.select_platforms_for_article(biz_id, "art_law_888", ["LinkedIn"])
    assert updated_art.approval_status == ArticleApprovalStatus.APPROVED
    assert updated_art.selected_platforms == ["LinkedIn"]

    # 4. Generate captions for approved article with selected platforms
    gen = CaptionGenerator()
    plan = gen.generate_monthly_plan(
        profile=profile,
        year=2026,
        month=10,
        month_name="October",
        approved_articles=[updated_art],
    )
    caps = [c for week in plan.captions_by_week.values() for c in week if c.concept_title == article.title]
    assert len(caps) > 0
    mgr.register_captions(biz_id, caps)

    saved_caps = mgr.list_captions(biz_id)
    assert len(saved_caps) > 0
    assert saved_caps[0].concept_title == article.title


def test_news_rejection_and_duplicate_prevention(clean_env):
    repo, mgr = clean_env
    biz_id = "biz_news_reject_2"

    art = NewsArticle(
        id="art_reject_99",
        business_id=biz_id,
        title="Unrelated Industry Gossip",
        source="Blog",
        url="https://example.com/gossip",
        publication_date="2026-10-01",
        summary="Rumors about regional supplier.",
        relevance="Low relevance.",
        industry="restaurant",
    )
    mgr.register_articles(biz_id, [art])

    # Reject article
    rejected = mgr.reject_article(biz_id, "art_reject_99")
    assert rejected.approval_status == ArticleApprovalStatus.REJECTED
    assert repo.is_article_rejected(biz_id, "art_reject_99")

    # Attempting to re-discover or save this article again must be ignored
    repo.save_discovered_news(biz_id, [art])
    # Remains rejected
    assert repo.get_news_article(biz_id, "art_reject_99").approval_status == ArticleApprovalStatus.REJECTED
