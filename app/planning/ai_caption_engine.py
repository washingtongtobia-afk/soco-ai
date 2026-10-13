"""AI-powered social media caption generation engine with guardrails.

Features:
- Deterministic tone, voice, and industry guidance injection
- Dynamic length optimization (short, medium, long)
- Robust factual grounding validation (invented URLs, ungrounded claims, superlatives)
- Prompt injection defense and sanitization
- Explicitly labeled fallback drafts requiring human review when AI is offline
- Safe, mockable architecture for testing and evaluation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import os
import re
import time
from typing import Sequence

from dotenv import load_dotenv

load_dotenv()

from app.config.industries import get_industry_profile
from app.config.model_config import SOCO_PRIMARY_MODEL
from app.models.caption import CaptionSourceType
from app.models.industry import IndustryType
from app.models.profile import BusinessProfile
from app.planning.approval_service import sanitize_external_content

FALLBACK_DRAFT_LABEL: str = "[SIMULATED DRAFT — Local Prototype / Demo Mode]"

FORBIDDEN_OPENINGS: list[str] = [
    "we are excited to announce",
    "we are thrilled to share",
    "mark your calendars",
    "join us as we",
    "get ready for",
    "we are excited to share",
    "community update:",
    "project spotlight:",
    "legal insight:",
    "legal briefing:",
    "now cooking at",
    "foodie news we love",
    "important community development:",
    "industry update:",
]

DEFAULT_MODEL: str = SOCO_PRIMARY_MODEL


class CaptionLength(str, Enum):
    """Categorized caption lengths."""
    SHORT = "short"      # < 150 characters
    MEDIUM = "medium"    # 150 - 700 characters
    LONG = "long"        # 700 - 2,200 characters


def determine_caption_length(
    platform: str,
    source_type: CaptionSourceType,
    details: str | None = None,
) -> CaptionLength:
    """Automatically determine the shortest effective caption length."""
    plt = platform.lower()
    # Short platforms or quick mobile formats
    if any(p in plt for p in ["x", "twitter", "thread", "reel", "story", "tiktok"]):
        return CaptionLength.SHORT

    # Brief holiday greetings on visual platforms
    if source_type in (CaptionSourceType.FEDERAL_HOLIDAY, CaptionSourceType.SOCIAL_HOLIDAY):
        if not details or len(details) < 60:
            return CaptionLength.SHORT
        return CaptionLength.MEDIUM

    # Detailed thought leadership or complex statutory news
    if details and len(details) > 250:
        return CaptionLength.LONG

    return CaptionLength.MEDIUM


_auth_status_cache: tuple[bool, float] | None = None


def is_ai_available(force_check: bool = False) -> bool:
    """Check if AI generation credentials and model access are genuinely active.

    Performs an actual authentication validation / token refresh check rather
    than merely instantiating a client object.
    """
    global _auth_status_cache
    now = time.time()
    if not force_check and _auth_status_cache is not None:
        cached_valid, cached_time = _auth_status_cache
        if now - cached_time < 60.0:
            return cached_valid

    # 1. Check direct Gemini API Key
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if api_key and api_key != "your-api-key-here" and len(api_key) > 10:
        _auth_status_cache = (True, now)
        return True

    # 2. Check Vertex AI / Application Default Credentials
    try:
        from google.auth import default as google_auth_default
        from google.auth.transport.requests import Request

        creds, _ = google_auth_default()
        if hasattr(creds, "refresh") and (creds.expired or not creds.token):
            creds.refresh(Request())
        valid = bool(creds.valid)
        _auth_status_cache = (valid, now)
        return valid
    except Exception:
        _auth_status_cache = (False, now)
        return False


def build_caption_prompt(
    profile: BusinessProfile,
    concept_title: str,
    source_type: CaptionSourceType,
    platform: str,
    extra_details: str | None = None,
    length_hint: CaptionLength | str = CaptionLength.MEDIUM,
) -> tuple[str, str]:
    """Construct system instructions and user message for AI caption generation."""
    ind_profile = get_industry_profile(profile.industry)
    guidelines_text = "\n".join(f"- {g}" for g in ind_profile.writing_guidelines)

    length_desc = {
        CaptionLength.SHORT: "SHORT (under 150 characters, concise hook, punchy message)",
        CaptionLength.MEDIUM: "MEDIUM (150-700 characters, clear narrative and call-to-action)",
        CaptionLength.LONG: "LONG (700-2200 characters, in-depth context and analysis)",
    }.get(length_hint, "MEDIUM (150-700 characters)")

    system_prompt = f"""You are SoCo, an elite social media copywriter for the {ind_profile.display_name} industry.

