"""Industry-specific caption generation engine.

Combines:
- Saved business profile
- Deterministic industry tone and voice
- User-provided events, promotions, and announcements
- Federal, social media, and industry observances
- Approved industry news articles
- Suggested posting dates, platform formatting, and hashtags
- Organization by week and month
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import re
import uuid
from typing import Sequence

from app.config.industries import get_industry_profile
from app.models.caption import CaptionDraft, CaptionSourceType, CaptionStatus, MonthlyPlan
from app.models.industry import IndustryType
from app.models.news import NewsArticle
from app.models.profile import BusinessProfile
from app.planning.ai_caption_engine import clean_concept_topic, generate_caption, revise_caption_copy
from app.planning.approval_service import assert_approved
from app.planning.calendar_service import (
    ObservanceItem,
    assign_day_to_week,
    get_month_observances,
    get_suggested_dates_for_week,
)


@dataclass
class SingleCaptionResult:
    """Outcome of generating a single targeted caption draft."""
    caption: CaptionDraft
    clarifying_questions: list[str]
    detected_platform: str
    cleaned_topic: str
    is_simulated: bool


def detect_missing_event_details(topic: str, extra_details: str | None = None) -> list[str]:
    """Identify missing operational details (date/time, location, admission) for events."""
    combined = f"{topic} {extra_details or ''}".strip().lower()

    event_keywords = [
        "event", "picnic", "fair", "outreach", "fest", "celebration", "open house",
        "fundraiser", "mixer", "workshop", "webinar", "luncheon", "gathering",
        "gala", "cleanup", "drive", "expo", "conference", "party", "grand opening",
    ]
    is_event_like = any(k in combined for k in event_keywords)

    questions: list[str] = []
    if is_event_like or len(combined.split()) < 10:
        has_date_time = bool(re.search(
            r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
            r"jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|"
            r"\d{1,2}/\d{1,2}|\d{1,2}(?:st|nd|rd|th)?|\d{1,2}\s*(?:am|pm)|"
            r"tomorrow|tonight|next\s+week)\b",
            combined,
            re.IGNORECASE,
        ))
        if not has_date_time:
            questions.append("When is the event scheduled? (Date and start/end time)")

        has_location = bool(re.search(
            r"\b(at\s+[a-z0-9]|in\s+[a-z0-9]|venue|park|hall|center|centre|street|avenue|st\.|ave\.|suite|online|zoom|downtown|campus|headquarters|office|address)\b",
            combined,
            re.IGNORECASE,
        ))
        if not has_location:
            questions.append("Where is the event taking place? (Venue name, address, or virtual link)")

        has_admission = bool(re.search(
            r"\b(free|tickets?|rsvp|admission|register|registration|cost|\$\d+|fee)\b",
            combined,
            re.IGNORECASE,
        ))
        if not has_admission:
            questions.append("What are the admission or RSVP requirements? (Free to the public, tickets required, or registration link)")

    return questions


def _generate_caption_id(concept: str, date_str: str) -> str:
    digest = hashlib.md5(f"{concept}_{date_str}_{uuid.uuid4().hex[:4]}".encode("utf-8")).hexdigest()[:8]
    return f"cap_{digest}"


def _format_hashtags(base_tags: list[str], extra_tag: str | None = None) -> list[str]:
    tags = list(base_tags)
    if extra_tag:
        clean = "#" + extra_tag.replace(" ", "").replace("'", "").replace("-", "")
        if clean not in tags:
            tags.append(clean)
    return tags[:6]


def craft_caption_text(
    profile: BusinessProfile,
    concept_title: str,
    source_type: CaptionSourceType,
    platform: str,
    extra_details: str | None = None,
) -> str:
    """Draft industry-specific copy using AI when available, falling back to labeled drafts."""
    text, _, _ = generate_caption(
        profile=profile,
        concept_title=concept_title,
        source_type=source_type,
        platform=platform,
        extra_details=extra_details,
    )
    return text


class CaptionGenerator:
    """Generates organized weekly and monthly caption drafts."""

    def generate_monthly_plan(
        self,
        profile: BusinessProfile,
        year: int,
        month: int,
        month_name: str,
        user_activities: Sequence[str] = (),
        approved_articles: Sequence[NewsArticle] = (),
    ) -> MonthlyPlan:
        """Create complete monthly plan with captions bucketed by week."""
        profile.validate_for_generation()
        industry_profile = get_industry_profile(profile.industry)
        observances = get_month_observances(year, month, profile.industry)
        platforms = profile.preferred_platforms or ["LinkedIn", "Instagram", "Facebook"]

        captions: list[CaptionDraft] = []
        platform_idx = 0

        def next_platform() -> str:
            nonlocal platform_idx
            p = platforms[platform_idx % len(platforms)]
            platform_idx += 1
            return p

        # 1. Captions from User-Provided Events & Activities
        for i, activity in enumerate(user_activities):
            week_num = (i % 4) + 1
            suggested_dates = get_suggested_dates_for_week(year, month, week_num)
            date_str = suggested_dates[i % len(suggested_dates)]
            plt = next_platform()
            cap_id = _generate_caption_id(activity, date_str)
            text, is_ai, warnings = generate_caption(
                profile=profile,
                concept_title=activity,
                source_type=CaptionSourceType.USER_EVENT,
                platform=plt,
                extra_details=f"Highlighting {activity} for our audience this month.",
            )
            note = (
                "Generated from your planned monthly activity."
                if is_ai
                else "Draft requiring human review (AI generation unavailable). Generated from your planned monthly activity."
            )
            captions.append(CaptionDraft(
                id=cap_id,
                month=month_name,
                year=year,
                week_number=week_num,
                suggested_date=date_str,
                platform=plt,
                caption_text=text,
                hashtags=_format_hashtags(industry_profile.recommended_hashtags, activity),
                concept_title=activity,
                source_type=CaptionSourceType.USER_EVENT,
                status=CaptionStatus.DRAFT,
                tone=industry_profile.tone,
                voice=industry_profile.voice,
                notes_for_user=note,
                is_ai_generated=is_ai,
                grounding_warnings=warnings,
            ))

        # 2. Captions from Federal & Social Holidays & Industry Observances
        for obs in observances:
            week_num = assign_day_to_week(obs.day)
            plt = next_platform()
            cap_id = _generate_caption_id(obs.name, obs.date_str)
            src_type = (
                CaptionSourceType.FEDERAL_HOLIDAY if obs.category == "federal_holiday"
                else CaptionSourceType.INDUSTRY_OBSERVANCE if obs.category == "industry_observance"
                else CaptionSourceType.SOCIAL_HOLIDAY
            )
            text, is_ai, warnings = generate_caption(
                profile=profile,
                concept_title=obs.name,
                source_type=src_type,
                platform=plt,
                extra_details=obs.description,
            )
            cat_display = obs.category.replace('_', ' ')
            note = (
                f"Relevant {cat_display}."
                if is_ai
                else f"Draft requiring human review (AI generation unavailable). Relevant {cat_display}."
            )
            captions.append(CaptionDraft(
                id=cap_id,
                month=month_name,
                year=year,
                week_number=week_num,
                suggested_date=obs.date_str,
                platform=plt,
                caption_text=text,
                hashtags=_format_hashtags(industry_profile.recommended_hashtags, obs.name),
                concept_title=obs.name,
                source_type=src_type,
                status=CaptionStatus.DRAFT,
                tone=industry_profile.tone,
                voice=industry_profile.voice,
                notes_for_user=note,
                is_ai_generated=is_ai,
                grounding_warnings=warnings,
            ))

        # 3. Captions from Approved Industry News Articles (Human approved only!)
        for art in approved_articles:
            assert_approved(art)
            week_num = 3  # Place news in mid-month by default
            suggested_dates = get_suggested_dates_for_week(year, month, week_num)
            date_str = suggested_dates[0]
            plt = next_platform()
            cap_id = _generate_caption_id(art.title, date_str)
            text, is_ai, warnings = generate_caption(
                profile=profile,
                concept_title=art.title,
                source_type=CaptionSourceType.APPROVED_NEWS,
                platform=plt,
                extra_details=f"Source: {art.source}. {art.summary}",
            )
            note = (
                f"Curated from approved news ({art.source})."
                if is_ai
                else f"Draft requiring human review (AI generation unavailable). Curated from approved news ({art.source})."
            )
            captions.append(CaptionDraft(
                id=cap_id,
                month=month_name,
                year=year,
                week_number=week_num,
                suggested_date=date_str,
                platform=plt,
                caption_text=text,
                hashtags=_format_hashtags(industry_profile.recommended_hashtags + [f"#{t}" for t in art.tags]),
                concept_title=art.title,
                source_type=CaptionSourceType.APPROVED_NEWS,
                status=CaptionStatus.DRAFT,
                tone=industry_profile.tone,
                voice=industry_profile.voice,
                notes_for_user=note,
                is_ai_generated=is_ai,
                grounding_warnings=warnings,
            ))

        # Group captions by week (1 to 5)
        by_week: dict[int, list[CaptionDraft]] = {w: [] for w in range(1, 6)}
        for cap in captions:
            by_week[cap.week_number].append(cap)

        # Remove empty trailing week 5 if not populated
        if not by_week[5]:
            del by_week[5]

        return MonthlyPlan(
            business_id=profile.business_id,
            month_name=month_name,
            year=year,
            total_captions=len(captions),
            captions_by_week=by_week,
            summary=(
                f"Generated {len(captions)} draft captions for {month_name} {year} "
                f"adhering to '{industry_profile.tone}' tone and '{industry_profile.voice}' voice."
            ),
        )

    def generate_single_caption(
        self,
        profile: BusinessProfile,
        topic: str,
        platform: str | None = None,
        extra_details: str | None = None,
        length_hint: str | None = None,
        year: int | None = None,
        month: int | None = None,
        month_name: str | None = None,
    ) -> SingleCaptionResult:
        """Create a single, targeted caption draft with missing details detection."""
        profile.validate_for_generation()
        industry_profile = get_industry_profile(profile.industry)

        # 1. Clean topic
        clean_title = clean_concept_topic(topic)

        # 2. Determine platform
        if platform:
            plt = platform
        else:
            lower_topic = topic.lower()
            if "instagram" in lower_topic or "insta" in lower_topic or "ig" in lower_topic:
                plt = "Instagram"
            elif "linkedin" in lower_topic:
                plt = "LinkedIn"
            elif "facebook" in lower_topic or "fb" in lower_topic:
                plt = "Facebook"
            elif any(x in lower_topic for x in ["twitter", " x ", "tweet"]):
                plt = "X"
            elif profile.preferred_platforms:
                plt = profile.preferred_platforms[0]
            else:
                plt = "Instagram"

        # 3. Detect missing event / announcement details
        questions = detect_missing_event_details(topic, extra_details)

        # 4. Generate caption copy
        text, is_ai, warnings = generate_caption(
            profile=profile,
            concept_title=clean_title,
            source_type=CaptionSourceType.USER_EVENT,
            platform=plt,
            extra_details=extra_details,
            length_hint=length_hint,
        )

        # 5. Metadata
        y = year or 2026
        m_name = month_name or "October"
        date_str = f"{m_name} {y}"
        cap_id = _generate_caption_id(clean_title, date_str)

        note = (
            f"Draft for {plt}."
            if is_ai
            else f"Simulated draft prototype for {plt}. Human review required before publishing."
        )

        draft = CaptionDraft(
            id=cap_id,
            business_id=profile.business_id,
            month=m_name,
            year=y,
            week_number=1,
            suggested_date=date_str,
            platform=plt,
            caption_text=text,
            hashtags=_format_hashtags(industry_profile.recommended_hashtags, clean_title),
            concept_title=clean_title,
            source_type=CaptionSourceType.USER_EVENT,
            status=CaptionStatus.DRAFT,
            tone=industry_profile.tone,
            voice=industry_profile.voice,
            notes_for_user=note,
            is_ai_generated=is_ai,
            grounding_warnings=warnings,
            current_version=1,
            version_history=[],
        )

        return SingleCaptionResult(
            caption=draft,
            clarifying_questions=questions,
            detected_platform=plt,
            cleaned_topic=clean_title,
            is_simulated=not is_ai,
        )

    def revise_caption(
        self,
        profile: BusinessProfile,
        caption: CaptionDraft,
        instruction: str,
    ) -> CaptionDraft:
        """Revise an existing caption draft, archiving prior version."""
        revised_text, is_ai, warnings = revise_caption_copy(
            profile=profile,
            original_text=caption.caption_text,
            instruction=instruction,
            platform=caption.platform,
        )

        # Archive prior version and apply new text (save_revision updates caption_text and increments current_version)
        caption.save_revision(
            new_text=revised_text,
            note=f"Revision request: '{instruction}'",
        )

        caption.is_ai_generated = is_ai
        caption.grounding_warnings = warnings
        caption.notes_for_user = (
            f"Version {caption.current_version} updated based on: '{instruction}'."
        )

        return caption


# Singleton generator
_CAPTION_GENERATOR = CaptionGenerator()


def get_caption_generator() -> CaptionGenerator:
    """Return default caption generator."""
    return _CAPTION_GENERATOR
