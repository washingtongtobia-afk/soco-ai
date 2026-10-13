"""Industry and tone/voice models for SoCo Agent."""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


class IndustryType(str, Enum):
    """The four supported industries in SoCo."""
    CONSTRUCTION_CIVIL_ENGINEERING = "construction_civil_engineering"
    NONPROFIT = "nonprofit"
    RESTAURANT = "restaurant"
    LAW_OFFICE = "law_office"

    @classmethod
    def from_str(cls, value: str) -> IndustryType:
        """Resolve industry enum from string or alias."""
        clean = value.strip().lower().replace(" ", "_").replace("/", "_").replace("&", "_").replace("-", "_")
        for member in cls:
            if clean in member.value or member.value in clean:
                return member
        # Fallbacks by keyword
        if "construction" in clean or "civil" in clean or "engineer" in clean:
            return cls.CONSTRUCTION_CIVIL_ENGINEERING
        if "nonprofit" in clean or "charity" in clean or "npo" in clean:
            return cls.NONPROFIT
        if "restaurant" in clean or "food" in clean or "cafe" in clean or "dining" in clean:
            return cls.RESTAURANT
        if "law" in clean or "legal" in clean or "attorney" in clean:
            return cls.LAW_OFFICE
        raise ValueError(f"Unknown industry: '{value}'. Must be one of: {[m.value for m in cls]}")


class IndustryObservance(BaseModel):
    """An industry-specific holiday or awareness observance."""
    name: str
    month: int = Field(ge=1, le=12)
    day: int | None = Field(default=None, ge=1, le=31)
    description: str
    floating_rule: str | None = None
    keywords: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class IndustryProfile(BaseModel):
    """Deterministic tone, voice, and industry configuration profile."""
    id: IndustryType
    display_name: str
    tone: str
    voice: str
    focus_areas: list[str]
    recommended_hashtags: list[str]
    observances: list[IndustryObservance] = Field(default_factory=list)
    writing_guidelines: list[str] = Field(default_factory=list)
