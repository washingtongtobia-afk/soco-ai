"""Authentication interfaces and data models for SoCo Agent."""

from __future__ import annotations

import abc
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class AuthUser(BaseModel):
    """Authenticated user representing a business account holder."""
    uid: str
    email: str
    email_verified: bool = False
    business_id: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class BaseAuthService(abc.ABC):
    """Abstract authentication service interface."""

    @abc.abstractmethod
    def register_business(
        self,
        email: str,
        password: str,
        invitation_code: str,
    ) -> AuthUser:
        """Register a new business account requiring valid invitation code."""
        raise NotImplementedError

    @abc.abstractmethod
    def login_business(
        self,
        email: str,
        password: str,
    ) -> tuple[AuthUser, str]:
        """Authenticate user and return user object with signed session token."""
        raise NotImplementedError

    @abc.abstractmethod
    def verify_token(self, token: str) -> AuthUser:
        """Cryptographically verify session token and return authenticated user."""
        raise NotImplementedError

    @abc.abstractmethod
    def logout(self, token: str) -> bool:
        """Invalidate active session token."""
        raise NotImplementedError

    @abc.abstractmethod
    def request_password_reset(self, email: str) -> str:
        """Generate password reset token for user email."""
        raise NotImplementedError

    @abc.abstractmethod
    def reset_password(self, reset_token: str, new_password: str) -> bool:
        """Apply new password using reset token."""
        raise NotImplementedError

    @abc.abstractmethod
    def verify_email(self, email_verification_token: str) -> bool:
        """Mark email as verified using verification token."""
        raise NotImplementedError

    @abc.abstractmethod
    def delete_account(self, uid: str) -> bool:
        """Permanently delete user authentication credentials."""
        raise NotImplementedError
