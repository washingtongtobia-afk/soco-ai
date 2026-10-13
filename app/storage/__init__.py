"""Storage package for persistent profiles, conversations, captions, and data."""

from app.storage.firestore_store import (
    FirestoreRepository,
    LocalDocumentRepository,
    get_persistence_repository,
    set_persistence_repository,
)
from app.storage.profile_store import (
    BaseProfileStore,
    LocalJsonProfileStore,
    get_default_store,
    set_default_store,
)
from app.storage.repository_interface import BasePersistenceRepository

__all__ = [
    "BasePersistenceRepository",
    "BaseProfileStore",
    "FirestoreRepository",
    "LocalDocumentRepository",
    "LocalJsonProfileStore",
    "get_default_store",
    "get_persistence_repository",
    "set_default_store",
    "set_persistence_repository",
]
