"""Invitation code models for private beta access control."""

from __future__ import annotations

from datetime import datetime, timezone
from pydantic import BaseModel, Field


class InvitationCode(BaseModel):
    """An authorization token permitting business account creation during private beta."""
    code: str
    max_uses: int = 1
    used_count: int = 0
    active: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: str | None = None
    created_by: str = "system_admin"
    notes: str | None = None

    def is_valid(self) -> bool:
        """Check if code can be redeemed."""
        if not self.active:
            return False
        if self.used_count >= self.max_uses:
            return False
        if self.expires_at:
            now = datetime.now(timezone.utc).isoformat()
            if now > self.expires_at:
                return False
        return True

    def mark_used(self) -> None:
        """Increment usage count and deactivate if limit reached."""
        self.used_count += 1
        if self.used_count >= self.max_uses:
            self.active = False
