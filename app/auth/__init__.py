"""Authentication package for SoCo Agent."""

from app.auth.auth_interface import AuthUser, BaseAuthService
from app.auth.firebase_auth import FirebaseAuthService
from app.auth.invitation_service import InvitationService, get_invitation_service
from app.auth.local_auth import LocalMockAuthService

_AUTH_SERVICE: BaseAuthService | None = None


def get_auth_service() -> BaseAuthService:
    """Return default configured auth service."""
    global _AUTH_SERVICE
    if _AUTH_SERVICE is None:
        _AUTH_SERVICE = FirebaseAuthService()
    return _AUTH_SERVICE


def set_auth_service(service: BaseAuthService) -> None:
    """Override auth service for testing."""
    global _AUTH_SERVICE
    _AUTH_SERVICE = service


__all__ = [
    "AuthUser",
    "BaseAuthService",
    "FirebaseAuthService",
    "InvitationService",
    "LocalMockAuthService",
    "get_auth_service",
    "get_invitation_service",
    "set_auth_service",
]
