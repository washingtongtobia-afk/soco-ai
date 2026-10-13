"""Unit tests for the four industry configurations and deterministic tone/voice."""

import pytest
from app.config.industries import (
    INDUSTRY_PROFILES,
    get_industry_profile,
    list_supported_industries,
)
from app.models.industry import IndustryType


def test_four_industries_defined():
    """Verify all four required industries are present."""
    supported = list_supported_industries()
    assert len(supported) == 4
    ids = {p.id for p in supported}
    assert ids == {
        IndustryType.CONSTRUCTION_CIVIL_ENGINEERING,
        IndustryType.NONPROFIT,
        IndustryType.RESTAURANT,
        IndustryType.LAW_OFFICE,
    }


def test_construction_civil_engineering_profile():
    """Verify Construction / Civil Engineering tone and voice match specifications."""
    profile = get_industry_profile(IndustryType.CONSTRUCTION_CIVIL_ENGINEERING)
    assert profile.tone == "Professional, confident, and informative"
    assert profile.voice == "Technical, authoritative, and accessible"
    assert any("Infrastructure" in f for f in profile.focus_areas)
    assert any("CivilEngineering" in t for t in profile.recommended_hashtags)


def test_nonprofit_profile():
    """Verify Nonprofit tone and voice match specifications."""
    profile = get_industry_profile(IndustryType.NONPROFIT)
    assert profile.tone == "Compassionate, encouraging, and community-focused"
    assert profile.voice == "Empathetic, informative, and action-oriented"
    assert any("Community" in f for f in profile.focus_areas)
    assert any("NonprofitWork" in t for t in profile.recommended_hashtags)


def test_restaurant_profile():
    """Verify Restaurant tone and voice match specifications."""
    profile = get_industry_profile(IndustryType.RESTAURANT)
    assert profile.tone == "Friendly, engaging, and conversational"
    assert profile.voice == "Welcoming, energetic, and promotional"
    assert any("Food safety" in f or "Culinary" in f for f in profile.focus_areas)
    assert any("EatLocal" in t for t in profile.recommended_hashtags)


def test_law_office_profile():
    """Verify Law Office tone and voice match specifications."""
    profile = get_industry_profile(IndustryType.LAW_OFFICE)
    assert profile.tone == "Professional, reassuring, and informative"
    assert profile.voice == "Authoritative, trustworthy, and clear"
    assert any("enacted statutes" in f.lower() for f in profile.focus_areas)
    assert any("LegalInsights" in t for t in profile.recommended_hashtags)


def test_industry_resolution_from_strings():
    """Verify flexible string aliases resolve deterministically."""
    assert get_industry_profile("construction").id == IndustryType.CONSTRUCTION_CIVIL_ENGINEERING
    assert get_industry_profile("Civil Engineering").id == IndustryType.CONSTRUCTION_CIVIL_ENGINEERING
    assert get_industry_profile("nonprofit").id == IndustryType.NONPROFIT
    assert get_industry_profile("charity").id == IndustryType.NONPROFIT
    assert get_industry_profile("restaurant").id == IndustryType.RESTAURANT
    assert get_industry_profile("dining").id == IndustryType.RESTAURANT
    assert get_industry_profile("law office").id == IndustryType.LAW_OFFICE
    assert get_industry_profile("legal").id == IndustryType.LAW_OFFICE

    with pytest.raises(ValueError):
        get_industry_profile("unknown_crypto_broker")
