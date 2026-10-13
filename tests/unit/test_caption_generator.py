"""Unit tests for industry-specific caption generation."""

from app.models.caption import CaptionStatus
from app.models.industry import IndustryType
from app.models.profile import BusinessProfile, OnboardingInput
from app.planning.caption_generator import CaptionGenerator


def test_caption_draft_generation_restaurant():
    """Verify generated captions for Restaurant adhere to friendly/conversational tone and draft status."""
    gen = CaptionGenerator()
    profile = BusinessProfile.create_from_onboarding(OnboardingInput(
        business_name="Trattoria Bella",
        industry=IndustryType.RESTAURANT,
        business_description="Artisanal wood-fired pizzas and fresh pasta",
        business_location="Seattle, WA",
        preferred_platforms=["Instagram", "Facebook"],
    ))

    plan = gen.generate_monthly_plan(
        profile=profile,
        year=2026,
        month=11,
        month_name="November",
        user_activities=["Fall Truffle Pasta Launch", "Thanksgiving Wine Pairing Dinner"],
    )

    assert plan.total_captions > 0
    # Captions must be organized by week
    assert len(plan.captions_by_week) >= 4

    # All generated captions must remain drafts until reviewed
    for week_num, caps in plan.captions_by_week.items():
        for cap in caps:
            assert cap.status == CaptionStatus.DRAFT
            assert cap.tone == "Friendly, engaging, and conversational"
            assert cap.voice == "Welcoming, energetic, and promotional"
            assert cap.suggested_date != ""
            assert len(cap.hashtags) > 0


def test_caption_draft_generation_law_office():
    """Verify generated captions for Law Office adhere to professional/reassuring tone and include disclaimers."""
    gen = CaptionGenerator()
    profile = BusinessProfile.create_from_onboarding(OnboardingInput(
        business_name="Harborview Legal Group",
        industry=IndustryType.LAW_OFFICE,
        business_description="Commercial contract litigation and corporate compliance",
        business_location="Boston, MA",
        preferred_platforms=["LinkedIn"],
    ))

    plan = gen.generate_monthly_plan(
        profile=profile,
        year=2026,
        month=10,
        month_name="October",
        user_activities=["Annual Compliance Audit Seminar"],
    )

    assert plan.total_captions > 0
    all_caps = [c for week in plan.captions_by_week.values() for c in week]
    # Check tone and disclaimer
    assert any("Informational legal overview" in c.caption_text for c in all_caps)
    for c in all_caps:
        assert c.status == CaptionStatus.DRAFT
        assert c.tone == "Professional, reassuring, and informative"
        assert c.voice == "Authoritative, trustworthy, and clear"
