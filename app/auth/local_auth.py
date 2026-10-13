"""Local development authentication service with cryptographic security and invitation enforcement."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
import uuid
from typing import Any

from app.auth.auth_interface import AuthUser, BaseAuthService
from app.auth.invitation_service import get_invitation_service


class LocalMockAuthService(BaseAuthService):
    """Local, production-grade mock authentication service for testing and development.

    Uses salted PBKDF2-HMAC-SHA256 password hashing and cryptographically signed
    session tokens. Enforces private invitation code redemption.
    """

    def __init__(self, secret_key: str | None = None) -> None:
        self._lock = threading.Lock()
        self._secret = (secret_key or os.environ.get("SOCO_AUTH_SECRET") or secrets.token_hex(32)).encode("utf-8")
        self._users: dict[str, dict[str, Any]] = {}  # email -> record
        self._users_by_uid: dict[str, dict[str, Any]] = {}  # uid -> record
        self._revoked_tokens: set[str] = set()
        self._reset_tokens: dict[str, str] = {}  # reset_token -> uid
        self._verify_tokens: dict[str, str] = {}  # verify_token -> uid

    def _hash_password(self, password: str, salt: bytes | None = None) -> tuple[str, str]:
        """Hash password using PBKDF2-HMAC-SHA256 with 100,000 iterations."""
        if salt is None:
            salt = secrets.token_bytes(16)
        pwd_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            100_000,
        )
        return salt.hex(), pwd_hash.hex()

    def _create_token(self, user: AuthUser, expires_in_seconds: int = 86400) -> str:
        """Create a cryptographically signed session token (HMAC-SHA256)."""
        payload = {
            "uid": user.uid,
            "email": user.email,
            "business_id": user.business_id,
            "email_verified": user.email_verified,
            "exp": int(time.time()) + expires_in_seconds,
            "jti": secrets.token_hex(8),
        }
        encoded_payload = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8").rstrip("=")
        signature = hmac.new(self._secret, encoded_payload.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"{encoded_payload}.{signature}"

    def register_business(
        self,
        email: str,
        password: str,
        invitation_code: str,
    ) -> AuthUser:
        """Register business enforcing invitation code requirement."""
        clean_email = email.strip().lower()
        if not clean_email or "@" not in clean_email:
            raise ValueError("Valid email address is required.")
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long.")

        # 1. Enforce private beta invitation code
        invite_svc = get_invitation_service()
        if not invite_svc.is_valid(invitation_code):
            raise PermissionError(f"Invalid or expired beta invitation code: '{invitation_code}'.")

        with self._lock:
            if clean_email in self._users:
                raise ValueError("An account with this email address already exists.")

            salt_hex, hash_hex = self._hash_password(password)
            uid = f"usr_{uuid.uuid4().hex[:12]}"
            business_id = f"biz_{uuid.uuid4().hex[:12]}"

            user_record = {
                "uid": uid,
                "email": clean_email,
                "salt": salt_hex,
                "hash": hash_hex,
                "business_id": business_id,
                "email_verified": False,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            self._users[clean_email] = user_record
            self._users_by_uid[uid] = user_record

            # Redeem invitation code
            invite_svc.redeem_code(invitation_code)

            # Persist to Firestore if available
            try:
                import google.cloud.firestore
                project = os.environ.get("GOOGLE_CLOUD_PROJECT")
                if project and not os.environ.get("USE_LOCAL_STORAGE"):
                    db = google.cloud.firestore.Client(project=project)
                    db.collection("auth_users").document(uid).set(user_record)
            except Exception:
                pass

            return AuthUser(
                uid=uid,
                email=clean_email,
                email_verified=False,
                business_id=business_id,
                created_at=user_record["created_at"],
            )

    def login_business(
        self,
        email: str,
        password: str,
    ) -> tuple[AuthUser, str]:
        """Authenticate with email/password and issue signed session token."""
        clean_email = email.strip().lower()
        with self._lock:
            record = self._users.get(clean_email)
            if not record:
                try:
                    import google.cloud.firestore
                    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
                    if project and not os.environ.get("USE_LOCAL_STORAGE"):
                        db = google.cloud.firestore.Client(project=project)
                        docs = list(db.collection("auth_users").where("email", "==", clean_email).limit(1).stream())
                        if docs:
                            record = docs[0].to_dict()
                            self._users[clean_email] = record
                            self._users_by_uid[record["uid"]] = record
                except Exception:
                    pass

            if not record:
                raise PermissionError("Invalid email or password.")

            salt = bytes.fromhex(record["salt"])
            _, expected_hash = self._hash_password(password, salt)
            if not hmac.compare_digest(record["hash"], expected_hash):
                raise PermissionError("Invalid email or password.")

            user = AuthUser(
                uid=record["uid"],
                email=record["email"],
                email_verified=record["email_verified"],
                business_id=record["business_id"],
                created_at=record["created_at"],
            )
            token = self._create_token(user)
            return user, token

    def verify_token(self, token: str) -> AuthUser:
        """Verify token cryptographic signature, revocation status, and expiration."""
        if not token or "." not in token:
            raise PermissionError("Malformed authentication token.")

        if token in self._revoked_tokens:
            raise PermissionError("Session token has been invalidated.")

        parts = token.split(".")
        if len(parts) != 2:
            raise PermissionError("Malformed authentication token structure.")

        encoded_payload, signature = parts
        expected_sig = hmac.new(self._secret, encoded_payload.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            raise PermissionError("Invalid token signature.")

        try:
            # Add padding back if necessary
            padding = len(encoded_payload) % 4
            if padding:
                encoded_payload += "=" * (4 - padding)
            payload_json = base64.urlsafe_b64decode(encoded_payload).decode("utf-8")
            payload = json.loads(payload_json)
        except Exception:
            raise PermissionError("Could not decode token payload.")

        if payload.get("exp", 0) < int(time.time()):
            raise PermissionError("Authentication token has expired.")

        uid = payload.get("uid")
        with self._lock:
            record = self._users_by_uid.get(uid)
            if not record:
                try:
                    import google.cloud.firestore
                    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
                    if project and not os.environ.get("USE_LOCAL_STORAGE"):
                        db = google.cloud.firestore.Client(project=project)
                        doc = db.collection("auth_users").document(uid).get()
                        if doc.exists:
                            record = doc.to_dict()
                            self._users[record["email"]] = record
                            self._users_by_uid[uid] = record
                except Exception:
                    pass

            if not record:
                raise PermissionError("User account no longer exists.")

            return AuthUser(
                uid=record["uid"],
                email=record["email"],
                email_verified=record["email_verified"],
                business_id=record["business_id"],
                created_at=record["created_at"],
            )

    def logout(self, token: str) -> bool:
        """Revoke active token."""
        with self._lock:
            self._revoked_tokens.add(token)
            return True

    def request_password_reset(self, email: str) -> str:
        """Generate reset token for user."""
        clean_email = email.strip().lower()
        with self._lock:
            record = self._users.get(clean_email)
            if not record:
                # Security best practice: don't disclose user existence, return dummy token
                return secrets.token_urlsafe(16)
            reset_token = secrets.token_urlsafe(24)
            self._reset_tokens[reset_token] = record["uid"]
            return reset_token

    def reset_password(self, reset_token: str, new_password: str) -> bool:
        """Apply new password using reset token."""
        if len(new_password) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        with self._lock:
            uid = self._reset_tokens.pop(reset_token, None)
            if not uid:
                raise PermissionError("Invalid or expired password reset token.")
            record = self._users_by_uid.get(uid)
            if not record:
                return False
            salt_hex, hash_hex = self._hash_password(new_password)
            record["salt"] = salt_hex
            record["hash"] = hash_hex
            return True

    def request_email_verification(self, uid: str) -> str:
        """Generate email verification token."""
        with self._lock:
            token = secrets.token_urlsafe(24)
            self._verify_tokens[token] = uid
            return token

    def verify_email(self, email_verification_token: str) -> bool:
        """Mark email as verified."""
        with self._lock:
            uid = self._verify_tokens.pop(email_verification_token, None)
            if not uid:
                return False
            record = self._users_by_uid.get(uid)
            if record:
                record["email_verified"] = True
                return True
            return False

    def delete_account(self, uid: str) -> bool:
        """Delete user credentials from memory and persistent Firestore storage."""
        with self._lock:
            record = self._users_by_uid.pop(uid, None)
            if record:
                self._users.pop(record["email"], None)
            try:
                import google.cloud.firestore
                project = os.environ.get("GOOGLE_CLOUD_PROJECT")
                if project and not os.environ.get("USE_LOCAL_STORAGE"):
                    db = google.cloud.firestore.Client(project=project)
                    db.collection("auth_users").document(uid).delete()
            except Exception:
                pass
            return bool(record)
