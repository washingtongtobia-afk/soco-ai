"""Workflow node implementations for SoCo Agent in ADK 2.0.

Nodes are modular functions emitting user-facing Event(content=...) and
internal Event(output=..., state=...) objects into the workflow graph.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import AsyncGenerator
from typing import Any

from google.adk.events import Event
from google.genai import types

from app.config.industries import get_industry_profile, list_supported_industries
from app.config.model_config import SOCO_PRIMARY_MODEL
from app.models.caption import CaptionDraft, CaptionStatus
from app.models.industry import IndustryType
from app.models.profile import BusinessProfile, OnboardingInput
from app.news.news_service import get_news_discovery_service
from app.planning.approval_service import get_approval_manager
from app.planning.calendar_service import format_conversational_opening, get_current_month_info
from app.planning.caption_generator import get_caption_generator
from app.planning.multi_tenant_approval import get_multi_tenant_approval_manager
from app.storage.firestore_store import get_persistence_repository
from app.storage.profile_store import get_default_store


def _text_event(text: str) -> Event:
    """Helper to emit formatted text content event for Web UI and streaming."""
    return Event(content=types.Content(role="model", parts=[types.Part.from_text(text=text)]))


async def soco_entrypoint_node(node_input: Any, ctx: Any = None) -> AsyncGenerator[Event, None]:
    """Primary entrypoint and intelligent router node for SoCo workflow graph.

    Handles:
    - Multi-tenant business profile lookup and isolation (via node_input or ADK Context)
    - Onboarding detection (new vs returning user)
    - News discovery requests
    - Human article approval / rejection commands
    - Conversational caption revisions (v1 -> v2)
    - Single-caption generation with missing detail clarification
    - Explicit monthly content strategy calendars
    - Conversational greetings and inquiries
    """
    repo = get_persistence_repository()
    profile_store = get_default_store()
    multi_tenant_approval = get_multi_tenant_approval_manager()
    legacy_approval_mgr = get_approval_manager()
    discovery_svc = get_news_discovery_service()
    caption_gen = get_caption_generator()

    # Extract user text from string, dict, or types.Content
    user_text = ""
    if isinstance(node_input, str):
        user_text = node_input.strip()
    elif isinstance(node_input, dict):
        if "parts" in node_input and isinstance(node_input["parts"], list):
            parts_text = []
            for p in node_input["parts"]:
                if isinstance(p, dict) and p.get("text"):
                    parts_text.append(p["text"])
                elif hasattr(p, "text") and p.text:
                    parts_text.append(p.text)
                elif isinstance(p, str):
                    parts_text.append(p)
            user_text = " ".join(parts_text).strip()
        else:
            user_text = str(node_input.get("text", node_input.get("message", ""))).strip()
    elif hasattr(node_input, "parts") and node_input.parts:
        parts_text = [p.text for p in node_input.parts if getattr(p, "text", None)]
        user_text = " ".join(parts_text).strip()
    elif hasattr(node_input, "role"):
        user_text = str(node_input)

    # Resolve tenant identity (strictly reject missing tenant ID in production)
    biz_id = None
    if isinstance(node_input, dict):
        biz_id = node_input.get("business_id")
    elif hasattr(node_input, "business_id"):
        biz_id = getattr(node_input, "business_id")

    if not biz_id and ctx:
        if hasattr(ctx, "user_id") and ctx.user_id:
            biz_id = ctx.user_id
        elif hasattr(ctx, "session") and getattr(ctx.session, "user_id", None):
            biz_id = ctx.session.user_id

    if not biz_id and user_text and user_text.startswith("{") and "business_id" in user_text:
        try:
            parsed_json = json.loads(user_text)
            if isinstance(parsed_json, dict) and "business_id" in parsed_json:
                biz_id = parsed_json["business_id"]
                if "text" in parsed_json:
                    user_text = parsed_json["text"]
                elif "message" in parsed_json:
                    user_text = parsed_json["message"]
        except Exception:
            pass

    if not biz_id:
        if os.environ.get("ENVIRONMENT", "").lower() == "production":
            yield _text_event("⚠️ **Authentication Error**: Missing required verified business_id. All requests must be tenant-scoped.")
            yield Event(output={"action": "error", "error": "Missing required business_id in production mode."})
            return
        biz_id = "default"

    # Resolve date parameters
    req_year = None
    req_month = None
    req_month_name = None
    if isinstance(node_input, dict):
        req_year = node_input.get("year")
        req_month = node_input.get("month")
        req_month_name = node_input.get("month_name")

    curr_year, curr_month, curr_month_name = get_current_month_info()
    year = req_year if req_year is not None else curr_year
    month = req_month if req_month is not None else curr_month
    month_name = req_month_name if req_month_name is not None else curr_month_name

    # Multi-tenant profile retrieval
    profile = repo.get_profile(biz_id)
    if profile is None:
        profile = profile_store.get_profile(biz_id)
        if profile is not None:
            repo.save_profile(profile)

    # 1. NEW USER ONBOARDING
    if profile is None:
        # Check if user provided onboarding data in JSON or structured text
        if "industry" in user_text.lower() and "business_name" in user_text.lower():
            try:
                data_dict = json.loads(user_text)
                onboard_input = OnboardingInput(**data_dict)
                profile = BusinessProfile.create_from_onboarding(onboard_input, business_id=biz_id)
                profile_store.save_profile(profile)
                repo.save_profile(profile)
                if biz_id != "default" and not profile_store.exists("default"):
                    default_alias = profile.model_copy(update={"business_id": "default"})
                    profile_store.save_profile(default_alias)
                    repo.save_profile(default_alias)

                ind_profile = get_industry_profile(profile.industry)
                msg = (
                    f"🎉 **Welcome to SoCo, {profile.business_name}!**\n\n"
                    f"Your business profile has been saved. Based on your industry (**{ind_profile.display_name}**), "
                    f"I have automatically applied your brand voice profile:\n"
                    f"- **Tone**: {profile.tone}\n"
                    f"- **Voice**: {profile.voice}\n\n"
                    f"You never need to repeat onboarding. "
                    f"{format_conversational_opening()}"
                )
                yield _text_event(msg)
                yield Event(output={"action": "onboarded", "business_id": profile.business_id})
                return
            except Exception:
                pass

        # Otherwise prompt for onboarding
        industries_list = "\n".join([f"- **{ind.display_name}**" for ind in list_supported_industries()])
        prompt = (
            "👋 **Welcome to SoCo — your dedicated industry social media assistant!**\n\n"
            "To get started, please tell me a little about your business:\n"
            "1. **Business Name**\n"
            "2. **Industry** (Choose one):\n"
            f"{industries_list}\n"
            "3. **Business Description** (Your focus, mission, or specialties)\n"
            "4. **Location** (City, State, or Region)\n"
            "5. **Preferred Social Platforms** (e.g., LinkedIn, Instagram, Facebook, X)\n\n"
            "Once entered, I will automatically configure your industry-specific tone and voice!"
        )
        yield _text_event(prompt)
        yield Event(output={"action": "awaiting_onboarding"})
        return

    lower_input = user_text.lower()

    # 2. RETURNING USER: HANDLE NEWS DISCOVERY COMMAND
    if any(k in lower_input for k in ["find news", "discover news", "latest news", "industry news", "news articles"]):
        try:
            articles = discovery_svc.discover_news(profile)
        except Exception as exc:
            yield _text_event(
                "⚠️ **Live News Search Notice**: Unable to retrieve verified live news at this moment. "
                "To maintain strict factual integrity, synthetic mock data is not presented as real news. "
                "Please verify network connectivity or try specifying a narrower search topic."
            )
            yield Event(output={"action": "news_discovery_failed", "error": str(exc)})
            return

        if not articles:
            yield _text_event(
                f"No recent news articles were found matching your criteria for {profile.business_name}."
            )
            yield Event(output={"action": "news_discovered", "count": 0})
            return

        multi_tenant_approval.register_articles(biz_id, articles)
        legacy_approval_mgr.register_articles(articles)

        has_synthetic = any(art.is_synthetic for art in articles)
        if has_synthetic:
            header = f"🧪 **[DEMO / TEST DATA ONLY — NOT FACTUAL NEWS]** Discovered for {profile.business_name} ({profile.industry.value}):\n"
        else:
            header = f"📰 **Timely Industry News Discovered for {profile.business_name}** ({profile.industry.value}):\n"

        msg_lines = [
            header,
            "Please review each article below and reply with **'approve [article_id]'** or **'reject [article_id]'**:\n",
        ]
        for art in articles:
            demo_tag = " *[SIMULATED DEMO DATA]*" if art.is_synthetic else ""
            msg_lines.append(
                f"• **[{art.id}]** **{art.title}** ({art.source} — {art.publication_date}){demo_tag}\n"
                f"  *Summary*: {art.summary}\n"
                f"  *Relevance*: {art.relevance}\n"
                f"  *URL*: {art.url}\n"
            )
        msg_lines.append("\n*Only approved articles will be used to generate draft captions.*")
        yield _text_event("\n".join(msg_lines))
        yield Event(output={"action": "news_discovered", "count": len(articles)})
        return

    # 3. RETURNING USER: HANDLE ARTICLE APPROVAL / REJECTION
    if "approve" in lower_input or "reject" in lower_input:
        tokens = user_text.replace(":", " ").replace(",", " ").split()
        handled = False
        for i, token in enumerate(tokens):
            cmd = token.lower()
            if cmd in ("approve", "reject") and i + 1 < len(tokens):
                target_id = tokens[i + 1].strip()
                try:
                    if cmd == "approve":
                        article = None
                        try:
                            article, _ = multi_tenant_approval.approve_article(biz_id, target_id)
                        except Exception:
                            pass
                        if not article:
                            try:
                                article = legacy_approval_mgr.approve_article(target_id)
                            except Exception:
                                pass

                        if article:
                            # Generate caption for approved article
                            plan = caption_gen.generate_monthly_plan(
                                profile=profile,
                                year=year,
                                month=month,
                                month_name=month_name,
                                approved_articles=[article],
                            )
                            news_cap = [c for c in plan.captions_by_week.get(3, []) if c.concept_title == article.title]
                            if news_cap:
                                news_cap[0].business_id = biz_id
                                repo.save_caption(biz_id, news_cap[0])
                                multi_tenant_approval.register_captions(biz_id, [news_cap[0]])

                            cap_text = news_cap[0].caption_text if news_cap else "Caption drafted."

                            msg = (
                                f"✅ **Article Approved:** {article.title}\n\n"
                                f"📝 **Generated Draft Caption ({profile.tone} Tone):**\n\n"
                                f"> {cap_text}\n\n"
                                f"📅 *Suggested Date*: {news_cap[0].suggested_date if news_cap else 'Mid-month'} | "
                                f"🏷️ *Platform*: {news_cap[0].platform if news_cap else 'LinkedIn'}\n"
                                f"🔖 *Hashtags*: {' '.join(news_cap[0].hashtags if news_cap else [])}\n\n"
                                f"*Note: All captions remain drafts until you explicitly review them.*"
                            )
                            yield _text_event(msg)
                            yield Event(output={
                                "action": "article_approved",
                                "article_id": target_id,
                                "card_type": "captions",
                                "card_data": {"captions": [news_cap[0].model_dump()]} if news_cap else None,
                                "total_captions": 1 if news_cap else 0,
                            })
                            handled = True
                    else:
                        article = None
                        try:
                            article = multi_tenant_approval.reject_article(biz_id, target_id)
                        except Exception:
                            pass
                        if not article:
                            try:
                                article = legacy_approval_mgr.reject_article(target_id)
                            except Exception:
                                pass

                        if article:
                            yield _text_event(f"❌ **Article Rejected:** {article.title}. It will not be used for captions.")
                            yield Event(output={"action": "article_rejected", "article_id": target_id})
                            handled = True
                except KeyError:
                    pass

        if handled:
            return

    # 4. GREETINGS & INTRODUCTORY INQUIRIES
    words = set(re.findall(r"\b[a-zA-Z0-9']+\b", lower_input))
    is_greeting_or_empty = not user_text or (
        len(words) <= 4 and bool(words.intersection({"hi", "hello", "hey", "help"}))
    ) or lower_input in ["who are you", "who are you?", "what can you do", "what can you do?"]
    if is_greeting_or_empty:
        opening = format_conversational_opening(month_name)
        welcome_back = (
            f"👋 Hello again, **{profile.business_name}**!\n\n"
            f"**{opening}**\n\n"
            f"Tell me about upcoming promotions, community events, milestones, or announcements you have planned, "
            f"or ask me to **'discover industry news'** to find timely news topics."
        )
        yield _text_event(welcome_back)
        yield Event(output={
            "action": "greeted_returning_user",
            "month": month_name,
            "year": year,
            "card_type": None,
            "card_data": None,
            "total_captions": 0,
        })
        return

    # 5. CONVERSATIONAL REVISION CHECK (v1 -> v2)
    existing_captions = multi_tenant_approval.list_captions(biz_id)
    if not existing_captions:
        existing_captions = repo.list_captions(biz_id)

    revision_triggers = [
        "make it shorter", "shorter", "shorten it", "make it longer", "longer",
        "more exciting", "more casual", "more professional", "punchier",
        "make it punchier", "revise it", "revise the caption", "update the caption",
        "change the date", "change date to", "add hashtag", "less text", "cut down",
        "more energetic", "rephrase", "tone down", "rewrite it", "can you shorten",
        "can you make it", "make it more",
    ]
    is_revision = any(t in lower_input for t in revision_triggers) and len(existing_captions) > 0

    if is_revision:
        target_caption = existing_captions[-1]
        revised = caption_gen.revise_caption(
            profile=profile,
            caption=target_caption,
            instruction=user_text,
        )
        repo.save_caption(biz_id, revised)
        multi_tenant_approval.register_captions(biz_id, [revised])

        resp_content = (
            f"✍️ **Updated Caption (v{revised.current_version}) for {revised.platform}**\n\n"
            f"I've revised your caption based on your feedback: *\"{user_text}\"*.\n\n"
            f"• **Previous Draft**: Safely archived in Version History (v{revised.current_version - 1}).\n"
            f"• **Tone**: Refined for {profile.business_name} in {profile.business_location}.\n\n"
            f"You can request further tweaks (e.g., *'Add #CommunityPride'* or *'Make it more professional'*) or copy it ready to post!"
        )
        yield _text_event(resp_content)
        yield Event(output={
            "action": "caption_revised",
            "card_type": "captions",
            "card_data": {"captions": [revised.model_dump()]},
            "total_captions": 1,
        })
        return

    # 6. EXPLICIT MONTHLY STRATEGY CHECK
    monthly_plan_triggers = [
        "monthly plan", "full month", "full monthly", "monthly strategy",
        "month plan", "all 4 weeks", "entire month", "content calendar",
        "plan the month", "monthly content plan", "generate a full month",
        "strategy for the month",
    ]
    activities = [a.strip() for a in user_text.replace("\n", ";").split(";") if a.strip()]
    is_monthly_plan = any(t in lower_input for t in monthly_plan_triggers) or (
        len(activities) >= 3 and not any(k in lower_input for k in ["caption", "post", "instagram", "linkedin", "facebook", "twitter"])
    )

    if is_monthly_plan:
        approved_articles = multi_tenant_approval.get_approved_articles(biz_id)
        if not approved_articles:
            approved_articles = legacy_approval_mgr.get_approved_articles()

        plan = caption_gen.generate_monthly_plan(
            profile=profile,
            year=year,
            month=month,
            month_name=month_name,
            user_activities=activities,
            approved_articles=approved_articles,
        )
        all_caps = [c for week in plan.captions_by_week.values() for c in week]
        for c in all_caps:
            c.business_id = biz_id
        multi_tenant_approval.register_captions(biz_id, all_caps)
        legacy_approval_mgr.register_captions(all_caps)
        for c in all_caps:
            repo.save_caption(biz_id, c)

        msg_lines = [
            f"📅 **Draft Social Media Strategy for {profile.business_name} ({month_name} {year})**\n",
            f"*{plan.summary}*\n",
            f"I drafted {plan.total_captions} personalized post concepts across the month. "
            f"All captions remain drafts requiring human review before publishing. "
            f"You can edit individual posts, view version histories, or ask me to revise specific ones!\n",
        ]
        for week_num, caps in sorted(plan.captions_by_week.items()):
            msg_lines.append(f"\n### 📆 Week {week_num}")
            for cap in caps:
                msg_lines.append(
                    f"\n**[{cap.suggested_date}] {cap.platform} — {cap.concept_title}** *(Status: {cap.status.value.upper()})*\n"
                    f"> \"{cap.caption_text}\"\n"
                    f"*Hashtags*: {' '.join(cap.hashtags)}\n"
                    f"*Notes*: {cap.notes_for_user or ''}"
                )
        msg_lines.append("\n\n🔒 *All captions are saved as drafts. You can review, approve, or edit any caption.*")

        yield _text_event("\n".join(msg_lines))
        yield Event(output={
            "action": "plan_generated",
            "card_type": "captions",
            "card_data": {"plan": plan.model_dump()},
            "total_captions": plan.total_captions,
        })
        return

    # 7. SINGLE CAPTION / SOCIAL POST REQUEST
    caption_triggers = [
        "caption", "post", "instagram", "linkedin", "facebook", "twitter", "tweet",
        "x post", "draft", "write a", "create a", "event", "community", "spotlight",
        "announcement", "promote", "share", "picnic", "holiday", "fundraiser",
    ]
    is_caption_request = any(t in lower_input for t in caption_triggers)

    if is_caption_request or len(user_text) > 12:
        res = caption_gen.generate_single_caption(
            profile=profile,
            topic=user_text,
            year=year,
            month=month,
            month_name=month_name,
        )
        res.caption.business_id = biz_id
        multi_tenant_approval.register_captions(biz_id, [res.caption])
        legacy_approval_mgr.register_captions([res.caption])
        repo.save_caption(biz_id, res.caption)

        mode_badge = (
            f"*(⚡ Generated by {SOCO_PRIMARY_MODEL})*"
            if not res.is_simulated
            else "*(🧪 Simulated Draft Prototype — Local Demo Mode)*"
        )

        resp_lines = [
            f"✨ **Draft {res.detected_platform} Caption: {res.cleaned_topic}** {mode_badge}\n",
            f"I crafted a focused draft tailored for **{profile.business_name}** in {profile.business_location} with authentic narrative, call-to-action, and relevant hashtags.\n",
        ]

        if res.clarifying_questions:
            resp_lines.append("To make sure this caption is 100% grounded and ready to publish, could you confirm a few details?")
            for i, q in enumerate(res.clarifying_questions, 1):
                resp_lines.append(f"{i}. {q}")
            resp_lines.append("\n*I've included bracketed placeholders (like `[📅 Date & Time]` and `[📍 Location]`) in the draft below so it's ready to customize.*")
        else:
            resp_lines.append("Take a look at the caption draft below.")

        resp_lines.append("\nYou can reply anytime to adjust it (e.g., *'Make it shorter'*, *'Make it more exciting'*), provide missing details, or ask for another platform!")
        resp_content = "\n".join(resp_lines)

        yield _text_event(resp_content)
        yield Event(output={
            "action": "caption_drafted",
            "card_type": "captions",
            "card_data": {"captions": [res.caption.model_dump()]},
            "total_captions": 1,
        })
        return

    # 8. GENERAL / FALLBACK
    resp_content = (
        f"Hello! I'm SoCo, your conversational social media strategist for **{profile.business_name}**.\n\n"
        f"Here are a few ways we can work together today:\n"
        f"• **Single Post**: Tell me about an upcoming event or announcement (e.g., *\"Create an Instagram caption for our community picnic\"*).\n"
        f"• **Monthly Strategy**: Ask me to *\"Generate our monthly content plan\"* for {month_name}.\n"
        f"• **Industry News**: We can review and curate approved news into engaging posts.\n\n"
        f"What would you like to create?"
    )
    yield _text_event(resp_content)
    yield Event(output={
        "action": "general_response",
        "card_type": None,
        "card_data": None,
        "total_captions": 0,
    })
    return
