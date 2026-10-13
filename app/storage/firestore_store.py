"""Firestore persistence implementation and local document repository."""

from __future__ import annotations

import logging
import os
import threading
from typing import Any

from app.models.caption import CaptionDraft, CaptionStatus
from app.models.conversation import ChatMessage, MonthlyConversation
from app.models.news import ArticleApprovalStatus, NewsArticle
from app.models.notification import InAppNotification, NotificationPreferences
from app.models.profile import BusinessProfile
from app.storage.repository_interface import BasePersistenceRepository

logger = logging.getLogger(__name__)


class LocalDocumentRepository(BasePersistenceRepository):
    """Thread-safe document repository modeling Firestore collections locally.

    Partitions all records strictly by business_id to guarantee multi-tenant isolation
    during local development and testing without provisioning cloud resources.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # Partitioned dictionaries: business_id -> domain_dict
        self._profiles: dict[str, BusinessProfile] = {}
        self._conversations: dict[str, dict[str, MonthlyConversation]] = {}  # biz_id -> {conv_id: obj}
        self._captions: dict[str, dict[str, CaptionDraft]] = {}  # biz_id -> {cap_id: obj}
        self._news: dict[str, dict[str, NewsArticle]] = {}  # biz_id -> {art_id: obj}
        self._rejected_news_ids: dict[str, set[str]] = {}  # biz_id -> {art_id}
        self._preferences: dict[str, NotificationPreferences] = {}
        self._notifications: dict[str, list[InAppNotification]] = {}

    # 1. Profiles
    def get_profile(self, business_id: str) -> BusinessProfile | None:
        with self._lock:
            return self._profiles.get(business_id)

    def save_profile(self, profile: BusinessProfile) -> None:
        with self._lock:
            self._profiles[profile.business_id] = profile.model_copy(deep=True)

    def update_profile(self, business_id: str, updates: dict) -> BusinessProfile:
        with self._lock:
            prof = self._profiles.get(business_id)
            if not prof:
                raise KeyError(f"Business profile '{business_id}' does not exist.")
            prof.update(**updates)
            return prof

    def exists(self, business_id: str) -> bool:
        with self._lock:
            return business_id in self._profiles

    def delete_profile(self, business_id: str) -> bool:
        with self._lock:
            return self._profiles.pop(business_id, None) is not None

    # 2. Conversations
    def _conv_id(self, business_id: str, year: int, month: int) -> str:
        return f"conv_{business_id}_{year}_{month:02d}"

    def get_or_create_monthly_conversation(
        self,
        business_id: str,
        year: int,
        month: int,
        month_name: str,
    ) -> tuple[MonthlyConversation, bool]:
        with self._lock:
            cid = self._conv_id(business_id, year, month)
            biz_convs = self._conversations.setdefault(business_id, {})
            if cid in biz_convs:
                return biz_convs[cid], False
            conv = MonthlyConversation(
                id=cid,
                business_id=business_id,
                year=year,
                month=month,
                month_name=month_name,
            )
            biz_convs[cid] = conv
            return conv, True

    def get_monthly_conversation(
        self,
        business_id: str,
        year: int,
        month: int,
    ) -> MonthlyConversation | None:
        with self._lock:
            cid = self._conv_id(business_id, year, month)
            return self._conversations.get(business_id, {}).get(cid)

    def list_monthly_conversations(self, business_id: str) -> list[MonthlyConversation]:
        with self._lock:
            convs = list(self._conversations.get(business_id, {}).values())
            convs.sort(key=lambda c: (c.year, c.month), reverse=True)
            return convs

    def append_message(
        self,
        business_id: str,
        year: int,
        month: int,
        message: ChatMessage,
    ) -> None:
        with self._lock:
            cid = self._conv_id(business_id, year, month)
            biz_convs = self._conversations.setdefault(business_id, {})
            conv = biz_convs.get(cid)
            if not conv:
                conv = MonthlyConversation(
                    id=cid,
                    business_id=business_id,
                    year=year,
                    month=month,
                    month_name="",
                )
                biz_convs[cid] = conv
            conv.messages.append(message)

    # 3. Captions
    def save_caption(self, business_id: str, caption: CaptionDraft) -> None:
        with self._lock:
            cap_copy = caption.model_copy(deep=True)
            cap_copy.business_id = business_id
            biz_caps = self._captions.setdefault(business_id, {})
            biz_caps[cap_copy.id] = cap_copy

    def get_caption(self, business_id: str, caption_id: str) -> CaptionDraft | None:
        with self._lock:
            cap = self._captions.get(business_id, {}).get(caption_id)
            return cap.model_copy(deep=True) if cap else None

    def list_captions(
        self,
        business_id: str,
        month: str | None = None,
        year: int | None = None,
    ) -> list[CaptionDraft]:
        with self._lock:
            caps = [c.model_copy(deep=True) for c in self._captions.get(business_id, {}).values()]
            if month:
                caps = [c for c in caps if c.month.lower() == month.lower()]
            if year:
                caps = [c for c in caps if c.year == year]
            return caps

    def update_caption_revision(
        self,
        business_id: str,
        caption_id: str,
        new_text: str,
        new_hashtags: list[str] | None = None,
        note: str | None = None,
    ) -> CaptionDraft:
        with self._lock:
            cap = self._captions.get(business_id, {}).get(caption_id)
            if not cap:
                raise KeyError(f"Caption '{caption_id}' for business '{business_id}' not found.")
            cap.save_revision(new_text=new_text, new_hashtags=new_hashtags, note=note)
            return cap.model_copy(deep=True)

    def restore_caption_version(
        self,
        business_id: str,
        caption_id: str,
        target_version: int,
    ) -> CaptionDraft:
        with self._lock:
            cap = self._captions.get(business_id, {}).get(caption_id)
            if not cap:
                raise KeyError(f"Caption '{caption_id}' for business '{business_id}' not found.")
            restored = cap.restore_version(target_version)
            if not restored:
                raise ValueError(f"Version {target_version} does not exist in history for caption '{caption_id}'.")
            return cap.model_copy(deep=True)

    def update_caption_status(
        self,
        business_id: str,
        caption_id: str,
        status: CaptionStatus,
    ) -> CaptionDraft:
        with self._lock:
            cap = self._captions.get(business_id, {}).get(caption_id)
            if not cap:
                raise KeyError(f"Caption '{caption_id}' for business '{business_id}' not found.")
            cap.status = status
            return cap.model_copy(deep=True)

    # 4. News Articles
    def save_discovered_news(self, business_id: str, articles: list[NewsArticle]) -> None:
        with self._lock:
            biz_news = self._news.setdefault(business_id, {})
            rejected = self._rejected_news_ids.setdefault(business_id, set())
            for art in articles:
                # Do not re-add previously rejected articles
                if art.id in rejected:
                    continue
                art_copy = art.model_copy(deep=True)
                art_copy.business_id = business_id
                biz_news[art_copy.id] = art_copy

    def list_news(
        self,
        business_id: str,
        status: ArticleApprovalStatus | None = None,
    ) -> list[NewsArticle]:
        with self._lock:
            arts = [a.model_copy(deep=True) for a in self._news.get(business_id, {}).values()]
            if status is not None:
                arts = [a for a in arts if a.approval_status == status]
            return arts

    def get_news_article(self, business_id: str, article_id: str) -> NewsArticle | None:
        with self._lock:
            art = self._news.get(business_id, {}).get(article_id)
            return art.model_copy(deep=True) if art else None

    def approve_news_article(self, business_id: str, article_id: str) -> NewsArticle:
        with self._lock:
            art = self._news.get(business_id, {}).get(article_id)
            if not art:
                raise KeyError(f"News article '{article_id}' for business '{business_id}' not found.")
            # Move to awaiting platforms
            art.approval_status = ArticleApprovalStatus.APPROVED_AWAITING_PLATFORMS
            return art

    def set_article_platforms(
        self,
        business_id: str,
        article_id: str,
        platforms: list[str],
    ) -> NewsArticle:
        with self._lock:
            art = self._news.get(business_id, {}).get(article_id)
            if not art:
                raise KeyError(f"News article '{article_id}' for business '{business_id}' not found.")
            art.selected_platforms = platforms
            art.approval_status = ArticleApprovalStatus.APPROVED
            return art

    def reject_news_article(self, business_id: str, article_id: str) -> NewsArticle:
        with self._lock:
            art = self._news.get(business_id, {}).get(article_id)
            if not art:
                raise KeyError(f"News article '{article_id}' for business '{business_id}' not found.")
            art.approval_status = ArticleApprovalStatus.REJECTED
            self._rejected_news_ids.setdefault(business_id, set()).add(article_id)
            return art

    def is_article_rejected(self, business_id: str, article_id: str) -> bool:
        with self._lock:
            return article_id in self._rejected_news_ids.get(business_id, set())

    def is_article_known(self, business_id: str, article_id: str) -> bool:
        with self._lock:
            return (
                article_id in self._news.get(business_id, {})
                or article_id in self._rejected_news_ids.get(business_id, set())
            )

    # 5. Notifications
    def get_notification_preferences(self, business_id: str) -> NotificationPreferences:
        with self._lock:
            prefs = self._preferences.get(business_id)
            if not prefs:
                prof = self._profiles.get(business_id)
                email = prof.business_name if prof else "user@example.com"
                prefs = NotificationPreferences(business_id=business_id, email=email)
                self._preferences[business_id] = prefs
            return prefs

    def update_notification_preferences(
        self,
        business_id: str,
        prefs: NotificationPreferences,
    ) -> None:
        with self._lock:
            prefs.business_id = business_id
            self._preferences[business_id] = prefs

    def add_notification(self, business_id: str, notification: InAppNotification) -> None:
        with self._lock:
            notification.business_id = business_id
            notifs = self._notifications.setdefault(business_id, [])
            notifs.insert(0, notification)

    def list_notifications(
        self,
        business_id: str,
        unread_only: bool = False,
    ) -> list[InAppNotification]:
        with self._lock:
            notifs = list(self._notifications.get(business_id, []))
            if unread_only:
                notifs = [n for n in notifs if not n.read]
            return notifs

    def mark_notification_read(self, business_id: str, notification_id: str) -> bool:
        with self._lock:
            for n in self._notifications.get(business_id, []):
                if n.id == notification_id:
                    n.read = True
                    return True
            return False

    # 6. Cascading Deletion
    def delete_all_business_data(self, business_id: str) -> bool:
        with self._lock:
            self._profiles.pop(business_id, None)
            self._conversations.pop(business_id, None)
            self._captions.pop(business_id, None)
            self._news.pop(business_id, None)
            self._rejected_news_ids.pop(business_id, None)
            self._preferences.pop(business_id, None)
            self._notifications.pop(business_id, None)
            return True


class FirestoreRepository(BasePersistenceRepository):
    """Google Cloud Firestore client wrapper with local fallback."""

    def __init__(self, fallback: BasePersistenceRepository | None = None) -> None:
        self._fallback = fallback or LocalDocumentRepository()
        self._firestore_active = False

        try:
            import google.cloud.firestore
            project = os.environ.get("GOOGLE_CLOUD_PROJECT")
            if project and not os.environ.get("USE_LOCAL_STORAGE"):
                self._db = google.cloud.firestore.Client(project=project)
                self._firestore_active = True
            else:
                self._firestore_active = False
        except (ImportError, Exception) as exc:
            logger.info("Firestore client not initialized (%s); using local document repository.", exc)
            self._firestore_active = False

    @property
    def is_live_firestore(self) -> bool:
        return self._firestore_active

    def get_profile(self, business_id: str) -> BusinessProfile | None:
        prof = self._fallback.get_profile(business_id)
        if not prof and self._firestore_active:
            try:
                doc = self._db.collection("businesses").document(business_id).collection("data").document("profile").get()
                if doc.exists:
                    prof = BusinessProfile(**doc.to_dict())
                    self._fallback.save_profile(prof)
            except Exception as e:
                logger.warning("Firestore get_profile failed: %s", e)
        return prof

    def save_profile(self, profile: BusinessProfile) -> None:
        self._fallback.save_profile(profile)
        if self._firestore_active:
            try:
                self._db.collection("businesses").document(profile.business_id).collection("data").document("profile").set(profile.model_dump())
            except Exception as e:
                logger.warning("Firestore save_profile failed: %s", e)

    def update_profile(self, business_id: str, updates: dict) -> BusinessProfile:
        updated = self._fallback.update_profile(business_id, updates)
        if self._firestore_active:
            try:
                self._db.collection("businesses").document(business_id).collection("data").document("profile").set(updated.model_dump())
            except Exception as e:
                logger.warning("Firestore update_profile failed: %s", e)
        return updated

    def exists(self, business_id: str) -> bool:
        if self._fallback.exists(business_id):
            return True
        if self._firestore_active:
            try:
                doc = self._db.collection("businesses").document(business_id).collection("data").document("profile").get()
                return doc.exists
            except Exception:
                pass
        return False

    def delete_profile(self, business_id: str) -> bool:
        res = self._fallback.delete_profile(business_id)
        if self._firestore_active:
            try:
                self._db.collection("businesses").document(business_id).collection("data").document("profile").delete()
            except Exception:
                pass
        return res

    def get_or_create_monthly_conversation(
        self, business_id: str, year: int, month: int, month_name: str
    ) -> tuple[MonthlyConversation, bool]:
        return self._fallback.get_or_create_monthly_conversation(business_id, year, month, month_name)

    def get_monthly_conversation(
        self, business_id: str, year: int, month: int
    ) -> MonthlyConversation | None:
        return self._fallback.get_monthly_conversation(business_id, year, month)

    def list_monthly_conversations(self, business_id: str) -> list[MonthlyConversation]:
        return self._fallback.list_monthly_conversations(business_id)

    def append_message(
        self, business_id: str, year: int, month: int, message: ChatMessage
    ) -> None:
        self._fallback.append_message(business_id, year, month, message)
        if self._firestore_active:
            try:
                conv_id = f"conv_{business_id}_{year}_{month:02d}"
                self._db.collection("businesses").document(business_id).collection("conversations").document(conv_id).collection("messages").document(message.id).set(message.model_dump())
            except Exception as e:
                logger.warning("Firestore append_message failed: %s", e)

    def save_caption(self, business_id: str, caption: CaptionDraft) -> None:
        self._fallback.save_caption(business_id, caption)
        if self._firestore_active:
            try:
                self._db.collection("businesses").document(business_id).collection("captions").document(caption.id).set(caption.model_dump())
            except Exception as e:
                logger.warning("Firestore save_caption failed: %s", e)

    def get_caption(self, business_id: str, caption_id: str) -> CaptionDraft | None:
        return self._fallback.get_caption(business_id, caption_id)

    def list_captions(
        self, business_id: str, month: str | None = None, year: int | None = None
    ) -> list[CaptionDraft]:
        return self._fallback.list_captions(business_id, month, year)

    def update_caption_revision(
        self, business_id: str, caption_id: str, new_text: str, new_hashtags: list[str] | None = None, note: str | None = None
    ) -> CaptionDraft:
        return self._fallback.update_caption_revision(business_id, caption_id, new_text, new_hashtags, note)

    def restore_caption_version(
        self, business_id: str, caption_id: str, target_version: int
    ) -> CaptionDraft:
        return self._fallback.restore_caption_version(business_id, caption_id, target_version)

    def update_caption_status(
        self, business_id: str, caption_id: str, status: CaptionStatus
    ) -> CaptionDraft:
        return self._fallback.update_caption_status(business_id, caption_id, status)

    def save_discovered_news(self, business_id: str, articles: list[NewsArticle]) -> None:
        self._fallback.save_discovered_news(business_id, articles)

    def list_news(
        self, business_id: str, status: ArticleApprovalStatus | None = None
    ) -> list[NewsArticle]:
        return self._fallback.list_news(business_id, status)

    def get_news_article(self, business_id: str, article_id: str) -> NewsArticle | None:
        return self._fallback.get_news_article(business_id, article_id)

    def approve_news_article(self, business_id: str, article_id: str) -> NewsArticle:
        return self._fallback.approve_news_article(business_id, article_id)

    def set_article_platforms(
        self, business_id: str, article_id: str, platforms: list[str]
    ) -> NewsArticle:
        return self._fallback.set_article_platforms(business_id, article_id, platforms)

    def reject_news_article(self, business_id: str, article_id: str) -> NewsArticle:
        return self._fallback.reject_news_article(business_id, article_id)

    def is_article_rejected(self, business_id: str, article_id: str) -> bool:
        return self._fallback.is_article_rejected(business_id, article_id)

    def is_article_known(self, business_id: str, article_id: str) -> bool:
        return self._fallback.is_article_known(business_id, article_id)

    def get_notification_preferences(self, business_id: str) -> NotificationPreferences:
        return self._fallback.get_notification_preferences(business_id)

    def update_notification_preferences(
        self, business_id: str, prefs: NotificationPreferences
    ) -> None:
        self._fallback.update_notification_preferences(business_id, prefs)

    def add_notification(self, business_id: str, notification: InAppNotification) -> None:
        self._fallback.add_notification(business_id, notification)

    def list_notifications(
        self, business_id: str, unread_only: bool = False
    ) -> list[InAppNotification]:
        return self._fallback.list_notifications(business_id, unread_only)

    def mark_notification_read(self, business_id: str, notification_id: str) -> bool:
        return self._fallback.mark_notification_read(business_id, notification_id)

    def delete_all_business_data(self, business_id: str) -> bool:
        return self._fallback.delete_all_business_data(business_id)


_REPOSITORY: BasePersistenceRepository | None = None


def get_persistence_repository() -> BasePersistenceRepository:
    """Return default configured persistence repository."""
    global _REPOSITORY
    if _REPOSITORY is None:
        _REPOSITORY = FirestoreRepository()
    return _REPOSITORY


def set_persistence_repository(repo: BasePersistenceRepository) -> None:
    """Override persistence repository for unit testing."""
    global _REPOSITORY
    _REPOSITORY = repo
