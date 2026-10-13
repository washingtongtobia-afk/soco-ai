"""Caption quality, factual grounding, and writing evaluation tests (Day 4B).

Validates:
- No generic / forbidden clichés ("We are excited to announce", etc.) across all 4 industries
- Explicit labeling of deterministic fallback drafts when AI is offline
- High-quality AI caption generation with mocked LLM responses (independent of live credentials)
- Strong factual grounding: detects invented URLs, unverified pricing, times, and superlatives
- Mandatory legal disclaimers for law offices
- Shortest effective length selection (short, medium, long)
- Representative generated caption examples for all four industries
"""

from unittest.mock import patch
import pytest

from app.config.industries import get_industry_profile
from app.models.caption import CaptionDraft, CaptionSourceType, CaptionStatus
from app.models.industry import IndustryType
from app.models.profile import BusinessProfile, OnboardingInput
from app.planning.ai_caption_engine import (
    FALLBACK_DRAFT_LABEL,
    FORBIDDEN_OPENINGS,
    CaptionLength,
    determine_caption_length,
    generate_caption,
    validate_caption_output,
)


@pytest.fixture
def profiles_all_industries() -> dict[IndustryType, BusinessProfile]:
    return {
        IndustryType.CONSTRUCTION_CIVIL_ENGINEERING: BusinessProfile.create_from_onboarding(OnboardingInput(
            business_name="Apex Structural Partners",
            industry=IndustryType.CONSTRUCTION_CIVIL_ENGINEERING,
            business_description="Seismic retrofits, municipal bridge engineering, and LEED-certified commercial construction",
            business_location="Seattle, WA",
            preferred_platforms=["LinkedIn", "Instagram"],
        )),
        IndustryType.NONPROFIT: BusinessProfile.create_from_onboarding(OnboardingInput(
            business_name="Hope Harbor Community Alliance",
            industry=IndustryType.NONPROFIT,
            business_description="Nutritious food pantry distribution, transitional family housing, and youth literacy programs",
            business_location="Houston, TX",
            preferred_platforms=["Facebook", "Instagram", "LinkedIn"],
        )),
        IndustryType.RESTAURANT: BusinessProfile.create_from_onboarding(OnboardingInput(
            business_name="Osteria Del Sole",
            industry=IndustryType.RESTAURANT,
            business_description="Seasonal farm-to-table Tuscan trattoria specializing in handcrafted pasta and natural wines",
            business_location="Chicago, IL",
            preferred_platforms=["Instagram", "Facebook", "X"],
        )),
        IndustryType.LAW_OFFICE: BusinessProfile.create_from_onboarding(OnboardingInput(
            business_name="Vanguard Legal Counsel",
            industry=IndustryType.LAW_OFFICE,
            business_description="Employment defense, commercial dispute litigation, and corporate compliance counseling",
            business_location="Boston, MA",
            preferred_platforms=["LinkedIn"],
        )),
    }


def test_no_forbidden_openings_in_fallback_across_all_four_industries(
    profiles_all_industries: dict[IndustryType, BusinessProfile]
):
    """Fallback captions must never lead with forbidden generic clichés for any industry or source."""
    sources = [
        (CaptionSourceType.USER_EVENT, "Q4 Growth Announcement"),
        (CaptionSourceType.FEDERAL_HOLIDAY, "Labor Day"),
        (CaptionSourceType.INDUSTRY_OBSERVANCE, "National Safety Stand-Down"),
        (CaptionSourceType.APPROVED_NEWS, "New State Compliance Guidelines"),
    ]

    for ind, profile in profiles_all_industries.items():
        for src_type, concept in sources:
            text, is_ai, warnings = generate_caption(
                profile=profile,
                concept_title=concept,
                source_type=src_type,
                platform="LinkedIn",
                extra_details="Key updates for the regional community.",
            )

            # Clean out the fallback draft label banner
            clean = text.replace(FALLBACK_DRAFT_LABEL, "").strip().lower()

            for forbidden in FORBIDDEN_OPENINGS:
                assert not clean.startswith(forbidden), (
                    f"Forbidden opening '{forbidden}' found in {ind.value} ({src_type.value}): {text}"
                )


