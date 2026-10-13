"""News article and discovery models."""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


class ArticleApprovalStatus(str, Enum):
    """Human approval state of discovered news articles."""
    PENDING = "pending"
    APPROVED_AWAITING_PLATFORMS = "approved_awaiting_platforms"
    APPROVED = "approved"
    REJECTED = "rejected"


class NewsArticle(BaseModel):
    """Structured information for an industry news discovery."""
    id: str
    business_id: str = "default"
    title: str
    source: str
    url: str
    publication_date: str
    summary: str
    relevance: str = Field(description="Explicit explanation of relevance to business mission, location, or industry")
    industry: str
    approval_status: ArticleApprovalStatus = ArticleApprovalStatus.PENDING
    tags: list[str] = Field(default_factory=list)
    law_status: str | None = Field(
        default=None,
        description="For legal news: 'enacted', 'effective', or 'proposed_bill' to prevent confusion",
    )
    is_synthetic: bool = Field(
        default=False,
        description="True only if generated as synthetic demo/test data; False for real live news",
    )
    selected_platforms: list[str] = Field(default_factory=list)
    caption_generated: bool = False
