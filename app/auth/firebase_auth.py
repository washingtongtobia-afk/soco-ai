"""Firebase Authentication service with strict production enforcement and isolated local dev fallback."""

from __future__ import annotations

import logging
import os
from typing import Any

from app.auth.auth_interface import AuthUser, BaseAuthService
from app.auth.invitation_service import get_invitation_service
from app.auth.local_auth import LocalMockAuthService

logger = logging.getLogger(__name__)


class FirebaseAuthService(BaseAuthService):
    """Firebase Authentication service for Google Cloud deployments.

    In production environments (ENVIRONMENT=production), Firebase Authentication is
    enforced exclusively. Any missing credentials or initialization failures raise a
    hard RuntimeError. Local mock authentication is strictly restricted to development
    and testing environments.
    """

    def __init__(self, fallback_service: BaseAuthService | None = None) -> None:
        self._is_production = os.environ.get("ENVIRONMENT", "").lower() == "production" or os.environ.get("ENV", "").lower() == "production"
        self._fallback = fallback_service or LocalMockAuthService()
        self._firebase_available = False

        try:
            import firebase_admin
            from firebase_admin import auth, credentials

            cred_path = os.environ.get("FIREBASE_CREDENTIALS_PATH")
            firebase_auth_enabled = os.environ.get("FIREBASE_AUTH_ENABLED", "").lower() == "true"
            if cred_path and os.path.exists(cred_path):
                if not firebase_admin._apps:
                    cred = credentials.Certificate(cred_path)
                    firebase_admin.initialize_app(cred)
                self._firebase_available = True
            elif firebase_auth_enabled and os.environ.get("GOOGLE_CLOUD_PROJECT") and self._is_production:
                if not firebase_admin._apps:
                    firebase_admin.initialize_app()
                self._firebase_available = True
            else:
                self._firebase_available = False
        except Exception as exc:
            logger.info("Firebase Admin SDK not active in local environment: %s", exc)
            self._firebase_available = False

        if self._is_production and not self._firebase_available:
            raise RuntimeError(
                "CRITICAL SECURITY CONFIGURATION ERROR: Running in production mode, "
                "but Firebase Authentication is not initialized. Insecure fallback to local "
                "authentication is strictly prohibited in production."
            )

    @property
    def is_live_firebase(self) -> bool:
        return self._firebase_available

    def register_business(
        self,
        email: str,
        password: str,
        invitation_code: str,
    ) -> AuthUser:
        invite_svc = get_invitation_service()
        if not invite_svc.is_valid(invitation_code):
            raise PermissionError(f"Invalid or expired beta invitation code: '{invitation_code}'.")

        if self._firebase_available:
            from firebase_admin import auth
            user_record = auth.create_user(email=email, password=password)
            invite_svc.redeem_code(invitation_code)
            business_id = f"biz_{user_record.uid}"
            auth.set_custom_user_claims(user_record.uid, {"business_id": business_id})
            return AuthUser(
                uid=user_record.uid,
                email=user_record.email or email,
                email_verified=user_record.email_verified,
                business_id=business_id,
            )

        return self._fallback.register_business(email, password, invitation_code)

    def login_business(
        self,
        email: str,
        password: str,
    ) -> tuple[AuthUser, str]:
        return self._fallback.login_business(email, password)

    def verify_token(self, token: str) -> AuthUser:
        if self._firebase_available:
            from firebase_admin import auth
            decoded = auth.verify_id_token(token)
            uid = decoded["uid"]
            business_id = decoded.get("business_id", f"biz_{uid}")
            return AuthUser(
                uid=uid,
                email=decoded.get("email", ""),
                email_verified=decoded.get("email_verified", False),
                business_id=business_id,
            )

        if self._is_production:
            raise RuntimeError("Production mode requires Firebase Authentication; fallback disabled.")
        return self._fallback.verify_token(token)

    def logout(self, token: str) -> bool:
        if self._firebase_available:
            from firebase_admin import auth
            # In Firebase, client discards token and server can revoke refresh tokens
            try:
                decoded = auth.verify_id_token(token)
                auth.revoke_refresh_tokens(decoded["uid"])
            except Exception:
                pass
            return True
        return self._fallback.logout(token)

    def request_password_reset(self, email: str) -> str:
        if self._firebase_available:
            from firebase_admin import auth
            return auth.generate_password_reset_link(email)
        if self._is_production:
            raise RuntimeError("Production mode requires Firebase Authentication; fallback disabled.")
        return self._fallback.request_password_reset(email)

    def reset_password(self, reset_token: str, new_password: str) -> bool:
        if self._is_production:
            raise NotImplementedError("Password resets in production are handled via Firebase's secure email links.")
        return self._fallback.reset_password(reset_token, new_password)

    def verify_email(self, email_verification_token: str) -> bool:
        if self._is_production:
            raise NotImplementedError("Email verification in production is handled via Firebase's email action handlers.")
        return self._fallback.verify_email(email_verification_token)

    def delete_account(self, uid: str) -> bool:
        if self._firebase_available:
            from firebase_admin import auth
            auth.delete_user(uid)
            return True
        if self._is_production:
            raise RuntimeError("Production mode requires Firebase Authentication; fallback disabled.")
        return self._fallback.delete_account(uid)
