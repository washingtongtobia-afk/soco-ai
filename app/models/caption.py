"""Caption and monthly planning data models with version history."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field


class CaptionStatus(str, Enum):
    """Lifecycle status for generated captions."""
    DRAFT = "draft"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    REJECTED = "rejected"


class CaptionSourceType(str, Enum):
    """Origin of the caption concept."""
    USER_EVENT = "user_event"
    FEDERAL_HOLIDAY = "federal_holiday"
    SOCIAL_HOLIDAY = "social_holiday"
    INDUSTRY_OBSERVANCE = "industry_observance"
    APPROVED_NEWS = "approved_news"
    ONGOING_THEME = "ongoing_theme"


class CaptionVersion(BaseModel):
    """Historical snapshot of a caption revision."""
    version: int
    caption_text: str
    hashtags: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    note: str | None = None

    @property
    def version_number(self) -> int:
        return self.version

    @property
    def text(self) -> str:
        return self.caption_text

    @property
    def saved_at(self) -> str:
        return self.created_at

    @property
    def change_note(self) -> str | None:
        return self.note

    def model_dump(self, *args, **kwargs):
        d = super().model_dump(*args, **kwargs)
        d["version_number"] = self.version
        d["text"] = self.caption_text
        d["saved_at"] = self.created_at
        d["change_note"] = self.note
        return d


class CaptionDraft(BaseModel):
    """Ready-to-post draft social media caption with version history."""
    id: str
    business_id: str = "default"
    month: str
    year: int
    week_number: int = Field(ge=1, le=5)
    suggested_date: str
    platform: str
    caption_text: str
    hashtags: list[str] = Field(default_factory=list)
    concept_title: str
    source_type: CaptionSourceType
    status: CaptionStatus = CaptionStatus.DRAFT
    tone: str
    voice: str
    notes_for_user: str | None = None
    is_ai_generated: bool = False
    grounding_warnings: list[str] = Field(default_factory=list)
    current_version: int = 1
    version_history: list[CaptionVersion] = Field(default_factory=list)

    @property
    def text(self) -> str:
        return self.caption_text

    @property
    def version_number(self) -> int:
        return self.current_version

    def model_dump(self, *args, **kwargs):
        d = super().model_dump(*args, **kwargs)
        d["text"] = self.caption_text
        d["version_number"] = self.current_version
        return d

    def save_revision(
        self,
        new_text: str,
        new_hashtags: list[str] | None = None,
        note: str | None = None,
    ) -> CaptionVersion:
        """Archive current copy to version history and apply new revision."""
        now_str = datetime.now(timezone.utc).isoformat()
        # Save snapshot of current version before updating
        snapshot = CaptionVersion(
            version=self.current_version,
            caption_text=self.caption_text,
            hashtags=list(self.hashtags),
            created_at=now_str,
            note=note or f"Revision prior to version {self.current_version + 1}",
        )
        self.version_history.append(snapshot)
        self.current_version += 1
        self.caption_text = new_text
        if new_hashtags is not None:
            self.hashtags = new_hashtags
        self.status = CaptionStatus.DRAFT
        return snapshot

    def restore_version(self, target_version: int) -> bool:
        """Restore text and hashtags from a previous version in history."""
        # Check if target is in version history
        for snap in self.version_history:
            if snap.version == target_version:
                # Archive current before restoring
                self.save_revision(
                    new_text=snap.caption_text,
                    new_hashtags=snap.hashtags,
                    note=f"Restored from version {target_version}",
                )
                return True
        return False


class MonthlyPlan(BaseModel):
    """Container for a full month's organized draft captions."""
    business_id: str
    month_name: str
    year: int
    total_captions: int
    captions_by_week: dict[int, list[CaptionDraft]] = Field(default_factory=dict)
    summary: str
