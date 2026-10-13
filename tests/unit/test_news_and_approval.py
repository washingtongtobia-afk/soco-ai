"""Unit tests for ongoing industry news discovery and human approval workflow."""

from app.models.industry import IndustryType
from app.models.news import ArticleApprovalStatus
from app.models.profile import BusinessProfile, OnboardingInput
from app.news.news_service import MockNewsDiscoveryService
from app.planning.approval_service import ApprovalManager
from app.planning.caption_generator import CaptionGenerator


def test_news_discovery_across_four_industries():
    """Verify discovery service yields tailored, structured news for all 4 industries."""
    service = MockNewsDiscoveryService()

    for ind in IndustryType:
        profile = BusinessProfile.create_from_onboarding(OnboardingInput(
            business_name=f"Sample {ind.value}",
            industry=ind,
            business_description="Specialized operations and localized delivery",
            business_location="Phoenix, AZ",
        ))
        articles = service.discover_news(profile)
        assert len(articles) > 0
        for art in articles:
            assert art.id != ""
            assert art.title != ""
            assert art.source != ""
            assert art.url.startswith("https://")
            assert art.summary != ""
            assert art.relevance != ""
            assert art.approval_status == ArticleApprovalStatus.PENDING

            # For Law Office: verify distinction between enacted laws and proposed bills
            if ind == IndustryType.LAW_OFFICE:
                assert art.law_status in ("enacted", "effective", "proposed_bill")


def test_human_approval_gate_and_caption_flow():
    """Verify explicit approval/rejection and that only approved articles become captions."""
    mgr = ApprovalManager()
    gen = CaptionGenerator()
    service = MockNewsDiscoveryService()

    profile = BusinessProfile.create_from_onboarding(OnboardingInput(
        business_name="BridgeWorks Engineering",
        industry=IndustryType.CONSTRUCTION_CIVIL_ENGINEERING,
        business_description="Bridge retrofitting and seismic rehabilitation",
        business_location="San Francisco, CA",
        preferred_platforms=["LinkedIn"],
    ))

    articles = service.discover_news(profile)
    mgr.register_articles(articles)

    art1 = articles[0]
    art2 = articles[1]

    # Explicit human approval and rejection
    mgr.approve_article(art1.id)
    mgr.reject_article(art2.id)

    assert mgr.get_article(art1.id).approval_status == ArticleApprovalStatus.APPROVED
    assert mgr.get_article(art2.id).approval_status == ArticleApprovalStatus.REJECTED

    # Only approved articles can proceed to caption generation
    approved_list = mgr.get_approved_articles()
    assert len(approved_list) == 1
    assert approved_list[0].id == art1.id

    plan = gen.generate_monthly_plan(
        profile=profile,
        year=2026,
        month=10,
        month_name="October",
        approved_articles=approved_list,
    )

    all_caps = [c for week in plan.captions_by_week.values() for c in week]
    approved_captions = [c for c in all_caps if c.concept_title == art1.title]
    rejected_captions = [c for c in all_caps if c.concept_title == art2.title]

    assert len(approved_captions) == 1
    assert len(rejected_captions) == 0
    # Tone and voice preserved in news-based caption
    assert approved_captions[0].tone == "Professional, confident, and informative"


def test_web_search_news_discovery_parsing_and_law_status():
    """Verify parsing logic, URL extraction from grounding metadata, and legal status."""
    from unittest.mock import MagicMock
    from app.news.news_service import WebSearchNewsDiscoveryService

    service = WebSearchNewsDiscoveryService()
    profile = BusinessProfile.create_from_onboarding(OnboardingInput(
        business_name="Desert Law Group",
        industry=IndustryType.LAW_OFFICE,
        business_description="Commercial litigation and corporate compliance",
        business_location="Phoenix, AZ",
    ))

    # Mock response with grounding chunks and JSON array
    mock_response = MagicMock()
    mock_response.text = """
    ```json
    [
      {
        "title": "HB 2045: Commercial Arbitration Transparency Act",
        "source": "State Legislature",
        "url": "https://example.com/placeholder",
        "publication_date": "2026-09-15",
        "summary": "Proposed bill to mandate additional disclosure on commercial arbitration clauses.",
        "relevance": "Directly impacts corporate client contract drafting.",
        "tags": ["Arbitration", "Legislation"],
        "law_status": "proposed_bill"
      },
      {
        "title": "State Supreme Court Issues E-Filing Ruling",
        "source": "Judicial Branch",
        "url": "https://courts.az.gov/orders/efiling-2026",
        "publication_date": "2026-10-01",
        "summary": "Enacted judicial rule updates mandatory electronic discovery procedures.",
        "relevance": "Affects litigation procedural timelines.",
        "tags": ["Courts", "CivilProcedure"],
        "law_status": "effective"
      }
    ]
    ```
    """
    mock_chunk = MagicMock()
    mock_chunk.web.uri = "https://vertexaisearch.cloud.google.com/grounding-redirect-real"
    mock_response.candidates = [MagicMock()]
    mock_response.candidates[0].grounding_metadata.grounding_chunks = [mock_chunk]

    articles = service._parse_grounded_response(mock_response, profile, max_results=2)
    assert len(articles) == 2

    # Article 1: proposed bill, placeholder URL replaced with grounding chunk
    assert articles[0].law_status == "proposed_bill"
    assert articles[0].approval_status == ArticleApprovalStatus.PENDING
    assert articles[0].url == "https://vertexaisearch.cloud.google.com/grounding-redirect-real"

    # Article 2: effective law, preserved real URL
    assert articles[1].law_status == "effective"
    assert articles[1].approval_status == ArticleApprovalStatus.PENDING
    assert articles[1].url == "https://courts.az.gov/orders/efiling-2026"


