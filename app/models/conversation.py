"""Monthly conversation and chat message models for SoCo Agent."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """An individual message in a monthly strategy conversation."""
    id: str
    conversation_id: str
    business_id: str
    role: str = Field(description="'user' or 'model'")
    content: str
    card_type: str | None = Field(default=None, description="Optional card type: 'observance', 'news', 'caption', 'platform_prompt'")
    card_data: dict[str, Any] | None = Field(default=None, description="Structured card payload")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class MonthlyConversation(BaseModel):
    """Container for an entire calendar month's strategic conversation thread."""
    id: str = Field(description="Format: conv_{business_id}_{year}_{month:02d}")
    business_id: str
    year: int
    month: int
    month_name: str
    status: str = Field(default="active", description="'active' or 'archived'")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    summary: str | None = None
    messages: list[ChatMessage] = Field(default_factory=list)
