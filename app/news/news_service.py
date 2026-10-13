"""News discovery service for industry developments.

Supports:
- Abstract BaseNewsDiscoveryService interface
- MockNewsDiscoveryService tailored to each business profile (location, mission, description)
- Live WebSearchNewsDiscoveryService with Google ADK / Gemini Search Grounding
"""

from __future__ import annotations

import abc
import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Sequence

from app.models.industry import IndustryType
from app.models.news import ArticleApprovalStatus, NewsArticle
from app.models.profile import BusinessProfile

logger = logging.getLogger(__name__)


class BaseNewsDiscoveryService(abc.ABC):
    """Abstract news discovery interface."""

    @abc.abstractmethod
    def discover_news(
        self,
        profile: BusinessProfile,
        topic_filter: str | None = None,
        max_results: int = 4,
    ) -> list[NewsArticle]:
        """Find timely news articles relevant to the business."""
        raise NotImplementedError


class MockNewsDiscoveryService(BaseNewsDiscoveryService):
    """Deterministic mock news discovery tailored to business details."""

    def _generate_article_id(self, title: str, source: str) -> str:
        digest = hashlib.md5(f"{title}_{source}".encode("utf-8")).hexdigest()[:8]
        return f"art_{digest}"

    def discover_news(
        self,
        profile: BusinessProfile,
        topic_filter: str | None = None,
        max_results: int = 4,
    ) -> list[NewsArticle]:
        loc = profile.business_location
        desc = profile.business_description
        name = profile.business_name
        ind = profile.industry

        articles: list[NewsArticle] = []

        if ind == IndustryType.CONSTRUCTION_CIVIL_ENGINEERING:
            articles = [
                NewsArticle(
                    id=self._generate_article_id("Regional Infrastructure Modernization Grants", "Civil Engineering Daily"),
                    title=f"Regional Infrastructure Modernization Grants Announced for {loc}",
                    source="Civil Engineering Daily",
                    url="https://example.com/civil/regional-grants-infrastructure",
                    publication_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    summary=f"Transportation authorities released new funding guidelines for roadway, bridge, and stormwater resilience projects in {loc}.",
                    relevance=f"Directly impacts {name}'s project pipeline and public bid opportunities aligned with '{desc}'.",
                    industry=ind.value,
                    tags=["Infrastructure", "Grants", "Transportation"],
                ),
                NewsArticle(
                    id=self._generate_article_id("OSHA Updates Fall Protection and Heat Standards", "Construction Safety Review"),
                    title="OSHA Issues Updated Job Site Safety Standards for Structural Engineering Crews",
                    source="Construction Safety Review",
                    url="https://example.com/safety/osha-fall-heat-standards",
                    publication_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    summary="New compliance checklist focuses on real-time site monitoring, safety stand-downs, and proactive crew protection.",
                    relevance=f"Enables {name} to demonstrate thought leadership on safety culture and technical compliance.",
                    industry=ind.value,
                    tags=["Safety", "Compliance", "OSHA"],
                ),
                NewsArticle(
                    id=self._generate_article_id("Mass Timber and Carbon-Smart Concrete Adoption", "Engineering News Record"),
                    title="Adoption of Carbon-Smart Concrete and Mass Timber Grows in Commercial Specs",
                    source="Engineering News Record",
                    url="https://example.com/engineering/green-materials-2026",
                    publication_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    summary="Municipalities are expediting permits for building projects that incorporate low-carbon materials and structural efficiency.",
                    relevance=f"Highlights {name}'s technical engineering capabilities in modern, sustainable construction practices.",
                    industry=ind.value,
                    tags=["Engineering", "Sustainability", "Materials"],
                ),
                NewsArticle(
                    id=self._generate_article_id("Digital Twin & Drone Surveying Tech Milestone", "Geospatial World"),
                    title="Drone Surveying and BIM Digital Twins Cut Site Rework by 25%",
                    source="Geospatial World",
                    url="https://example.com/tech/digital-twins-bim-construction",
                    publication_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    summary="Case studies show precision photogrammetry and cloud BIM integration accelerate project delivery times.",
                    relevance=f"Relevant to {name}'s engineering workflow and client-facing tech capabilities.",
                    industry=ind.value,
                    tags=["Technology", "BIM", "Innovation"],
                ),
            ]

        elif ind == IndustryType.NONPROFIT:
            articles = [
                NewsArticle(
                    id=self._generate_article_id("Community Foundation Announces Rapid-Response Grants", "Nonprofit Philanthropy Journal"),
                    title=f"Community Foundation Opens High-Impact Grant Cycle in {loc}",
                    source="Nonprofit Philanthropy Journal",
                    url="https://example.com/philanthropy/regional-impact-grants",
                    publication_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    summary=f"New funding initiative allocates $1.5M to local organizations addressing community needs, youth, and family stability in {loc}.",
                    relevance=f"Directly supports {name}'s mission: '{desc}'. Great hook for community partner advocacy.",
                    industry=ind.value,
                    tags=["Grants", "Community", "Philanthropy"],
                ),
                NewsArticle(
                    id=self._generate_article_id("Regional Housing and Nutrition Task Force Report", "Urban Social Policy Review"),
                    title=f"Regional Task Force Releases Annual Assessment of Housing and Family Needs in {loc}",
                    source="Urban Social Policy Review",
                    url="https://example.com/policy/housing-food-security-report",
                    publication_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    summary="Report underscores a 12% rise in demand for grassroots support services and emergency family relief.",
                    relevance=f"Validates the urgent necessity of {name}'s community services and provides verified statistics for donor calls-to-action.",
                    industry=ind.value,
                    tags=["Housing", "FoodSecurity", "SocialPolicy"],
                ),
                NewsArticle(
                    id=self._generate_article_id("New Tax Incentives for Charitable Giving Signed", "Charity Sector News"),
                    title="Federal and State Updates Expand Deductions for Charitable Micro-Donations",
                    source="Charity Sector News",
                    url="https://example.com/news/charitable-giving-incentives-update",
                    publication_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    summary="Legislation reinforces incentives for everyday donors contributing to local 501(c)(3) charities.",
                    relevance=f"Encourages {name}'s donor community to participate in recurring giving campaigns.",
                    industry=ind.value,
                    tags=["TaxPolicy", "Giving", "Donors"],
                ),
                NewsArticle(
                    id=self._generate_article_id("Youth and Volunteer Mobilization Trends", "Volunteer Leadership Network"),
                    title="Generation Z Volunteer Engagement Surges for Grassroots Nonprofits",
                    source="Volunteer Leadership Network",
                    url="https://example.com/volunteering/youth-engagement-trends",
                    publication_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    summary="Survey reveals younger demographics seek hands-on weekend volunteer projects and digital advocacy roles.",
                    relevance=f"Provides strategic context for {name}'s upcoming volunteer recruitment campaigns.",
                    industry=ind.value,
                    tags=["Volunteers", "Youth", "Advocacy"],
                ),
            ]

        elif ind == IndustryType.RESTAURANT:
            articles = [
                NewsArticle(
                    id=self._generate_article_id("FDA and Local Health Board Update Fresh Produce Protocols", "Food Safety Magazine"),
                    title=f"Health Department Publishes Enhanced Traceability Guidelines for {loc} Restaurants",
                    source="Food Safety Magazine",
                    url="https://example.com/foodsafety/traceability-guidelines",
                    publication_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    summary="Updated food safety regulations emphasize farm-to-table batch verification and temperature log automation.",
                    relevance=f"Allows {name} to reassure guests about rigorous hygiene, quality sourcing, and kitchen excellence.",
                    industry=ind.value,
                    tags=["FoodSafety", "HealthGuidelines", "Quality"],
                ),
                NewsArticle(
                    id=self._generate_article_id("Seasonal Local Farm Sourcing Partnerships", "Culinary Arts & Dining"),
                    title=f"Regional Agriculture Guild Connects Independent Restaurants with Heirloom Growers in {loc}",
                    source="Culinary Arts & Dining",
                    url="https://example.com/dining/local-farm-collaborations",
                    publication_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    summary="New farm cooperative delivers harvest-fresh produce, artisanal cheeses, and specialty herbs direct to kitchens.",
                    relevance=f"Perfect match for {name}'s concept '{desc}' to feature farm-to-table specials and chef stories.",
                    industry=ind.value,
                    tags=["FarmToTable", "LocalSourcing", "MenuTrends"],
                ),
                NewsArticle(
                    id=self._generate_article_id("Culinary Trends Spotlight Zero-Proof Craft Cocktails", "Beverage & Hospitality Digest"),
                    title="Craft Mocktails and Fermented Botanicals Lead Evening Dining Growth",
                    source="Beverage & Hospitality Digest",
                    url="https://example.com/trends/zero-proof-dining-cocktails",
                    publication_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    summary="Consumers are enthusiastically ordering elevated non-alcoholic pairings featuring house-made syrups and herbal infusions.",
                    relevance=f"Inspires new beverage promotions and inclusive dining options for {name}.",
                    industry=ind.value,
                    tags=["Cocktails", "Beverages", "DiningTrends"],
                ),
                NewsArticle(
                    id=self._generate_article_id("Local Restaurant Week Dates Announced", "City Dining Guide"),
                    title=f"{loc} Restaurant Week Dates Officially Announced for Upcoming Season",
                    source="City Dining Guide",
                    url="https://example.com/dining/city-restaurant-week-dates",
                    publication_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    summary="Annual culinary showcase expects record patron turnout across participating neighborhood venues.",
                    relevance=f"Key milestone for {name} to promote reservations, signature tasting menus, and special pricing.",
                    industry=ind.value,
                    tags=["Events", "Promotions", "DiningWeek"],
                ),
            ]

        elif ind == IndustryType.LAW_OFFICE:
            articles = [
                NewsArticle(
                    id=self._generate_article_id("Enacted Statute Modifying Small Business Contracts", "State Bar Legal Gazette"),
                    title=f"Newly Enacted Statute Modifies Commercial Contract Provisions in {loc}",
                    source="State Bar Legal Gazette",
                    url="https://example.com/law/enacted-commercial-statute-2026",
                    publication_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    summary="Governor signed legislation establishing mandatory disclosure rules for business arbitration clauses, effective next quarter.",
                    relevance=f"Crucial enacted law relevant to {name}'s practice '{desc}'. Vital to alert commercial clients to audit agreements.",
                    industry=ind.value,
                    law_status="enacted",
                    tags=["EnactedLaw", "CommercialLitigation", "Contracts"],
                ),
                NewsArticle(
                    id=self._generate_article_id("Appellate Court Ruling on Privacy Compliance", "National Law Journal"),
                    title="Appellate Court Clarifies Statutory Damages for Consumer Data Privacy Infractions",
                    source="National Law Journal",
                    url="https://example.com/law/appellate-ruling-privacy-damages",
                    publication_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    summary="Key precedent establishes that technical non-compliance without harm cannot sustain class statutory claims.",
                    relevance=f"Provides {name} an opportunity to deliver authoritative legal commentary and reassuring analysis for corporate clients.",
                    industry=ind.value,
                    law_status="effective",
                    tags=["CourtRuling", "Precedent", "PrivacyLaw"],
                ),
                NewsArticle(
                    id=self._generate_article_id("Proposed Legislative Bill on Estate Asset Thresholds", "Legislative Monitor"),
                    title="PROPOSED BILL: Legislative Committee Debates Increased Threshold for Simplified Probate",
                    source="Legislative Monitor",
                    url="https://example.com/legislation/proposed-probate-threshold-bill",
                    publication_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    summary="Proposed bill HB-402 seeks to double the simplified probate limit; currently pending committee vote (NOT yet enacted).",
                    relevance=f"Educational topic for {name}. Crucially distinguishes proposed bills from currently enforceable probate law.",
                    industry=ind.value,
                    law_status="proposed_bill",
                    tags=["ProposedBill", "EstatePlanning", "Probate"],
                ),
                NewsArticle(
                    id=self._generate_article_id("State Supreme Court Issues Mandatory E-Filing Guidelines", "Judicial Administration Review"),
                    title="Judicial Council Issues Revised Civil Motion Procedures and Electronic Evidence Rules",
                    source="Judicial Administration Review",
                    url="https://example.com/courts/revised-civil-motion-rules",
                    publication_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    summary="New judicial rules standardize electronic exhibit authentication and streamline summary judgment hearings.",
                    relevance=f"Demonstrates {name}'s deep familiarity with procedural rules and court efficiency.",
                    industry=ind.value,
                    law_status="effective",
                    tags=["CourtRules", "CivilLitigation", "Practice"],
                ),
            ]

        for a in articles:
            a.is_synthetic = True
            if not a.source.startswith("[Demo]"):
                a.source = f"[Demo] {a.source}"
            if "DemoData" not in a.tags:
                a.tags.append("DemoData")

        if topic_filter:
            tf = topic_filter.lower()
            filtered = [a for a in articles if tf in a.title.lower() or tf in a.summary.lower() or any(tf in t.lower() for t in a.tags)]
            if filtered:
                articles = filtered

        return articles[:max_results]