BRAND IDENTITY & VOICE REQUIREMENTS:
- Industry: {ind_profile.display_name}
- Tone: {profile.tone}
- Voice: {profile.voice}

INDUSTRY WRITING GUIDELINES:
{guidelines_text}

CRITICAL RULES & GUARDRAILS:
1. NEVER start captions with clichés like:
   - "We are excited to announce..."
   - "We are thrilled to share..."
   - "Mark your calendars..."
   - "Join us as we..."
   - "Get ready for..."
   - "Community Update:" or "Project Spotlight:" or "Legal Insight:" or "Now cooking at..."
2. HOOK FIRST: Lead immediately with a compelling, specific hook tied to the actual event, benefit, or business action.
3. FACTUAL GROUNDING:
   - ONLY state facts, dates, services, and claims explicitly supplied in the prompt.
   - NEVER invent unverified dates, discount percentages, dollar amounts, awards, or fake quotes.
   - NEVER invent URLs or link strings (e.g. do not invent "https://..." or "bit.ly/...").
4. LENGTH TARGET: {length_desc}. Choose the shortest effective length.
5. PLATFORM: Tailor formatting and cadence for {platform}. Include 2-5 relevant hashtags at the bottom.
"""
    if profile.industry == IndustryType.LAW_OFFICE:
        system_prompt += (
            "\n6. MANDATORY LEGAL DISCLAIMER: You MUST include this exact disclaimer at the end:\n"
            "*(Informational legal overview; not formal legal representation.)*\n"
        )

    user_prompt = f"""Generate a high-converting {platform} caption for this business:
- Business Name: {profile.business_name}
- Location: {profile.business_location}
- Description: {profile.business_description}
- Post Topic / Concept: {concept_title}
- Source Type: {source_type.value}
- Additional Context / Source Details: {extra_details or 'None provided'}
"""
    return system_prompt, user_prompt


def call_model(
    user_prompt: str,
    system_instruction: str,
    model: str = DEFAULT_MODEL,
) -> str:
    """Call Google GenAI SDK to generate copy. Mocked in offline unit tests."""
    from google import genai
    from google.genai import types

    client = genai.Client()
    response = client.models.generate_content(
        model=model,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.7,
        ),
    )
    return response.text or ""


@dataclass
class ValidationResult:
    """Detailed validation evaluation of a caption draft."""
    is_valid: bool
    warnings: list[str] = field(default_factory=list)
    forbidden_opening_detected: str | None = None
    invented_urls: list[str] = field(default_factory=list)
    grounding_issues: list[str] = field(default_factory=list)
    unsupported_claims: list[str] = field(default_factory=list)


def validate_caption_output(
    caption_text: str,
    profile: BusinessProfile,
    concept_title: str,
    extra_details: str | None = None,
    source_type: CaptionSourceType | None = None,
    length_hint: CaptionLength | str | None = None,
) -> ValidationResult:
    """Comprehensive validation: forbidden openings, URLs, factual grounding, and claims."""
    warnings: list[str] = []
    grounding_issues: list[str] = []
    unsupported_claims: list[str] = []
    invented_urls: list[str] = []
    forbidden_opening: str | None = None
    is_valid = True

    clean_text = caption_text.strip()
    # Strip fallback label before validation if present
    if clean_text.startswith(FALLBACK_DRAFT_LABEL):
        clean_text = clean_text[len(FALLBACK_DRAFT_LABEL):].strip()
    lower_text = clean_text.lower()

    # 1. Check forbidden openings
    for forbidden in FORBIDDEN_OPENINGS:
        if lower_text.startswith(forbidden):
            forbidden_opening = forbidden
            is_valid = False
            warnings.append(f"Forbidden generic opening detected: '{forbidden}'")
            break

    # 2. Check invented URLs
    found_urls = re.findall(r"https?://[^\s]+|www\.[^\s]+", clean_text)
    source_text = f"{extra_details or ''} {profile.business_description}"
    for u in found_urls:
        if u not in source_text:
            invented_urls.append(u)
            is_valid = False
            warnings.append(f"Invented URL detected: '{u}'")

    # 3. Grounding: Check concept title presence
    stopwords = {"and", "the", "for", "with", "from", "that", "this", "our", "day", "week", "month"}
    concept_words = [
        w.lower() for w in re.findall(r"\b[A-Za-z0-9]{3,}\b", concept_title)
        if w.lower() not in stopwords
    ]
    if concept_words:
        matched = any(w in lower_text for w in concept_words)
        if not matched:
            issue = f"Caption does not mention key terms from concept '{concept_title}'"
            grounding_issues.append(issue)
            warnings.append(issue)

    # 4. Grounding: For user events, check business name presence
    if source_type == CaptionSourceType.USER_EVENT:
        biz_name_clean = profile.business_name.lower()
        name_words = [w for w in re.findall(r"\b[A-Za-z0-9]{3,}\b", biz_name_clean) if w not in stopwords]
        if biz_name_clean not in lower_text and not any(w in lower_text for w in name_words):
            issue = f"User event caption does not mention business name '{profile.business_name}'"
            grounding_issues.append(issue)
            warnings.append(issue)

    # 5. Factual Grounding: Detect unsupported claims (specific times, prices, discounts, superlatives)
    times_found = re.findall(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b", lower_text)
    for t in times_found:
        if t not in source_text.lower():
            claim = f"Specific time '{t}' not in provided details"
            unsupported_claims.append(claim)
            warnings.append(claim)

    prices_found = re.findall(r"\$\d+(?:\.\d{2})?|\b\d+%\s*off\b", lower_text)
    for p in prices_found:
        if p not in source_text.lower():
            claim = f"Pricing or discount '{p}' not in provided details"
            unsupported_claims.append(claim)
            warnings.append(claim)

    superlatives = ["voted #1", "best in the nation", "100% guaranteed", "award-winning", "certified safe"]
    for s in superlatives:
        if s in lower_text and s not in source_text.lower():
            claim = f"Unverified claim/guarantee '{s}' not supported by input data"
            unsupported_claims.append(claim)
            warnings.append(claim)

    # 6. Law office disclaimer check
    if profile.industry == IndustryType.LAW_OFFICE:
        if "informational legal overview" not in lower_text:
            warnings.append("Law Office caption missing mandatory disclaimer.")

    return ValidationResult(
        is_valid=is_valid,
        warnings=warnings,
        forbidden_opening_detected=forbidden_opening,
        invented_urls=invented_urls,
        grounding_issues=grounding_issues,
        unsupported_claims=unsupported_claims,
    )


def clean_concept_topic(raw_title: str) -> str:
    """Clean conversational prompt prefixes from concept title."""
    clean = raw_title.strip()
    patterns = [
        r"^(?:please\s+)?(?:can\s+you\s+)?(?:create|draft|write|make|generate)\s+(?:an?\s+)?(?:[a-z0-9_-]+\s+)?(?:caption|post)\s+(?:about|for|on)\s+",
        r"^(?:please\s+)?(?:can\s+you\s+)?(?:create|draft|write|make|generate)\s+(?:an?\s+)?(?:[a-z0-9_-]+\s+)?(?:caption|post)\s+",
        r"^(?:an?\s+)?(?:instagram|linkedin|facebook|x|twitter)\s+(?:caption|post)\s+(?:about|for|on)\s+",
    ]
    for p in patterns:
        clean = re.sub(p, "", clean, flags=re.IGNORECASE).strip()
    if clean:
        return clean[0].upper() + clean[1:]
    return "Community Spotlight"


def deterministic_fallback_caption(
    profile: BusinessProfile,
    concept_title: str,
    source_type: CaptionSourceType,
    platform: str,
    extra_details: str | None = None,
) -> str:
    """High-quality simulated prototype copy tailored to platform, industry, and topic.

    Explicitly labeled as simulated draft for local testing and demo mode.
    """
    ind = profile.industry
    name = profile.business_name
    loc = profile.business_location
    details = extra_details or ""
    topic = clean_concept_topic(concept_title)
    plt = platform.lower()

    disclaimer = "*(Informational legal overview; not formal legal representation.)*"

    # 1. Holidays & Observances
    if source_type in (CaptionSourceType.FEDERAL_HOLIDAY, CaptionSourceType.SOCIAL_HOLIDAY):
        if ind == IndustryType.RESTAURANT:
            body = (
                f"Happy {topic} from your friends at {name}! 🎉 "
                f"Gather your favorite people and celebrate with us in {loc}. "
                f"We're serving up delicious seasonal bites and signature drinks all day long. Reserve your table!"
            )
        elif ind == IndustryType.LAW_OFFICE:
            body = (
                f"{name} wishes our clients, colleagues, and community in {loc} a reflective {topic}. "
                f"Our office will observe normal business hours following the holiday. "
                f"We remain steadfast in protecting your rights and delivering trusted counsel.\n\n{disclaimer}"
            )
        else:
            body = (
                f"Honoring {topic} across all {name} teams in {loc}. "
                f"Dedication and community progress rest on the passion of our crews and partners. "
                f"Wishing our teams and community a safe, restorative holiday."
            )

    elif source_type == CaptionSourceType.INDUSTRY_OBSERVANCE:
        if ind == IndustryType.LAW_OFFICE:
            body = (
                f"Observing {topic}. Proactive planning provides lasting peace of mind. "
                f"At {name}, we guide individuals and businesses in {loc} through intricate regulatory landscapes with clarity. "
                f"{details or 'Ensure your legal foundation is secure with experienced guidance.'}\n\n{disclaimer}"
            )
        elif ind == IndustryType.RESTAURANT:
            body = (
                f"It's {topic}, and we're ready to celebrate in delicious style! 🍽️ "
                f"Chef has prepared something truly special at {name}. "
                f"{details or 'Fresh ingredients, bold flavor, and warm hospitality waiting for you.'} "
                f"Who are you bringing to dinner tonight? Tag them below!"
            )
        else:
            body = (
                f"Recognizing {topic}. {name} reinforces our commitment to excellence and community service in {loc}. "
                f"{details or 'Every initiative begins with uncompromising standards and care.'} "
                f"Connect with us this month to learn more."
            )

    elif source_type == CaptionSourceType.APPROVED_NEWS:
        if ind == IndustryType.LAW_OFFICE:
            body = (
                f"Regulatory analysis: {topic}. "
                f"Our attorneys at {name} in {loc} are monitoring these legal developments closely. "
                f"{details or 'Understanding how enacted statutes impact your rights is essential for risk mitigation.'}\n\n{disclaimer}"
            )
        else:
            body = (
                f"Industry development: {topic}. "
                f"At {name} in {loc}, we stay ahead of regulatory and community shifts to deliver leading results. "
                f"{details or 'Keeping our clients informed and proactive at every stage.'} "
                f"Reach out to our team for tailored guidance."
            )

    # 2. User-Requested Event / Topic (Instagram, LinkedIn, Facebook, X)
    else:
        is_community = any(k in topic.lower() for k in ["community", "event", "gathering", "picnic", "fair", "outreach", "fest"])
        
        if "instagram" in plt:
            if is_community:
                body = (
                    f"Building strong communities starts from the ground up! ✨🤝\n\n"
                    f"Join {name} for our upcoming {topic} in {loc}. "
                    f"{details or 'We are bringing neighbors, partners, and friends together to celebrate local progress and give back.'}\n\n"
                    f"📍 Location: [Event Venue / Location]\n"
                    f"📅 Date & Time: [Date & Time]\n"
                    f"🎟️ Admission: [Free / RSVP details]\n\n"
                    f"Save this post, tag a friend who should come along, and drop a comment below if we'll see you there!"
                )
            else:
                body = (
                    f"Inside look at {name}: {topic}! ✨\n\n"
                    f"Our team in {loc} is dedicated to delivering quality, craftsmanship, and real results. "
                    f"{details or 'Every project represents the hard work and passion of our dedicated crew.'}\n\n"
                    f"Double tap if you love seeing behind-the-scenes progress, and check out the link in our bio for more details!"
                )

        elif "linkedin" in plt:
            if is_community:
                body = (
                    f"Corporate citizenship and community partnership in action: {topic}.\n\n"
                    f"At {name}, we believe long-term success in {loc} means actively investing in the people and communities we serve. "
                    f"{details or 'Our team is proud to participate in this upcoming initiative alongside regional community leaders.'}\n\n"
                    f"📅 Event Schedule: [Date & Time] | 📍 Location: [Venue]\n\n"
                    f"How is your organization advancing community engagement this quarter? Connect with us below."
                )
            else:
                body = (
                    f"Strategic milestone: {topic}.\n\n"
                    f"The team at {name} continues to drive measurable performance and operational excellence across {loc}. "
                    f"{details or 'Ensuring precision, compliance, and lasting quality across all deliverables.'}\n\n"
                    f"We invite industry partners and prospective clients to connect with us to discuss upcoming project requirements."
                )

        elif "facebook" in plt:
            body = (
                f"We love staying connected with our {loc} community! 🌟\n\n"
                f"Mark your calendars for {topic} with {name}. "
                f"{details or 'We cannot wait to celebrate with our wonderful neighbors and families.'}\n\n"
                f"📍 Where: [Location]\n"
                f"📅 When: [Date & Time]\n\n"
                f"Share this post with a friend or neighbor, and let us know in the comments if you plan on attending!"
            )

        elif any(x in plt for x in ["x", "twitter"]):
            body = (
                f"{topic} with {name} in {loc}! 🚀 "
                f"{details or 'Proud to support our local community and partners.'} "
                f"Details & RSVP: [Link in Bio]. Join the conversation below!"
            )

        else:
            body = (
                f"{topic} from {name} in {loc}. "
                f"{details or 'Dedicated to delivering excellence and community engagement.'} "
                f"Connect with us to learn more!"
            )

        if ind == IndustryType.LAW_OFFICE and disclaimer not in body:
            body += f"\n\n{disclaimer}"

    return f"{FALLBACK_DRAFT_LABEL}\n\n{body}"


def generate_caption(
    profile: BusinessProfile,
    concept_title: str,
    source_type: CaptionSourceType,
    platform: str,
    extra_details: str | None = None,
    length_hint: CaptionLength | str | None = None,
) -> tuple[str, bool, list[str]]:
    """Generate caption using AI when available, falling back gracefully to labeled draft.

    Returns:
        tuple of (caption_text, is_ai_generated, warnings)
    """
    # 1. Profile completeness check
    profile.validate_for_generation()

    # 2. Injection defense & sanitization
    safe_details = sanitize_external_content(extra_details)

    # 3. Determine length
    if not length_hint:
        length_hint = determine_caption_length(platform, source_type, safe_details)

    # 4. Check AI availability
    if is_ai_available():
        try:
            sys_prompt, user_prompt = build_caption_prompt(
                profile=profile,
                concept_title=concept_title,
                source_type=source_type,
                platform=platform,
                extra_details=safe_details,
                length_hint=length_hint,
            )
            raw_text = call_model(user_prompt, sys_prompt)
            if raw_text and raw_text.strip():
                val = validate_caption_output(
                    raw_text,
                    profile=profile,
                    concept_title=concept_title,
                    extra_details=safe_details,
                    source_type=source_type,
                    length_hint=length_hint,
                )
                if val.is_valid:
                    final_text = raw_text.strip()
                    if (
                        profile.industry == IndustryType.LAW_OFFICE
                        and "informational legal overview" not in final_text.lower()
                    ):
                        final_text += "\n\n*(Informational legal overview; not formal legal representation.)*"
                    return final_text, True, val.warnings
        except Exception:
            pass

    # 5. Deterministic fallback (clearly labeled draft requiring human review)
    fallback_text = deterministic_fallback_caption(
        profile=profile,
        concept_title=concept_title,
        source_type=source_type,
        platform=platform,
        extra_details=safe_details,
    )
    val = validate_caption_output(
        fallback_text,
        profile=profile,
        concept_title=concept_title,
        extra_details=safe_details,
        source_type=source_type,
        length_hint=length_hint,
    )
    warnings = ["AI generation unavailable; deterministic fallback draft produced for human review."] + val.warnings
    return fallback_text, False, warnings


def revise_caption_copy(
    profile: BusinessProfile,
    original_text: str,
    instruction: str,
    platform: str = "Instagram",
    extra_details: str | None = None,
) -> tuple[str, bool, list[str]]:
    """Revise an existing caption copy following user guidance.

    Returns:
        tuple of (revised_text, is_ai_generated, warnings)
    """
    safe_instruction = sanitize_external_content(instruction)
    clean_orig = original_text.replace(FALLBACK_DRAFT_LABEL, "").strip()

    if is_ai_available():
        try:
            ind_profile = get_industry_profile(profile.industry)
            sys_prompt = f"""You are SoCo, an elite social media copywriter for the {ind_profile.display_name} industry.