def test_fallback_captions_explicitly_labeled_as_drafts(
    profiles_all_industries: dict[IndustryType, BusinessProfile]
):
    """When AI is unavailable, captions must be labeled with the explicit draft review banner."""
    profile = profiles_all_industries[IndustryType.RESTAURANT]
    with patch("app.planning.ai_caption_engine.is_ai_available", return_value=False):
        text, is_ai, warnings = generate_caption(
            profile=profile,
            concept_title="Fall White Truffle Dinner",
            source_type=CaptionSourceType.USER_EVENT,
            platform="Instagram",
            extra_details="Five-course tasting menu paired with Piedmont wines.",
        )

        assert is_ai is False
        assert text.startswith(FALLBACK_DRAFT_LABEL)
        assert "Osteria Del Sole" in text
        assert any("fallback" in w.lower() for w in warnings)


def test_ai_caption_generation_with_mocked_model(
    profiles_all_industries: dict[IndustryType, BusinessProfile]
):
    """When AI generation succeeds, returns natural copy without fallback label and flags is_ai=True."""
    profile = profiles_all_industries[IndustryType.CONSTRUCTION_CIVIL_ENGINEERING]
    mock_caption = (
        "Crews at Apex Structural Partners completed the final girder placement on the Spokane Street Bridge retrofit. "
        "Engineered for 75-year seismic resilience, this municipal milestone keeps commuters safe. "
        "#CivilEngineering #Infrastructure #SeattleEngineering"
    )

    with patch("app.planning.ai_caption_engine.is_ai_available", return_value=True), \
         patch("app.planning.ai_caption_engine.call_model", return_value=mock_caption):

        text, is_ai, warnings = generate_caption(
            profile=profile,
            concept_title="Spokane Street Bridge Seismic Retrofit",
            source_type=CaptionSourceType.USER_EVENT,
            platform="LinkedIn",
            extra_details="Completed final girder placement on Spokane Street Bridge.",
        )

        assert is_ai is True
        assert FALLBACK_DRAFT_LABEL not in text
        assert "Apex Structural Partners" in text
        assert "Spokane Street Bridge" in text


def test_factual_grounding_rejects_invented_urls(
    profiles_all_industries: dict[IndustryType, BusinessProfile]
):
    """Validation detects and rejects invented URLs that were not supplied in the input."""
    profile = profiles_all_industries[IndustryType.RESTAURANT]
    hallucinated_copy = (
        "Handcrafted pasta tonight at Osteria Del Sole! "
        "Claim your 50% discount at https://unauthorized-deals-portal.com/claim-now."
    )

    val = validate_caption_output(
        caption_text=hallucinated_copy,
        profile=profile,
        concept_title="Pasta Night",
        extra_details="Serving fresh tagliatelle in Chicago.",
        source_type=CaptionSourceType.USER_EVENT,
    )

    assert val.is_valid is False
    assert len(val.invented_urls) == 1
    assert "https://unauthorized-deals-portal.com/claim-now" in val.invented_urls[0]


def test_factual_grounding_flags_unsupported_pricing_and_times(
    profiles_all_industries: dict[IndustryType, BusinessProfile]
):
    """Validation flags specific prices, discounts, and times not present in source context."""
    profile = profiles_all_industries[IndustryType.RESTAURANT]
    unsupported_claims_copy = (
        "Join us at Osteria Del Sole tonight at 7:30 pm where bottles of Chianti are $14.99 and 35% off appetizers."
    )

    val = validate_caption_output(
        caption_text=unsupported_claims_copy,
        profile=profile,
        concept_title="Evening Wine Special",
        extra_details="Featuring selected Chianti wines this Thursday.",
        source_type=CaptionSourceType.USER_EVENT,
    )

    # Claims are captured in unsupported_claims and warnings
    assert any("7:30 pm" in c for c in val.unsupported_claims)
    assert any("$14.99" in c or "35% off" in c for c in val.unsupported_claims)


def test_factual_grounding_flags_unsupported_superlatives(
    profiles_all_industries: dict[IndustryType, BusinessProfile]
):
    """Validation flags unverified superlatives and guarantees for human review."""
    profile = profiles_all_industries[IndustryType.CONSTRUCTION_CIVIL_ENGINEERING]
    copy_with_superlatives = (
        "Apex Structural Partners is voted #1 in the nation with 100% guaranteed zero-delay delivery on every bridge project."
    )

    val = validate_caption_output(
        caption_text=copy_with_superlatives,
        profile=profile,
        concept_title="Bridge Delivery",
        extra_details="Delivering quality infrastructure in Seattle.",
        source_type=CaptionSourceType.USER_EVENT,
    )

    assert any("voted #1" in c or "100% guaranteed" in c for c in val.unsupported_claims)


