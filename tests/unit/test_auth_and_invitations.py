"""Unit tests for Phase 2 authentication and private beta invitation enforcement."""

import pytest
from app.auth.auth_interface import AuthUser
from app.auth.invitation_service import InvitationService
from app.auth.local_auth import LocalMockAuthService


def test_invitation_code_validation_and_exhaustion():
    inv_svc = InvitationService(seed_codes=[])
    code = inv_svc.create_invitation("TEST-INVITE-2026", max_uses=2)

    assert inv_svc.is_valid("TEST-INVITE-2026")
    assert inv_svc.is_valid("test-invite-2026")  # Case insensitive
    assert not inv_svc.is_valid("INVALID-CODE")

    # Redeem once
    assert inv_svc.redeem_code("TEST-INVITE-2026")
    assert inv_svc.is_valid("TEST-INVITE-2026")

    # Redeem second time -> should exhaust
    assert inv_svc.redeem_code("TEST-INVITE-2026")
    assert not inv_svc.is_valid("TEST-INVITE-2026")
    assert not inv_svc.redeem_code("TEST-INVITE-2026")


def test_registration_requires_valid_invitation():
    auth_svc = LocalMockAuthService()
    inv_svc = InvitationService(seed_codes=["BETA-ALLOWED"])
    from app.auth import invitation_service
    invitation_service._INVITATION_SERVICE = inv_svc

    # Attempt registration with invalid code -> must raise PermissionError
    with pytest.raises(PermissionError) as exc:
        auth_svc.register_business(
            email="test@example.com",
            password="SecurePassword123!",
            invitation_code="BAD-CODE",
        )
    assert "Invalid or expired beta invitation code" in str(exc.value)

    # Attempt with valid code -> succeeds
    user = auth_svc.register_business(
        email="test@example.com",
        password="SecurePassword123!",
        invitation_code="BETA-ALLOWED",
    )
    assert user.uid.startswith("usr_")
    assert user.business_id.startswith("biz_")
    assert user.email == "test@example.com"
    assert not user.email_verified


def test_password_hashing_and_credential_security():
    auth_svc = LocalMockAuthService()
    inv_svc = InvitationService(seed_codes=["BETA-HASH-TEST"])
    from app.auth import invitation_service
    invitation_service._INVITATION_SERVICE = inv_svc

    user = auth_svc.register_business(
        email="security@example.com",
        password="MySecretPassword99!",
        invitation_code="BETA-HASH-TEST",
    )

    # Check internal storage: password must NOT be stored in plaintext
    record = auth_svc._users["security@example.com"]
    assert "MySecretPassword99!" not in str(record)
    assert "hash" in record
    assert "salt" in record
    assert len(record["hash"]) == 64  # SHA-256 hex string


def test_token_creation_verification_and_revocation():
    auth_svc = LocalMockAuthService()
    inv_svc = InvitationService(seed_codes=["BETA-TOKEN-TEST"])
    from app.auth import invitation_service
    invitation_service._INVITATION_SERVICE = inv_svc

    user = auth_svc.register_business(
        email="token@example.com",
        password="Password123456!",
        invitation_code="BETA-TOKEN-TEST",
    )

    _, token = auth_svc.login_business("token@example.com", "Password123456!")
    assert "." in token

    # Verify valid token
    verified_user = auth_svc.verify_token(token)
    assert verified_user.uid == user.uid
    assert verified_user.business_id == user.business_id

    # Tampered token must fail
    tampered = token[:-4] + "abcd"
    with pytest.raises(PermissionError):
        auth_svc.verify_token(tampered)

    # Revoke via logout
    auth_svc.logout(token)
    with pytest.raises(PermissionError) as exc:
        auth_svc.verify_token(token)
    assert "Session token has been invalidated" in str(exc.value)


def test_password_reset_and_email_verification():
    auth_svc = LocalMockAuthService()
    inv_svc = InvitationService(seed_codes=["BETA-RESET-TEST"])
    from app.auth import invitation_service
    invitation_service._INVITATION_SERVICE = inv_svc

    user = auth_svc.register_business(
        email="reset@example.com",
        password="OldPassword123!",
        invitation_code="BETA-RESET-TEST",
    )

    # Email verification
    v_token = auth_svc.request_email_verification(user.uid)
    assert auth_svc.verify_email(v_token)
    u_updated = auth_svc.login_business("reset@example.com", "OldPassword123!")[0]
    assert u_updated.email_verified

    # Password reset
    reset_token = auth_svc.request_password_reset("reset@example.com")
    assert auth_svc.reset_password(reset_token, "BrandNewPassword456!")

    # Old password fails, new password succeeds
    with pytest.raises(PermissionError):
        auth_svc.login_business("reset@example.com", "OldPassword123!")
    _, new_tok = auth_svc.login_business("reset@example.com", "BrandNewPassword456!")
    assert new_tok is not None


def test_cryptographically_secure_invitation_generation():
    inv_svc = InvitationService(seed_codes=[])
    code1 = inv_svc.generate_secure_invitation(max_uses=1, expires_days=14)
    code2 = inv_svc.generate_secure_invitation(max_uses=1, expires_days=14)

    assert code1.code.startswith("SOCO-")
    assert len(code1.code) >= 21  # "SOCO-" + 16 hex chars
    assert code1.code != code2.code  # High-entropy uniqueness
    assert code1.max_uses == 1
    assert inv_svc.is_valid(code1.code)

    # Single-use redemption
    assert inv_svc.redeem_code(code1.code)
    assert not inv_svc.is_valid(code1.code)


def test_production_mode_strictly_prohibits_local_auth_fallback(monkeypatch):
    from app.auth.firebase_auth import FirebaseAuthService
    monkeypatch.setenv("ENVIRONMENT", "production")

    # In production without live Firebase SDK initialized, must raise RuntimeError
    with pytest.raises(RuntimeError) as exc:
        FirebaseAuthService()
    assert "CRITICAL SECURITY CONFIGURATION ERROR" in str(exc.value)
