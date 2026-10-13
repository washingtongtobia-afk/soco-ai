"""Persistence repository interface for multi-tenant SoCo Agent data."""

from __future__ import annotations

import abc
from app.models.caption import CaptionDraft, CaptionStatus
from app.models.conversation import ChatMessage, MonthlyConversation
from app.models.news import ArticleApprovalStatus, NewsArticle
from app.models.notification import InAppNotification, NotificationPreferences
from app.models.profile import BusinessProfile


class BasePersistenceRepository(abc.ABC):
    """Abstract repository managing all business workspace data."""

    # 1. Business Profiles
    @abc.abstractmethod
    def get_profile(self, business_id: str) -> BusinessProfile | None:
        raise NotImplementedError

    @abc.abstractmethod
    def save_profile(self, profile: BusinessProfile) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def update_profile(self, business_id: str, updates: dict) -> BusinessProfile:
        raise NotImplementedError

    @abc.abstractmethod
    def exists(self, business_id: str) -> bool:
        raise NotImplementedError

    @abc.abstractmethod
    def delete_profile(self, business_id: str) -> bool:
        raise NotImplementedError

    # 2. Monthly Conversations & Messages
    @abc.abstractmethod
    def get_or_create_monthly_conversation(
        self,
        business_id: str,
        year: int,
        month: int,
        month_name: str,
    ) -> tuple[MonthlyConversation, bool]:
        """Return (conversation, created_new)."""
        raise NotImplementedError

    @abc.abstractmethod
    def get_monthly_conversation(
        self,
        business_id: str,
        year: int,
        month: int,
    ) -> MonthlyConversation | None:
        raise NotImplementedError

    @abc.abstractmethod
    def list_monthly_conversations(self, business_id: str) -> list[MonthlyConversation]:
        raise NotImplementedError

    @abc.abstractmethod
    def append_message(
        self,
        business_id: str,
        year: int,
        month: int,
        message: ChatMessage,
    ) -> None:
        raise NotImplementedError

    # 3. Caption Drafts & Versions
    @abc.abstractmethod
    def save_caption(self, business_id: str, caption: CaptionDraft) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def get_caption(self, business_id: str, caption_id: str) -> CaptionDraft | None:
        raise NotImplementedError

    @abc.abstractmethod
    def list_captions(
        self,
        business_id: str,
        month: str | None = None,
        year: int | None = None,
    ) -> list[CaptionDraft]:
        raise NotImplementedError

    @abc.abstractmethod
    def update_caption_revision(
        self,
        business_id: str,
        caption_id: str,
        new_text: str,
        new_hashtags: list[str] | None = None,
        note: str | None = None,
    ) -> CaptionDraft:
        raise NotImplementedError

    @abc.abstractmethod
    def restore_caption_version(
        self,
        business_id: str,
        caption_id: str,
        target_version: int,
    ) -> CaptionDraft:
        raise NotImplementedError

    @abc.abstractmethod
    def update_caption_status(
        self,
        business_id: str,
        caption_id: str,
        status: CaptionStatus,
    ) -> CaptionDraft:
        raise NotImplementedError

    # 4. News Articles
    @abc.abstractmethod
    def save_discovered_news(self, business_id: str, articles: list[NewsArticle]) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def list_news(
        self,
        business_id: str,
        status: ArticleApprovalStatus | None = None,
    ) -> list[NewsArticle]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_news_article(self, business_id: str, article_id: str) -> NewsArticle | None:
        raise NotImplementedError

    @abc.abstractmethod
    def approve_news_article(self, business_id: str, article_id: str) -> NewsArticle:
        """Move article to APPROVED_AWAITING_PLATFORMS."""
        raise NotImplementedError

    @abc.abstractmethod
    def set_article_platforms(
        self,
        business_id: str,
        article_id: str,
        platforms: list[str],
    ) -> NewsArticle:
        """Record selected social platforms and finalize approval for caption generation."""
        raise NotImplementedError

    @abc.abstractmethod
    def reject_news_article(self, business_id: str, article_id: str) -> NewsArticle:
        """Mark article as rejected so it is never recommended again."""
        raise NotImplementedError

    @abc.abstractmethod
    def is_article_rejected(self, business_id: str, article_id: str) -> bool:
        raise NotImplementedError

    @abc.abstractmethod
    def is_article_known(self, business_id: str, article_id: str) -> bool:
        raise NotImplementedError

    # 5. Notifications & Preferences
    @abc.abstractmethod
    def get_notification_preferences(self, business_id: str) -> NotificationPreferences:
        raise NotImplementedError

    @abc.abstractmethod
    def update_notification_preferences(
        self,
        business_id: str,
        prefs: NotificationPreferences,
    ) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def add_notification(self, business_id: str, notification: InAppNotification) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def list_notifications(
        self,
        business_id: str,
        unread_only: bool = False,
    ) -> list[InAppNotification]:
        raise NotImplementedError

    @abc.abstractmethod
    def mark_notification_read(self, business_id: str, notification_id: str) -> bool:
        raise NotImplementedError

    # 6. Cascading Account Deletion
    @abc.abstractmethod
    def delete_all_business_data(self, business_id: str) -> bool:
        """Permanently delete all data associated with business."""
        raise NotImplementedError
