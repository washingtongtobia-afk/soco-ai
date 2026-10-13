"""Human approval and review service for articles and generated captions.

Guarantees:
- Explicit human approval or rejection of discovered news articles
- Only approved articles can proceed to caption generation
- All generated captions remain drafts until explicitly reviewed
- No automatic social media posting is ever permitted
"""

from __future__ import annotations

import re
from typing import Sequence

from app.models.caption import CaptionDraft, CaptionStatus
from app.models.news import ArticleApprovalStatus, NewsArticle

INJECTION_PATTERNS: list[str] = [
    r"(?i)\bignore\s+(?:all\s+|previous\s+|prior\s+)*instructions\b",
    r"(?i)\bdisregard\s+(?:all\s+|previous\s+|prior\s+)*instructions\b",
    r"(?i)\b(you\s+are\s+now|act\s+as|pretend\s+to\s+be)\b",
    r"(?i)\b(system\s+prompt|new\s+instructions|prompt\s+override)\b",
    r"(?i)\b(forget|discard)\s+(everything|all)\s+(above|previous)\b",
    r"(?i)<\s*(system|instruction|prompt)\s*>",
    r"(?i)\[\s*(system|instruction|prompt)\s*\]",
]


def sanitize_external_content(text: str | None) -> str:
    """Sanitize and defang prompt injection patterns in external content.

    Neutralizes malicious prompt injection attempts while preserving
    legitimate factual text and news summaries.
    """
    if not text:
        return ""
    sanitized = text
    for pattern in INJECTION_PATTERNS:
        sanitized = re.sub(pattern, "[sanitized]", sanitized)
    return sanitized.strip()


def assert_approved(article: NewsArticle) -> None:
    """Enforce explicit human approval gate.

    Raises PermissionError if article is not in ArticleApprovalStatus.APPROVED status.
    """
    if article.approval_status != ArticleApprovalStatus.APPROVED:
        raise PermissionError(
            f"Article '{article.id}' ('{article.title}') is '{article.approval_status.value}' "
            f"and has not been approved for caption generation."
        )


class ApprovalManager:
    """Manages human approval decisions for articles and captions."""

    def __init__(self) -> None:
        self._articles: dict[str, NewsArticle] = {}
        self._captions: dict[str, CaptionDraft] = {}

    def register_articles(self, articles: Sequence[NewsArticle]) -> None:
        """Register newly discovered articles for review."""
        for art in articles:
            self._articles[art.id] = art

    def get_article(self, article_id: str) -> NewsArticle | None:
        return self._articles.get(article_id)

    def list_articles(
        self,
        status: ArticleApprovalStatus | None = None,
    ) -> list[NewsArticle]:
        """List articles, optionally filtered by status."""
        if status is None:
            return list(self._articles.values())
        return [a for a in self._articles.values() if a.approval_status == status]

    def approve_article(self, article_id: str) -> NewsArticle:
        """Approve an individual news article for caption generation."""
        article = self._articles.get(article_id)
        if not article:
            raise KeyError(f"Article with id '{article_id}' not found.")
        article.approval_status = ArticleApprovalStatus.APPROVED
        return article

    def reject_article(self, article_id: str) -> NewsArticle:
        """Reject an individual news article."""
        article = self._articles.get(article_id)
        if not article:
            raise KeyError(f"Article with id '{article_id}' not found.")
        article.approval_status = ArticleApprovalStatus.REJECTED
        return article

    def get_approved_articles(self) -> list[NewsArticle]:
        """Return only articles approved by the user."""
        return [a for a in self._articles.values() if a.approval_status == ArticleApprovalStatus.APPROVED]

    # Caption Review
    def register_captions(self, captions: Sequence[CaptionDraft]) -> None:
        """Register newly generated draft captions."""
        for cap in captions:
            self._captions[cap.id] = cap

    def get_caption(self, caption_id: str) -> CaptionDraft | None:
        return self._captions.get(caption_id)

    def list_captions(
        self,
        status: CaptionStatus | None = None,
    ) -> list[CaptionDraft]:
        if status is None:
            return list(self._captions.values())
        return [c for c in self._captions.values() if c.status == status]

    def update_caption_status(
        self,
        caption_id: str,
        new_status: CaptionStatus,
        edited_text: str | None = None,
    ) -> CaptionDraft:
        """Update caption review status and optional text edits."""
        cap = self._captions.get(caption_id)
        if not cap:
            raise KeyError(f"Caption with id '{caption_id}' not found.")
        cap.status = new_status
        if edited_text:
            cap.caption_text = edited_text
        return cap


# Singleton approval manager
_APPROVAL_MANAGER = ApprovalManager()


def get_approval_manager() -> ApprovalManager:
    """Return default approval manager."""
    return _APPROVAL_MANAGER
