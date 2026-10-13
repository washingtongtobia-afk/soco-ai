"""In-app notifications and email preference models."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field


class EmailDigestFrequency(str, Enum):
    """User preference for email news digests."""
    WEEKLY = "weekly"
    DAILY = "daily"
    OFF = "off"


class NotificationPreferences(BaseModel):
    """Notification settings for an authenticated business."""
    business_id: str
    email: str
    email_digest_frequency: EmailDigestFrequency = EmailDigestFrequency.WEEKLY
    email_verified: bool = False
    in_app_enabled: bool = True
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class InAppNotification(BaseModel):
    """A proactive notification displayed in SoCo's notification center."""
    id: str
    business_id: str
    title: str
    body: str
    type: str = Field(default="news_discovered", description="'news_discovered', 'digest_ready', 'system'")
    article_id: str | None = None
    action_url: str | None = None
    read: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
