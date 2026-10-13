"""Backend API Gateway Router for SoCo Agent with secure multi-tenant isolation."""

from __future__ import annotations

import logging
import os
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from app.auth import get_auth_service, get_invitation_service
from app.auth.auth_interface import AuthUser
from app.config.industries import get_industry_profile, list_supported_industries
from app.models.caption import CaptionDraft, CaptionSourceType, CaptionStatus
from app.models.conversation import ChatMessage
from app.models.industry import IndustryType
from app.models.news import ArticleApprovalStatus
from app.models.notification import EmailDigestFrequency, NotificationPreferences
from app.models.profile import BusinessProfile, OnboardingInput
from app.planning.ai_caption_engine import generate_caption
from app.planning.approval_service import sanitize_external_content
from app.planning.calendar_service import format_conversational_opening, get_current_month_info, get_month_observances
from app.planning.caption_generator import _format_hashtags, get_caption_generator
from app.planning.multi_tenant_approval import get_multi_tenant_approval_manager
from app.billing.spending_guard import get_spending_guard
from app.gateway.agent_runtime_client import stream_deployed_reasoning_engine
from app.storage.firestore_store import get_persistence_repository
from app.workflow_nodes import soco_entrypoint_node

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["gateway"])


# Dependency: Verify token and resolve authenticated business identity
async def get_current_user(authorization: str = Header(None)) -> AuthUser:
    """Validate Bearer token and return verified authenticated user."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header. Bearer token required.",
        )
    token = authorization.split(" ", 1)[1].strip()
    auth_svc = get_auth_service()
    try:
        user = auth_svc.verify_token(token)
        return user
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(exc)}",
        )


# Request & Response Schemas
class RegisterRequest(BaseModel):
    email: str
    password: str
    invitation_code: str
    business_name: str
    industry: IndustryType
    business_description: str
    business_location: str
    preferred_platforms: list[str] = ["LinkedIn", "Instagram", "Facebook"]

    @field_validator("industry", mode="before")
    @classmethod
    def parse_industry(cls, v: Any) -> IndustryType:
        if isinstance(v, IndustryType):
            return v
        return IndustryType.from_str(str(v))


class LoginRequest(BaseModel):
    email: str
    password: str


class PasswordResetRequest(BaseModel):
    email: str


class PasswordResetConfirmRequest(BaseModel):
    reset_token: str
    new_password: str


class ChatMessageRequest(BaseModel):
    message: str
    year: int | None = None
    month: int | None = None


class CaptionRevisionRequest(BaseModel):
    new_text: str
    new_hashtags: list[str] | None = None
    note: str | None = None


class CaptionStatusRequest(BaseModel):
    status: CaptionStatus


class PlatformSelectionRequest(BaseModel):
    platforms: list[str] = Field(..., min_length=1)


class NotificationPreferencesRequest(BaseModel):
    email_digest_frequency: EmailDigestFrequency
    in_app_enabled: bool = True


class CreateInvitationRequest(BaseModel):
    code: str | None = None
    max_uses: int = 1
    expires_days: int = 30
    notes: str | None = None


# 1. Authentication & Invitation Endpoints
@router.post("/auth/register")
async def register(req: RegisterRequest):
    """Register a new business account requiring valid beta invitation code."""
    auth_svc = get_auth_service()
    repo = get_persistence_repository()

    try:
        user = auth_svc.register_business(
            email=req.email,
            password=req.password,
            invitation_code=req.invitation_code,
        )
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))

    # Save business profile permanently during registration (never repeated)
    onboarding_data = OnboardingInput(
        business_name=req.business_name,
        industry=req.industry,
        business_description=req.business_description,
        business_location=req.business_location,
        preferred_platforms=req.preferred_platforms,
    )
    profile = BusinessProfile.create_from_onboarding(onboarding_data, business_id=user.business_id)
    repo.save_profile(profile)

    # Initialize notification preferences
    prefs = NotificationPreferences(
        business_id=user.business_id,
        email=user.email,
        email_digest_frequency=EmailDigestFrequency.WEEKLY,
    )
    repo.update_notification_preferences(user.business_id, prefs)

    _, token = auth_svc.login_business(req.email, req.password)
    return {
        "user": user.model_dump(),
        "token": token,
        "profile": profile.model_dump(),
        "message": f"🎉 Welcome to SoCo, {profile.business_name}! Your profile is saved.",
    }


@router.get("/auth/invitation/sample")
async def get_sample_invitation():
    """Return an active invitation code strictly in local development/testing environments."""
    is_production = (
        os.environ.get("ENVIRONMENT", "").lower() == "production"
        or os.environ.get("ENV", "").lower() == "production"
        or bool(os.environ.get("K_SERVICE"))
    )
    if is_production:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Endpoint disabled in production.",
        )

    inv_svc = get_invitation_service()
    valid_codes = [c for c in inv_svc.list_codes() if c.is_valid()]
    if not valid_codes:
        new_inv = inv_svc.generate_secure_invitation(max_uses=5, expires_days=30, notes="Demo evaluation key")
        return {"code": new_inv.code}
    return {"code": valid_codes[0].code}


class DemoLoginRequest(BaseModel):
    industry: IndustryType = IndustryType.CONSTRUCTION_CIVIL_ENGINEERING

    @field_validator("industry", mode="before")
    @classmethod
    def parse_industry(cls, v: Any) -> IndustryType:
        if isinstance(v, IndustryType):
            return v
        return IndustryType.from_str(str(v))


@router.post("/auth/demo-login")
async def demo_login(req: DemoLoginRequest = DemoLoginRequest()):
    """Provision or login an instant functional demo business across all 4 supported industries."""
    is_strict_prod = (
        os.environ.get("ENVIRONMENT", "").lower() == "production"
        or os.environ.get("ENV", "").lower() == "production"
    ) and os.environ.get("ALLOW_DEMO_LOGIN", "").lower() != "true"
    if is_strict_prod:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demo login disabled in production.",
        )

    auth_svc = get_auth_service()
    repo = get_persistence_repository()
    inv_svc = get_invitation_service()

    demo_email = f"demo_{req.industry.value}@soco.local"
    demo_password = "DemoPassword123!"

    demo_defaults = {
        IndustryType.CONSTRUCTION_CIVIL_ENGINEERING: {
            "name": "Skyline Civil Constructors",
            "location": "Atlanta, GA",
            "desc": "Heavy civil infrastructure, bridge foundations, DOT contracts, and structural concrete engineering.",
            "platforms": ["LinkedIn", "Facebook", "Instagram"],
        },
        IndustryType.NONPROFIT: {
            "name": "Hope Forward Foundation",
            "location": "Chicago, IL",
            "desc": "Community food security, urban youth education initiatives, and grassroots donor stewardship.",
            "platforms": ["Instagram", "LinkedIn", "Facebook"],
        },
        IndustryType.RESTAURANT: {
            "name": "Osteria Bella Trattoria",
            "location": "Austin, TX",
            "desc": "Scratch wood-fired Italian dining, handmade pasta specials, and organic regional wine pairings.",
            "platforms": ["Instagram", "Facebook"],
        },
        IndustryType.LAW_OFFICE: {
            "name": "Apex Legal Counsel",
            "location": "Boston, MA",
            "desc": "Corporate advisory, employment compliance, IP protection, and commercial litigation.",
            "platforms": ["LinkedIn", "Facebook"],
        },
    }
    cfg = demo_defaults.get(req.industry, demo_defaults[IndustryType.CONSTRUCTION_CIVIL_ENGINEERING])

    user = None
    token = None
    try:
        user, token = auth_svc.login_business(demo_email, demo_password)
    except Exception:
        pass

    if user is None:
        demo_code = f"SOCO-DEMO-{req.industry.value.upper()[:8]}"
        inv_svc.create_invitation(demo_code, max_uses=9999, notes="Local demo account")
        user = auth_svc.register_business(
            email=demo_email,
            password=demo_password,
            invitation_code=demo_code,
        )
        _, token = auth_svc.login_business(demo_email, demo_password)

    profile = repo.get_profile(user.business_id)
    if not profile:
        onboarding_data = OnboardingInput(
            business_name=cfg["name"],
            industry=req.industry,
            business_description=cfg["desc"],
            business_location=cfg["location"],
            preferred_platforms=cfg["platforms"],
        )
        profile = BusinessProfile.create_from_onboarding(onboarding_data, business_id=user.business_id)
        repo.save_profile(profile)

        prefs = NotificationPreferences(
            business_id=user.business_id,
            email=user.email,
            email_digest_frequency=EmailDigestFrequency.WEEKLY,
        )
        repo.update_notification_preferences(user.business_id, prefs)

    return {
        "user": user.model_dump(),
        "token": token,
        "profile": profile.model_dump(),
        "message": f"⚡ Loaded demo workspace for {profile.business_name}!",
    }


@router.post("/auth/login")
async def login(req: LoginRequest):
    """Authenticate returning business and issue session token."""
    auth_svc = get_auth_service()
    repo = get_persistence_repository()

    try:
        user, token = auth_svc.login_business(req.email, req.password)
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(pe))

    profile = repo.get_profile(user.business_id)
    return {
        "user": user.model_dump(),
        "token": token,
        "profile": profile.model_dump() if profile else None,
    }


@router.post("/auth/logout")
async def logout(authorization: str = Header(None)):
    """Revoke session token."""
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1].strip()
        get_auth_service().logout(token)
    return {"message": "Logged out successfully."}


@router.delete("/auth/account")
async def delete_account(user: AuthUser = Depends(get_current_user)):
    """Permanently delete user account and cascade-delete all business data."""
    repo = get_persistence_repository()
    auth_svc = get_auth_service()

    # Cascade delete all business data
    repo.delete_all_business_data(user.business_id)
    auth_svc.delete_account(user.uid)

    return {"message": "Business account and associated data permanently deleted."}


# 2. Business Profile Endpoints
@router.get("/business/profile")
async def get_profile(user: AuthUser = Depends(get_current_user)):
    """Retrieve verified business profile."""
    repo = get_persistence_repository()
    prof = repo.get_profile(user.business_id)
    if not prof:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found.")
    return prof.model_dump()


@router.put("/business/profile")
async def update_profile(updates: dict, user: AuthUser = Depends(get_current_user)):
    """Update profile settings (tone, voice, location, platforms, industry)."""
    repo = get_persistence_repository()
    try:
        updated = repo.update_profile(user.business_id, updates)
        return updated.model_dump()
    except KeyError as ke:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ke))


# 3. Monthly Conversations & Strategic Chat
@router.get("/conversations/current")
async def get_current_conversation(user: AuthUser = Depends(get_current_user)):
    """Retrieve ongoing monthly conversation or auto-greet for a new month without re-onboarding."""
    repo = get_persistence_repository()
    prof = repo.get_profile(user.business_id)
    if not prof:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business profile not found.")

    year, month, month_name = get_current_month_info()
    conv, created_new = repo.get_or_create_monthly_conversation(user.business_id, year, month, month_name)

    if created_new:
        # Auto-greet with conversational opening for the new month without re-onboarding!
        opening = format_conversational_opening(month_name)
        greeting = (
            f"👋 Hello again, **{prof.business_name}**!\n\n"
            f"**{opening}**\n\n"
            f"Tell me about upcoming promotions, announcements, milestones, or community events, "
            f"or ask me to discover timely industry news."
        )
        # Observances card
        observances = get_month_observances(year, month, prof.industry)
        obs_payload = [o.model_dump() for o in observances]

        welcome_msg = ChatMessage(
            id=f"msg_welcome_{year}_{month:02d}",
            conversation_id=conv.id,
            business_id=user.business_id,
            role="model",
            content=greeting,
            card_type="observances",
            card_data={"observances": obs_payload, "month_name": month_name, "year": year},
        )
        repo.append_message(user.business_id, year, month, welcome_msg)
        conv.messages.append(welcome_msg)

    return conv.model_dump()


@router.get("/conversations/history")
async def list_conversation_history(user: AuthUser = Depends(get_current_user)):
    """List historical monthly conversations for session switcher."""
    repo = get_persistence_repository()
    convs = repo.list_monthly_conversations(user.business_id)
    return [
        {
            "id": c.id,
            "year": c.year,
            "month": c.month,
            "month_name": c.month_name,
            "message_count": len(c.messages),
            "updated_at": c.updated_at,
        }
        for c in convs
    ]


@router.get("/conversations/{year}/{month}")
async def get_monthly_conversation_by_date(
    year: int,
    month: int,
    user: AuthUser = Depends(get_current_user),
):
    """Retrieve specific monthly conversation in read-only review mode."""
    repo = get_persistence_repository()
    conv = repo.get_monthly_conversation(user.business_id, year, month)
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No conversation record found for {year}-{month:02d}.",
        )
    return conv.model_dump()


@router.post("/chat/message")
async def send_chat_message(
    req: ChatMessageRequest,
    user: AuthUser = Depends(get_current_user),
):
    """Send user message to strategist and return response."""
    repo = get_persistence_repository()
    approval_mgr = get_multi_tenant_approval_manager()
    prof = repo.get_profile(user.business_id)
    if not prof:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found.")

    year, month, month_name = get_current_month_info()
    if req.year:
        year = req.year
    if req.month:
        month = req.month

    # 1. Record sanitized user message
    clean_text = sanitize_external_content(req.message)
    user_msg = ChatMessage(
        id=f"msg_usr_{int(year)}_{int(month)}_{user.business_id[:6]}_{id(clean_text)}",
        conversation_id=f"conv_{user.business_id}_{year}_{month:02d}",
        business_id=user.business_id,
        role="user",
        content=clean_text,
    )
    repo.append_message(user.business_id, year, month, user_msg)

    # 2. Spending guard check: enforce rate limit, daily/monthly allowance, and $20 auto-suspension
    guard = get_spending_guard()
    allowed, guard_reason = guard.can_proceed(user.business_id)
    if not allowed:
        model_msg = ChatMessage(
            id=f"msg_guard_{year}_{month:02d}_{id(guard_reason)}",
            conversation_id=f"conv_{user.business_id}_{year}_{month:02d}",
            business_id=user.business_id,
            role="model",
            content=guard_reason,
            card_type="spending_limit",
            card_data=guard.get_business_usage(user.business_id),
        )
        repo.append_message(user.business_id, year, month, model_msg)
        return {
            "message": model_msg.model_dump(),
            "total_captions": 0,
        }

    # 3. Stream from deployed Reasoning Engine on Agent Runtime or local unified ADK entrypoint
    use_remote = os.environ.get("USE_REMOTE_AGENT_RUNTIME", "").lower() in ("true", "1")
    event_stream = None
    if use_remote:
        try:
            event_stream = stream_deployed_reasoning_engine(
                text=clean_text,
                business_id=user.business_id,
                year=year,
                month=month,
                month_name=month_name,
            )
        except Exception as exc:
            logger.warning("Remote Reasoning Engine call failed, falling back to local ADK node: %s", exc)
            event_stream = None

    if event_stream is None:
        node_input = {
            "text": clean_text,
            "business_id": user.business_id,
            "year": year,
            "month": month,
            "month_name": month_name,
        }
        event_stream = soco_entrypoint_node(node_input)

    resp_text_parts: list[str] = []
    card_type: str | None = None
    card_data: dict[str, Any] | None = None
    total_captions: int = 0

    async for event in event_stream:
        if event.content and event.content.parts:
            for part in event.content.parts:
                if getattr(part, "text", None):
                    resp_text_parts.append(part.text)
        if getattr(event, "output", None) and isinstance(event.output, dict):
            out = event.output
            if "card_type" in out:
                card_type = out["card_type"]
            if "card_data" in out:
                card_data = out["card_data"]
            if "total_captions" in out:
                total_captions = out["total_captions"]

    if total_captions == 0 and card_data and "captions" in card_data:
        total_captions = len(card_data["captions"])

    resp_content = "\n\n".join(resp_text_parts) if resp_text_parts else "No response generated."

    # Record token consumption and compute cost in spending guard
    input_tokens = max(50, len(clean_text.split()) * 4 + 250)
    output_tokens = max(30, len(resp_content.split()) * 4)
    guard.record_usage(user.business_id, input_tokens=input_tokens, output_tokens=output_tokens)

    model_msg = ChatMessage(
        id=f"msg_mod_{year}_{month:02d}_{id(resp_content)}",
        conversation_id=f"conv_{user.business_id}_{year}_{month:02d}",
        business_id=user.business_id,
        role="model",
        content=resp_content,
        card_type=card_type,
        card_data=card_data,
    )
    repo.append_message(user.business_id, year, month, model_msg)

    return {
        "message": model_msg.model_dump(),
        "total_captions": total_captions,
    }


@router.get("/business/usage")
async def get_business_usage(user: AuthUser = Depends(get_current_user)):
    """Retrieve quota consumption and remaining allowance for authenticated business."""
    guard = get_spending_guard()
    return guard.get_business_usage(user.business_id)


@router.get("/admin/spending")
async def get_system_spending(user: AuthUser = Depends(get_current_user)):
    """Retrieve portfolio-level budget status, tracking metrics, and safeguard health."""
    if user.email.endswith("@soco.local") or user.email.startswith("demo_"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Demo accounts are restricted from administrative spending controls.",
        )
    guard = get_spending_guard()
    return guard.get_system_summary().model_dump()


@router.get("/admin/invitations")
async def list_admin_invitations(user: AuthUser = Depends(get_current_user)):
    """List active private beta invitation codes (Restricted to non-demo administrators)."""
    if user.email.endswith("@soco.local") or user.email.startswith("demo_"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Demo accounts are restricted from private invitation management.",
        )
    inv_svc = get_invitation_service()
    return [c.model_dump() for c in inv_svc.list_codes()]


@router.post("/admin/invitations")
async def create_admin_invitation(
    req: CreateInvitationRequest,
    user: AuthUser = Depends(get_current_user),
):
    """Generate or register a new beta invitation code (Restricted to non-demo administrators)."""
    if user.email.endswith("@soco.local") or user.email.startswith("demo_"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Demo accounts are restricted from private invitation management.",
        )
    inv_svc = get_invitation_service()
    if req.code:
        inv = inv_svc.create_invitation(req.code, max_uses=req.max_uses, notes=req.notes)
    else:
        inv = inv_svc.generate_secure_invitation(
            max_uses=req.max_uses,
            expires_days=req.expires_days,
            notes=req.notes,
        )
    return inv.model_dump()


# 4. Caption Editing, Versions & Restoration
@router.get("/captions")
async def list_captions(
    month: str | None = None,
    year: int | None = None,
    user: AuthUser = Depends(get_current_user),
):
    """List saved draft captions for authenticated business."""
    repo = get_persistence_repository()
    caps = repo.list_captions(user.business_id, month=month, year=year)
    return [c.model_dump() for c in caps]


@router.post("/captions/{caption_id}/revise")
async def revise_caption(
    caption_id: str,
    req: CaptionRevisionRequest,
    user: AuthUser = Depends(get_current_user),
):
    """Revise caption copy while preserving historical version in version history."""
    repo = get_persistence_repository()
    try:
        updated = repo.update_caption_revision(
            user.business_id,
            caption_id,
            new_text=req.new_text,
            new_hashtags=req.new_hashtags,
            note=req.note,
        )
        return updated.model_dump()
    except KeyError as ke:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ke))


@router.post("/captions/{caption_id}/restore/{version_num}")
async def restore_caption_version(
    caption_id: str,
    version_num: int,
    user: AuthUser = Depends(get_current_user),
):
    """Restore previous version of a caption."""
    repo = get_persistence_repository()
    try:
        restored = repo.restore_caption_version(user.business_id, caption_id, version_num)
        return restored.model_dump()
    except (KeyError, ValueError) as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.post("/captions/{caption_id}/status")
async def update_caption_status(
    caption_id: str,
    req: CaptionStatusRequest,
    user: AuthUser = Depends(get_current_user),
):
    """Update caption approval status (all remain drafts until finalized)."""
    repo = get_persistence_repository()
    try:
        updated = repo.update_caption_status(user.business_id, caption_id, req.status)
        return updated.model_dump()
    except KeyError as ke:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ke))


# 5. News Approval Workflow with Platform Selection
@router.get("/news")
async def list_news(user: AuthUser = Depends(get_current_user)):
    """List pending, approved, and rejected news for authenticated business."""
    repo = get_persistence_repository()
    articles = repo.list_news(user.business_id)
    return [a.model_dump() for a in articles]


@router.post("/news/{article_id}/approve")
async def approve_news_article(
    article_id: str,
    user: AuthUser = Depends(get_current_user),
):
    """Approve news article and prompt for social media platforms before generating captions."""
    approval_mgr = get_multi_tenant_approval_manager()
    try:
        article, prompt = approval_mgr.approve_article(user.business_id, article_id)
        return {
            "article": article.model_dump(),
            "prompt": prompt,
            "status": "approved_awaiting_platforms",
            "message": "Article approved. Please specify which social media platform(s) to create captions for.",
        }
    except KeyError as ke:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ke))


@router.post("/news/{article_id}/select-platforms")
async def select_platforms_for_news(
    article_id: str,
    req: PlatformSelectionRequest,
    user: AuthUser = Depends(get_current_user),
):
    """Finalize platform selection and generate draft captions for approved news."""
    approval_mgr = get_multi_tenant_approval_manager()
    repo = get_persistence_repository()
    prof = repo.get_profile(user.business_id)
    if not prof:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found.")

    try:
        article = approval_mgr.select_platforms_for_article(user.business_id, article_id, req.platforms)
    except (KeyError, ValueError) as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))

    # Generate draft captions specifically for the approved article on the selected platforms
    industry_profile = get_industry_profile(prof.industry)
    year, month, month_name = get_current_month_info()
    created_captions: list[CaptionDraft] = []

    for plt in req.platforms:
        text, is_ai, warnings = generate_caption(
            profile=prof,
            concept_title=article.title,
            source_type=CaptionSourceType.APPROVED_NEWS,
            platform=plt,
            extra_details=article.summary,
        )
        cap_id = f"cap_news_{article.id[:8]}_{plt.lower()[:4]}"
        cap = CaptionDraft(
            id=cap_id,
            business_id=user.business_id,
            month=month_name,
            year=year,
            week_number=3,
            suggested_date=f"{year}-{month:02d}-15",
            platform=plt,
            caption_text=text,
            hashtags=_format_hashtags(industry_profile.recommended_hashtags, article.title),
            concept_title=article.title,
            source_type=CaptionSourceType.APPROVED_NEWS,
            status=CaptionStatus.DRAFT,
            tone=prof.tone,
            voice=prof.voice,
            notes_for_user=f"Draft generated from approved news article '{article.title}'.",
            is_ai_generated=is_ai,
            grounding_warnings=warnings,
        )
        created_captions.append(cap)
        repo.save_caption(user.business_id, cap)

    approval_mgr.register_captions(user.business_id, created_captions)

    return {
        "article": article.model_dump(),
        "created_captions": [c.model_dump() for c in created_captions],
        "message": f"Generated {len(created_captions)} draft captions across: {', '.join(req.platforms)}.",
    }


@router.post("/news/{article_id}/reject")
async def reject_news_article(
    article_id: str,
    user: AuthUser = Depends(get_current_user),
):
    """Reject article and permanently prevent future recommendation."""
    approval_mgr = get_multi_tenant_approval_manager()
    try:
        rejected = approval_mgr.reject_article(user.business_id, article_id)
        return {
            "article": rejected.model_dump(),
            "message": f"Article '{rejected.title}' rejected. It will not be recommended again.",
        }
    except KeyError as ke:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ke))


# 6. Notifications & Notification Preferences
@router.get("/notifications")
async def list_notifications(
    unread_only: bool = False,
    user: AuthUser = Depends(get_current_user),
):
    """Retrieve in-app notifications and unread count."""
    repo = get_persistence_repository()
    notifs = repo.list_notifications(user.business_id, unread_only=unread_only)
    unread_count = len([n for n in notifs if not n.read])
    return {
        "notifications": [n.model_dump() for n in notifs],
        "unread_count": unread_count,
    }


@router.put("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    user: AuthUser = Depends(get_current_user),
):
    """Mark an in-app notification as read."""
    repo = get_persistence_repository()
    success = repo.mark_notification_read(user.business_id, notification_id)
    return {"success": success}


@router.get("/notifications/preferences")
async def get_notification_preferences(user: AuthUser = Depends(get_current_user)):
    """Retrieve notification settings."""
    repo = get_persistence_repository()
    prefs = repo.get_notification_preferences(user.business_id)
    return prefs.model_dump()


@router.put("/notifications/preferences")
async def update_notification_preferences(
    req: NotificationPreferencesRequest,
    user: AuthUser = Depends(get_current_user),
):
    """Update email digest frequency (weekly, daily, off)."""
    repo = get_persistence_repository()
    prefs = repo.get_notification_preferences(user.business_id)
    prefs.email_digest_frequency = req.email_digest_frequency
    prefs.in_app_enabled = req.in_app_enabled
    repo.update_notification_preferences(user.business_id, prefs)
    return prefs.model_dump()