def test_failed_live_search_never_presents_mock_as_factual():
    """Verify failed live searches raise an error and NEVER present mock/synthetic news as factual."""
    from unittest.mock import patch
    import pytest
    from app.news.news_service import WebSearchNewsDiscoveryService

    service = WebSearchNewsDiscoveryService(allow_synthetic_fallback=False)
    profile = BusinessProfile.create_from_onboarding(OnboardingInput(
        business_name="Civic Builders",
        industry=IndustryType.CONSTRUCTION_CIVIL_ENGINEERING,
        business_description="Urban stormwater and structural engineering",
        business_location="Phoenix, AZ",
    ))

    with patch.object(service, "_discover_live_news", side_effect=RuntimeError("Search network timeout")):
        with pytest.raises(RuntimeError) as exc_info:
            service.discover_news(profile, max_results=3)
        assert "Synthetic mock data is withheld" in str(exc_info.value)


def test_synthetic_news_clearly_labeled_as_demo_data():
    """Verify synthetic mock data is always explicitly labeled as demo/test data."""
    from app.news.news_service import MockNewsDiscoveryService

    mock_service = MockNewsDiscoveryService()
    profile = BusinessProfile.create_from_onboarding(OnboardingInput(
        business_name="Civic Builders",
        industry=IndustryType.CONSTRUCTION_CIVIL_ENGINEERING,
        business_description="Urban stormwater and structural engineering",
        business_location="Phoenix, AZ",
    ))

    articles = mock_service.discover_news(profile, max_results=3)
    assert len(articles) == 3
    for art in articles:
        assert art.is_synthetic is True
        assert "[Demo]" in art.source
        assert "DemoData" in art.tags


def test_web_search_explicit_demo_fallback_mode():
    """Verify demo mode with allow_synthetic_fallback=True returns labeled demo data."""
    from unittest.mock import patch
    from app.news.news_service import WebSearchNewsDiscoveryService

    service = WebSearchNewsDiscoveryService(allow_synthetic_fallback=True)
    profile = BusinessProfile.create_from_onboarding(OnboardingInput(
        business_name="Civic Builders",
        industry=IndustryType.CONSTRUCTION_CIVIL_ENGINEERING,
        business_description="Urban stormwater and structural engineering",
        business_location="Phoenix, AZ",
    ))

    with patch.object(service, "_discover_live_news", side_effect=RuntimeError("Simulated API failure")):
        articles = service.discover_news(profile, max_results=3)
        assert len(articles) == 3
        for art in articles:
            assert art.is_synthetic is True
            assert "[Demo]" in art.source
            assert "DemoData" in art.tags


def test_live_web_search_news_discovery_e2e():
    """Live test calling Gemini with Google Search grounding."""
    from app.news.news_service import WebSearchNewsDiscoveryService

    service = WebSearchNewsDiscoveryService()
    profile = BusinessProfile.create_from_onboarding(OnboardingInput(
        business_name="Southwest Civil Solutions",
        industry=IndustryType.CONSTRUCTION_CIVIL_ENGINEERING,
        business_description="Municipal infrastructure and highway modernization",
        business_location="Phoenix, AZ",
    ))

    articles = service.discover_news(profile, max_results=2)
    assert len(articles) > 0
    for art in articles:
        assert art.is_synthetic is False
        assert art.id.startswith("art_")
        assert len(art.title) > 5
        assert art.source != ""
        assert not art.source.startswith("[Demo]")
        assert art.url.startswith("http://") or art.url.startswith("https://")
        assert len(art.publication_date) >= 7
        assert len(art.summary) > 20
        assert len(art.relevance) > 10
        assert art.approval_status == ArticleApprovalStatus.PENDING

