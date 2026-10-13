"""Unit tests for onboarding and persistent business profile storage."""

from pathlib import Path
import pytest
from app.models.industry import IndustryType
from app.models.profile import BusinessProfile, OnboardingInput
from app.storage.profile_store import LocalJsonProfileStore


@pytest.fixture
def temp_store(tmp_path: Path):
    """Fixture providing isolated temporary profile store."""
    return LocalJsonProfileStore(storage_dir=tmp_path)


def test_onboarding_auto_assigns_tone_and_voice():
    """Verify onboarding automatically assigns industry tone and voice."""
    onboard_data = OnboardingInput(
        business_name="Apex Civil Partners",
        industry=IndustryType.CONSTRUCTION_CIVIL_ENGINEERING,
        business_description="Bridge inspection and municipal roadway grading",
        business_location="Denver, CO",
        preferred_platforms=["LinkedIn", "Instagram"],
    )
    profile = BusinessProfile.create_from_onboarding(onboard_data)

    assert profile.business_name == "Apex Civil Partners"
    assert profile.industry == IndustryType.CONSTRUCTION_CIVIL_ENGINEERING
    # Auto-assigned tone and voice
    assert profile.tone == "Professional, confident, and informative"
    assert profile.voice == "Technical, authoritative, and accessible"


def test_persistent_profile_storage(temp_store: LocalJsonProfileStore):
    """Verify profiles persist, load for returning users, and support updates."""
    # 1. New user has no profile
    assert not temp_store.exists("biz_1")
    assert temp_store.get_profile("biz_1") is None

    # 2. Save profile
    onboard_data = OnboardingInput(
        business_name="Hope Community Center",
        industry=IndustryType.NONPROFIT,
        business_description="Emergency food pantry and family shelter resources",
        business_location="Austin, TX",
        preferred_platforms=["Facebook", "Instagram"],
    )
    profile = BusinessProfile.create_from_onboarding(onboard_data, business_id="biz_1")
    temp_store.save_profile(profile)

    # 3. Returning user automatically retrieves saved profile
    assert temp_store.exists("biz_1")
    loaded = temp_store.get_profile("biz_1")
    assert loaded is not None
    assert loaded.business_name == "Hope Community Center"
    assert loaded.tone == "Compassionate, encouraging, and community-focused"
    assert loaded.voice == "Empathetic, informative, and action-oriented"

    # 4. Update profile details
    updated = temp_store.update_profile("biz_1", {"business_location": "Round Rock, TX"})
    assert updated.business_location == "Round Rock, TX"

    reloaded = temp_store.get_profile("biz_1")
    assert reloaded.business_location == "Round Rock, TX"