def test_law_office_mandatory_disclaimer_enforced(
    profiles_all_industries: dict[IndustryType, BusinessProfile]
):
    """Law Office captions must always include the mandatory informational disclaimer."""
    profile = profiles_all_industries[IndustryType.LAW_OFFICE]
    mock_law_caption = (
        "Recent appellate court opinions clarify employer non-compete enforceability across Massachusetts. "
        "Proactive review of severance policies safeguards against regulatory non-compliance."
    )

    with patch("app.planning.ai_caption_engine.is_ai_available", return_value=True), \
         patch("app.planning.ai_caption_engine.call_model", return_value=mock_law_caption):

        text, is_ai, warnings = generate_caption(
            profile=profile,
            concept_title="Appellate Non-Compete Ruling",
            source_type=CaptionSourceType.APPROVED_NEWS,
            platform="LinkedIn",
            extra_details="Source: Massachusetts Law Weekly. Clarified employer non-compete enforceability.",
        )

        assert is_ai is True
        assert "Informational legal overview; not formal legal representation." in text


def test_shortest_effective_length_selection():
    """Verify dynamic length category selection based on platform and content depth."""
    # Short platforms
    assert determine_caption_length("X", CaptionSourceType.USER_EVENT) == CaptionLength.SHORT
    assert determine_caption_length("Twitter", CaptionSourceType.USER_EVENT) == CaptionLength.SHORT
    assert determine_caption_length("Instagram Reels", CaptionSourceType.USER_EVENT) == CaptionLength.SHORT

    # Brief holiday on standard platform
    assert determine_caption_length("LinkedIn", CaptionSourceType.FEDERAL_HOLIDAY, "Office closed") == CaptionLength.SHORT

    # Standard feed update
    assert determine_caption_length("LinkedIn", CaptionSourceType.USER_EVENT, "Community workshop") == CaptionLength.MEDIUM

    # In-depth statutory/regulatory update
    long_statutory_text = (
        "The newly enacted Chapter 128 statutes establish stringent oversight mechanisms for commercial subcontractors. "
        "Beginning in Q1 2027, municipal engineering firms must document carbon offset credits, seismic testing data, "
        "and certified payroll compliance across all public infrastructure contracts exceeding $2.5 million."
    )
    assert determine_caption_length("LinkedIn", CaptionSourceType.APPROVED_NEWS, long_statutory_text) == CaptionLength.LONG


def test_representative_caption_examples_inspection(
    profiles_all_industries: dict[IndustryType, BusinessProfile]
):
    """Generate and display representative captions for all 4 industries across multiple source types."""
    scenarios = [
        (IndustryType.CONSTRUCTION_CIVIL_ENGINEERING, "Seismic Foundation Pour on Pier 54", CaptionSourceType.USER_EVENT, "LinkedIn", "Pouring 400 cubic yards of high-durability concrete for deep marine pilings."),
        (IndustryType.NONPROFIT, "Annual Thanksgiving Food Drive Kickoff", CaptionSourceType.USER_EVENT, "Facebook", "Collecting non-perishable staples and holiday meal boxes to serve 800 Houston families."),
        (IndustryType.RESTAURANT, "Autumn Alba Truffle & Barolo Weekend", CaptionSourceType.USER_EVENT, "Instagram", "Shaved white truffles over house-made tajarin pasta with vintage Barolo pairings."),
        (IndustryType.LAW_OFFICE, "2026 Commercial Lease Dispute Guidelines", CaptionSourceType.APPROVED_NEWS, "LinkedIn", "Source: Boston Legal Review. Key appellate updates on commercial lease escalation clauses."),
    ]

    print("\n" + "=" * 80)
    print("REPRESENTATIVE CAPTION EXAMPLES ACROSS ALL FOUR INDUSTRIES")
    print("=" * 80)

    for ind, concept, src_type, platform, details in scenarios:
        profile = profiles_all_industries[ind]
        text, is_ai, warnings = generate_caption(
            profile=profile,
            concept_title=concept,
            source_type=src_type,
            platform=platform,
            extra_details=details,
        )

        assert text != ""
        assert len(text) > 40
        # If fallback, ensure properly labeled
        if not is_ai:
            assert text.startswith(FALLBACK_DRAFT_LABEL)
        # If law office, ensure disclaimer
        if ind == IndustryType.LAW_OFFICE:
            assert "Informational legal overview" in text

        print(f"\n--- [{ind.value.upper()}] | {platform} | {concept} ---")
        print(f"AI Generated: {is_ai}")
        print(f"Warnings: {warnings}")
        print(f"Caption:\n{text}\n")

    print("=" * 80 + "\n")
