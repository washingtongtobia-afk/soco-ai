"""Business profile and onboarding data models."""

from __future__ import annotations

from datetime import datetime, timezone
from pydantic import BaseModel, Field

from app.config.industries import get_industry_profile
from app.models.industry import IndustryType


class OnboardingInput(BaseModel):
    """Input payload collected during one-time business onboarding."""
    business_name: str = Field(..., description="Legal or operating business name")
    industry: IndustryType = Field(..., description="One of the four supported industries")
    business_description: str = Field(..., description="Description of services, mission, or specialties")
    business_location: str = Field(..., description="City, state, or operating region")
    preferred_platforms: list[str] = Field(
        default_factory=lambda: ["LinkedIn", "Instagram", "Facebook"],
        description="Preferred social platforms (e.g. LinkedIn, Instagram, Facebook, X)",
    )


class BusinessProfile(BaseModel):
    """Persistent business profile with auto-assigned industry tone and voice."""
    business_id: str = Field(default="default", description="Unique identifier for business")
    business_name: str
    industry: IndustryType
    business_description: str
    business_location: str
    preferred_platforms: list[str]
    tone: str
    voice: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @classmethod
    def create_from_onboarding(
        cls,
        data: OnboardingInput,
        business_id: str = "default",
    ) -> BusinessProfile:
        """Create a profile and automatically assign deterministic tone and voice."""
        industry_profile = get_industry_profile(data.industry)
        now_str = datetime.now(timezone.utc).isoformat()
        return cls(
            business_id=business_id,
            business_name=data.business_name,
            industry=data.industry,
            business_description=data.business_description,
            business_location=data.business_location,
            preferred_platforms=data.preferred_platforms,
            tone=industry_profile.tone,
            voice=industry_profile.voice,
            created_at=now_str,
            updated_at=now_str,
        )

    def update(self, **kwargs) -> BusinessProfile:
        """Apply updates and recalculate tone/voice if industry changes."""
        for key, val in kwargs.items():
            if hasattr(self, key) and val is not None:
                setattr(self, key, val)
        if "industry" in kwargs and kwargs["industry"] is not None:
            ind_profile = get_industry_profile(self.industry)
            self.tone = ind_profile.tone
            self.voice = ind_profile.voice
        self.updated_at = datetime.now(timezone.utc).isoformat()
        return self

    def validate_for_generation(self) -> None:
        """Validate profile completeness before social media copy generation.

        Raises ValueError with a clear message if required fields are missing or sparse.
        """
        if not self.business_name or not isinstance(self.business_name, str) or len(self.business_name.strip()) < 2:
            raise ValueError("Valid business name (at least 2 characters) is required for caption generation.")
        if not self.business_location or not isinstance(self.business_location, str) or len(self.business_location.strip()) < 2:
            raise ValueError("Valid business location (at least 2 characters) is required for caption generation.")
        if not self.business_description or not isinstance(self.business_description, str) or len(self.business_description.strip()) < 10:
            raise ValueError("Descriptive business description (at least 10 characters) is required for caption generation.")
        if not self.industry or not isinstance(self.industry, IndustryType):
            raise ValueError("A supported IndustryType is required for caption generation.")

