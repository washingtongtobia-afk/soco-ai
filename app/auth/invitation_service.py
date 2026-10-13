"""Secure invitation code registry and validation service for private beta access."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
import secrets
import threading
from typing import Sequence
from app.models.invitation import InvitationCode


class InvitationService:
    """Thread-safe invitation management enforcing private beta access with secure, unguessable codes."""

    def __init__(self, seed_codes: Sequence[str] | None = None) -> None:
        self._lock = threading.Lock()
        self._codes: dict[str, InvitationCode] = {}

        if seed_codes is not None:
            for c in seed_codes:
                self.create_invitation(code=c, max_uses=1, notes="Test seed invitation")
        else:
            # Load active invitation keys from environment variable if provided
            # Format: CODE:max_uses:notes,CODE2:max_uses:notes
            env_keys_raw = os.environ.get("SOCO_INITIAL_INVITATION_CODES", "").strip()
            if env_keys_raw:
                for item in env_keys_raw.split(","):
                    item = item.strip()
                    if not item:
                        continue
                    parts = item.split(":", 2)
                    code = parts[0].strip()
                    max_uses = int(parts[1].strip()) if len(parts) > 1 and parts[1].strip().isdigit() else 5
                    notes = parts[2].strip() if len(parts) > 2 else "Configured invite key"
                    self.create_invitation(code=code, max_uses=max_uses, notes=notes)
            else:
                # Safe development placeholder keys when running locally without explicit env configuration
                dev_keys = [
                    ("SOCO-DEV-MASTER-KEY", 10, "Development master key"),
                    ("SOCO-DEV-CIVIL-KEY", 5, "Development civil engineering cohort key"),
                    ("SOCO-DEV-NONPROFIT-KEY", 5, "Development nonprofit cohort key"),
                    ("SOCO-DEV-RESTAURANT-KEY", 5, "Development restaurant cohort key"),
                    ("SOCO-DEV-LEGAL-KEY", 5, "Development law office cohort key"),
                ]
                for code, max_uses, notes in dev_keys:
                    self.create_invitation(code=code, max_uses=max_uses, notes=notes)

    def generate_secure_invitation(
        self,
        max_uses: int = 1,
        expires_days: int = 30,
        notes: str | None = None,
    ) -> InvitationCode:
        """Generate a cryptographically unguessable, high-entropy invitation code (e.g. SOCO-A7F92B104D38E591)."""
        token = secrets.token_hex(8).upper()
        code = f"SOCO-{token}"
        expires_at = (datetime.now(timezone.utc) + timedelta(days=expires_days)).isoformat()
        return self.create_invitation(code=code, max_uses=max_uses, expires_at=expires_at, notes=notes)

    def create_invitation(
        self,
        code: str,
        max_uses: int = 1,
        expires_at: str | None = None,
        notes: str | None = None,
    ) -> InvitationCode:
        """Register a valid invitation code."""
        with self._lock:
            clean_code = code.strip().upper()
            invite = InvitationCode(
                code=clean_code,
                max_uses=max_uses,
                expires_at=expires_at,
                notes=notes,
            )
            self._codes[clean_code] = invite
            return invite

    def is_valid(self, code: str) -> bool:
        """Check if an invitation code is currently valid and unexhausted."""
        with self._lock:
            clean_code = code.strip().upper()
            invite = self._codes.get(clean_code)
            if not invite:
                return False
            return invite.is_valid()

    def redeem_code(self, code: str) -> bool:
        """Validate and redeem an invitation code upon successful registration."""
        with self._lock:
            clean_code = code.strip().upper()
            invite = self._codes.get(clean_code)
            if not invite or not invite.is_valid():
                return False
            invite.mark_used()
            return True

    def revoke_code(self, code: str) -> bool:
        """Deactivate an invitation code."""
        with self._lock:
            clean_code = code.strip().upper()
            invite = self._codes.get(clean_code)
            if invite:
                invite.active = False
                return True
            return False

    def list_codes(self) -> list[InvitationCode]:
        """List all codes for administration."""
        with self._lock:
            return list(self._codes.values())


# Global singleton instance
_INVITATION_SERVICE: InvitationService | None = None


def get_invitation_service() -> InvitationService:
    """Return default configured invitation service."""
    global _INVITATION_SERVICE
    if _INVITATION_SERVICE is None:
        _INVITATION_SERVICE = InvitationService()
    return _INVITATION_SERVICE