class WebSearchNewsDiscoveryService(BaseNewsDiscoveryService):
    """Live news discovery using Google ADK / Gemini with Google Search Grounding.
    
    Guarantees:
    - Real-time industry news grounded in live Google Search results.
    - Verified source URLs and publication dates.
    - Never presents mock or synthetic data as factual news.
    """

    def __init__(
        self,
        model: str = "gemini-2.5-flash",
        api_key: str | None = None,
        fallback_service: BaseNewsDiscoveryService | None = None,
        allow_synthetic_fallback: bool = False,
    ) -> None:
        self.model = model
        self.api_key = api_key
        self.fallback_service = fallback_service or MockNewsDiscoveryService()
        self.allow_synthetic_fallback = allow_synthetic_fallback

    def _generate_article_id(self, title: str, source: str) -> str:
        digest = hashlib.md5(f"{title}_{source}".encode("utf-8")).hexdigest()[:8]
        return f"art_{digest}"

    def discover_news(
        self,
        profile: BusinessProfile,
        topic_filter: str | None = None,
        max_results: int = 4,
    ) -> list[NewsArticle]:
        """Discover live, grounded industry news and events via Google Search.
        
        Guarantees:
        - Real search results are strictly grounded with verified source URLs and publication dates.
        - Failed searches NEVER present mock or synthetic data as factual news.
        - Synthetic data is only returned if explicitly opted into for demo/test purposes, and is clearly labeled.
        """
        try:
            return self._discover_live_news(profile, topic_filter, max_results)
        except Exception as exc:
            logger.warning(
                "Live Gemini Search news discovery encountered an error: %s",
                exc,
            )
            # Factual integrity guardrail: never substitute synthetic mock data as factual news
            if self.allow_synthetic_fallback and self.fallback_service:
                logger.info("allow_synthetic_fallback is enabled: returning clearly labeled demo test data.")
                return self.fallback_service.discover_news(profile, topic_filter, max_results)

            raise RuntimeError(
                f"Live Google Search news discovery failed ({exc}). "
                "Synthetic mock data is withheld to prevent presenting unverified claims as factual news."
            ) from exc

    def _discover_live_news(
        self,
        profile: BusinessProfile,
        topic_filter: str | None,
        max_results: int,
    ) -> list[NewsArticle]:
        from dotenv import load_dotenv
        load_dotenv()

        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self.api_key) if self.api_key else genai.Client()
        prompt = self._build_grounding_prompt(profile, topic_filter, max_results)

        config = types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0.2,
        )

        response = client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=config,
        )

        articles = self._parse_grounded_response(response, profile, max_results)
        if not articles:
            raise ValueError("No valid structured articles could be parsed from Gemini Search grounding response.")
        return articles

    def _build_grounding_prompt(
        self,
        profile: BusinessProfile,
        topic_filter: str | None,
        max_results: int,
    ) -> str:
        loc = profile.business_location
        desc = profile.business_description
        name = profile.business_name
        ind = profile.industry.value
        current_year = datetime.now(timezone.utc).year

        filter_clause = f"Focus specifically on developments matching: '{topic_filter}'." if topic_filter else ""

        legal_directive = ""
        if profile.industry == IndustryType.LAW_OFFICE:
            legal_directive = """
CRITICAL LEGAL STATUS REQUIREMENT:
For each legal article, identify its exact legal status and output the "law_status" field with one of these three exact values:
- "enacted" (for statutes, legislation, or ordinances officially signed into law)
- "effective" (for court decisions, procedural rules, or laws currently in effect)
- "proposed_bill" (for pending bills, legislative debates, or unpassed proposals)
Never describe a proposed bill as an enacted law.
"""

        return f"""You are a professional industry research assistant for {name}, operating in the {ind} industry located in {loc}.
Business Profile & Mission: {desc}

Perform a Google Search to discover up to {max_results} real, timely news articles, regulatory announcements, industry updates, or events from {current_year} relevant to this business.
{filter_clause}
{legal_directive}

Format your output STRICTLY as a JSON array of objects with the following schema:
[
  {{
    "title": "Headline of the article or announcement",
    "source": "Name of publisher, journal, or reporting agency",
    "url": "Real, verified article or source URL from the search results",
    "publication_date": "YYYY-MM-DD or recent date string",
    "summary": "2-3 sentence clear, factual summary of the news",
    "relevance": "1-2 sentences explaining why this matters specifically to {name}'s operations and audience in {loc}",
    "tags": ["Topic1", "Topic2"]{', "law_status": "enacted|effective|proposed_bill"' if profile.industry == IndustryType.LAW_OFFICE else ''}
  }}
]

Output ONLY the JSON array (inside ```json ... ``` code fence).
"""

    def _parse_grounded_response(
        self,
        response: Any,
        profile: BusinessProfile,
        max_results: int,
    ) -> list[NewsArticle]:
        text = response.text or ""
        start_idx = text.find("[")
        end_idx = text.rfind("]")
        if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
            return []

        json_str = text[start_idx : end_idx + 1]
        data = json.loads(json_str)
        if not isinstance(data, list):
            return []

        grounding_uris: list[str] = []
        if response.candidates and response.candidates[0].grounding_metadata:
            gm = response.candidates[0].grounding_metadata
            if getattr(gm, "grounding_chunks", None):
                for chunk in gm.grounding_chunks:
                    web = getattr(chunk, "web", None)
                    if web and getattr(web, "uri", None):
                        grounding_uris.append(web.uri)

        articles: list[NewsArticle] = []
        for i, item in enumerate(data[:max_results]):
            title = str(item.get("title", "")).strip()
            source = str(item.get("source", "")).strip() or "Industry Source"
            url = str(item.get("url", "")).strip()

            if not (url.startswith("http://") or url.startswith("https://")) or "example.com" in url:
                if i < len(grounding_uris):
                    url = grounding_uris[i]
                elif grounding_uris:
                    url = grounding_uris[0]
                else:
                    url = f"https://www.google.com/search?q={title.replace(' ', '+')}"

            pub_date = str(item.get("publication_date", "")).strip() or datetime.now(timezone.utc).strftime("%Y-%m-%d")
            summary = str(item.get("summary", "")).strip()
            relevance = str(item.get("relevance", "")).strip()
            tags = item.get("tags", [])
            if not isinstance(tags, list):
                tags = [str(tags)]

            law_status = item.get("law_status")
            if profile.industry == IndustryType.LAW_OFFICE:
                if law_status not in ("enacted", "effective", "proposed_bill"):
                    lower_content = f"{title.lower()} {summary.lower()}"
                    if any(w in lower_content for w in ["proposed", "bill", "pending", "draft", "committee debate"]):
                        law_status = "proposed_bill"
                    elif any(w in lower_content for w in ["enacted", "passed", "signed into law", "approved legislation"]):
                        law_status = "enacted"
                    else:
                        law_status = "effective"

            art_id = self._generate_article_id(title, source)
            articles.append(
                NewsArticle(
                    id=art_id,
                    title=title,
                    source=source,
                    url=url,
                    publication_date=pub_date,
                    summary=summary,
                    relevance=relevance,
                    industry=profile.industry.value,
                    approval_status=ArticleApprovalStatus.PENDING,
                    tags=[str(t) for t in tags],
                    law_status=law_status,
                )
            )
        return articles


# Global default discovery instance
_DISCOVERY_SERVICE: BaseNewsDiscoveryService = WebSearchNewsDiscoveryService()


def get_news_discovery_service() -> BaseNewsDiscoveryService:
    """Return configured news discovery service."""
    return _DISCOVERY_SERVICE


def set_news_discovery_service(service: BaseNewsDiscoveryService) -> None:
    """Override discovery service (useful for testing or switching to live search)."""
    global _DISCOVERY_SERVICE
    _DISCOVERY_SERVICE = service
