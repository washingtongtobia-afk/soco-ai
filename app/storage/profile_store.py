"""Storage layer for business profile persistence.

Provides an abstract interface BaseProfileStore and a local JSON-backed
implementation LocalJsonProfileStore that can be replaced by a database
repository (PostgreSQL, Cloud SQL, Firestore) without affecting domain logic.
"""

from __future__ import annotations

import abc
import json
import os
from pathlib import Path

from app.models.profile import BusinessProfile


class BaseProfileStore(abc.ABC):
    """Abstract profile storage interface."""

    @abc.abstractmethod
    def get_profile(self, business_id: str = "default") -> BusinessProfile | None:
        """Retrieve a business profile by ID, or None if not found."""
        raise NotImplementedError

    @abc.abstractmethod
    def save_profile(self, profile: BusinessProfile) -> None:
        """Persist a business profile."""
        raise NotImplementedError

    @abc.abstractmethod
    def update_profile(self, business_id: str, updates: dict) -> BusinessProfile:
        """Apply partial updates to an existing profile."""
        raise NotImplementedError

    @abc.abstractmethod
    def exists(self, business_id: str = "default") -> bool:
        """Check if a profile exists."""
        raise NotImplementedError

    @abc.abstractmethod
    def delete_profile(self, business_id: str = "default") -> bool:
        """Delete a profile (useful for testing or resets)."""
        raise NotImplementedError


class LocalJsonProfileStore(BaseProfileStore):
    """Local JSON file-backed profile store for prototype development."""

    def __init__(self, storage_dir: Path | str | None = None) -> None:
        if storage_dir is None:
            # Default to data/ directory in project root
            base_dir = Path(__file__).resolve().parent.parent.parent
            self.storage_dir = base_dir / "data"
        else:
            self.storage_dir = Path(storage_dir)

        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.file_path = self.storage_dir / "business_profiles.json"
        if not self.file_path.exists():
            self._write_all({})

    def _read_all(self) -> dict[str, dict]:
        try:
            if not self.file_path.exists():
                return {}
            content = self.file_path.read_text(encoding="utf-8").strip()
            if not content:
                return {}
            return json.loads(content)
        except (OSError, json.JSONDecodeError):
            return {}

    def _write_all(self, data: dict[str, dict]) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        temp_file = self.file_path.with_suffix(".tmp")
        temp_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(temp_file, self.file_path)

    def get_profile(self, business_id: str = "default") -> BusinessProfile | None:
        data = self._read_all()
        raw = data.get(business_id)
        if not raw:
            return None
        return BusinessProfile.model_validate(raw)

    def save_profile(self, profile: BusinessProfile) -> None:
        data = self._read_all()
        data[profile.business_id] = profile.model_dump()
        self._write_all(data)

    def update_profile(self, business_id: str, updates: dict) -> BusinessProfile:
        profile = self.get_profile(business_id)
        if profile is None:
            raise KeyError(f"Business profile with ID '{business_id}' does not exist.")
        profile.update(**updates)
        self.save_profile(profile)
        return profile

    def exists(self, business_id: str = "default") -> bool:
        return self.get_profile(business_id) is not None

    def delete_profile(self, business_id: str = "default") -> bool:
        data = self._read_all()
        if business_id in data:
            del data[business_id]
            self._write_all(data)
            return True
        return False


# Singleton default instance
_DEFAULT_STORE: BaseProfileStore | None = None


def get_default_store() -> BaseProfileStore:
    """Return the global configured profile store."""
    global _DEFAULT_STORE
    if _DEFAULT_STORE is None:
        _DEFAULT_STORE = LocalJsonProfileStore()
    return _DEFAULT_STORE


def set_default_store(store: BaseProfileStore) -> None:
    """Override store instance (useful for unit tests with temp paths)."""
    global _DEFAULT_STORE
    _DEFAULT_STORE = store