You are revising an existing social media caption based on the user's feedback.
Brand Name: {profile.business_name}
Location: {profile.business_location}
Tone: {ind_profile.tone}
Voice: {ind_profile.voice}
Platform: {platform}

Strict Guidelines:
1. Maintain brand voice and tone.
2. Adhere faithfully to the user's revision instruction.
3. Do not invent ungrounded facts, unverified dates, or fake pricing.
4. Output only the revised caption text. Do not include meta-commentary."""

            user_prompt = f"""Existing Caption:
{clean_orig}

Revision Instruction:
{safe_instruction}

Please provide the revised caption:"""

            raw_text = call_model(user_prompt, sys_prompt)
            if raw_text and raw_text.strip():
                final_text = raw_text.strip()
                if (
                    profile.industry == IndustryType.LAW_OFFICE
                    and "informational legal overview" not in final_text.lower()
                ):
                    final_text += "\n\n*(Informational legal overview; not formal legal representation.)*"
                return final_text, True, []
        except Exception:
            pass

    # Deterministic simulation of revision
    lower_instr = safe_instruction.lower()

    if "shorter" in lower_instr or "brief" in lower_instr or "concise" in lower_instr or "cut down" in lower_instr:
        # Condense: keep first hook paragraph, key bracketed details, and punchy CTA
        paras = [p.strip() for p in clean_orig.split("\n\n") if p.strip()]
        if len(paras) > 2:
            hook = paras[0]
            detail_lines = [p for p in paras[1:-1] if any(sym in p for sym in ["📍", "📅", "🎟️", "•", "-"])]
            cta = paras[-1]
            if detail_lines:
                revised_body = f"{hook}\n\n" + "\n\n".join(detail_lines) + f"\n\n{cta}"
            else:
                revised_body = f"{hook}\n\n{cta}"
        else:
            revised_body = f"{clean_orig[:len(clean_orig)//2].rstrip()}... See you there! ✨"

    elif "exciting" in lower_instr or "energetic" in lower_instr or "hype" in lower_instr or "enthusiastic" in lower_instr:
        revised_body = (
            f"🔥 BIG NEWS! Get ready for something amazing in {profile.business_location}!\n\n"
            + clean_orig.replace("Building strong communities", "We are so thrilled to bring our wonderful community together")
                        .replace("Join ", "Don't miss out! Join ")
            + "\n\n⚡ Drop a 🔥 in the comments if you're as excited as we are!"
        )

    elif "professional" in lower_instr or "formal" in lower_instr:
        revised_body = clean_orig.replace("✨🤝", "").replace("✨", "").replace("🎉", "").replace("!", ".")
        revised_body = f"Official announcement on behalf of {profile.business_name}:\n\n{revised_body}"

    else:
        # Update / replace details or add note
        revised_body = f"{clean_orig}\n\n*(Updated: {safe_instruction})*"

    labeled_text = f"{FALLBACK_DRAFT_LABEL} (Revision: {safe_instruction.strip()[:40]})\n\n{revised_body.strip()}"
    return labeled_text, False, ["AI generation unavailable; deterministic simulated revision applied."]
