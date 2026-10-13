"""Multi-tenant approval manager enforcing strict business isolation and platform selection."""

from __future__ import annotations

import threading
from typing import Sequence

from app.models.caption import CaptionDraft, CaptionStatus
from app.models.news import ArticleApprovalStatus, NewsArticle
from app.storage.firestore_store import get_persistence_repository


class MultiTenantApprovalManager:
    """Manages human approval decisions scoped strictly by business identity."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def _repo(self):
        return get_persistence_repository()

    # News Articles
    def register_articles(self, business_id: str, articles: Sequence[NewsArticle]) -> None:
        """Register newly discovered articles for an individual business."""
        self._repo().save_discovered_news(business_id, list(articles))

    def get_article(self, business_id: str, article_id: str) -> NewsArticle | None:
        return self._repo().get_news_article(business_id, article_id)

    def list_articles(
        self,
        business_id: str,
        status: ArticleApprovalStatus | None = None,
    ) -> list[NewsArticle]:
        return self._repo().list_news(business_id, status=status)

    def approve_article(self, business_id: str, article_id: str) -> tuple[NewsArticle, str]:
        """Approve an article and initiate platform selection without auto-generating captions."""
        article = self._repo().approve_news_article(business_id, article_id)
        prompt = (
            f"✅ **Article Approved:** {article.title}\n\n"
            f"Which social media platform(s) would you like to create draft captions for? "
            f"(e.g., LinkedIn, Instagram, Facebook, X)"
        )
        return article, prompt

    def select_platforms_for_article(
        self,
        business_id: str,
        article_id: str,
        platforms: list[str],
    ) -> NewsArticle:
        """Record selected social platforms for an approved article."""
        if not platforms:
            raise ValueError("At least one target social media platform must be selected.")
        return self._repo().set_article_platforms(business_id, article_id, platforms)

    def reject_article(self, business_id: str, article_id: str) -> NewsArticle:
        """Reject an article and permanently prevent future recommendation."""
        return self._repo().reject_news_article(business_id, article_id)

    def get_approved_articles(self, business_id: str) -> list[NewsArticle]:
        """Return articles finalized with platform selection."""
        return self._repo().list_news(business_id, status=ArticleApprovalStatus.APPROVED)

    # Captions
    def register_captions(self, business_id: str, captions: Sequence[CaptionDraft]) -> None:
        repo = self._repo()
        for cap in captions:
            repo.save_caption(business_id, cap)

    def get_caption(self, business_id: str, caption_id: str) -> CaptionDraft | None:
        return self._repo().get_caption(business_id, caption_id)

    def list_captions(
        self,
        business_id: str,
        month: str | None = None,
        year: int | None = None,
    ) -> list[CaptionDraft]:
        return self._repo().list_captions(business_id, month=month, year=year)

    def update_caption_revision(
        self,
        business_id: str,
        caption_id: str,
        new_text: str,
        new_hashtags: list[str] | None = None,
        note: str | None = None,
    ) -> CaptionDraft:
        """Apply and preserve new revision in version history."""
        return self._repo().update_caption_revision(
            business_id, caption_id, new_text, new_hashtags=new_hashtags, note=note
        )

    def restore_caption_version(
        self,
        business_id: str,
        caption_id: str,
        target_version: int,
    ) -> CaptionDraft:
        """Restore previous version from history."""
        return self._repo().restore_caption_version(business_id, caption_id, target_version)

    def update_caption_status(
        self,
        business_id: str,
        caption_id: str,
        new_status: CaptionStatus,
    ) -> CaptionDraft:
        return self._repo().update_caption_status(business_id, caption_id, new_status)


_MULTI_TENANT_APPROVAL: MultiTenantApprovalManager | None = None


def get_multi_tenant_approval_manager() -> MultiTenantApprovalManager:
    """Return default multi-tenant approval manager."""
    global _MULTI_TENANT_APPROVAL
    if _MULTI_TENANT_APPROVAL is None:
        _MULTI_TENANT_APPROVAL = MultiTenantApprovalManager()
    return _MULTI_TENANT_APPROVAL
