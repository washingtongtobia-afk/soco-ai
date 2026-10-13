"""Structure and contract for future monthly caption PDF export.

Day 4A Scope: Prepare data contract and interface; full PDF rendering is
scheduled for future phase.
"""

from __future__ import annotations

import abc
from pydantic import BaseModel, Field

from app.models.caption import MonthlyPlan
from app.models.profile import BusinessProfile


class ExportPdfRequest(BaseModel):
    """Payload specifying options for monthly caption PDF export."""
    business_profile: BusinessProfile
    monthly_plan: MonthlyPlan
    include_draft_notes: bool = True
    include_hashtags: bool = True
    title: str = Field(default="Monthly Social Media Calendar")


class BasePdfExporter(abc.ABC):
    """Abstract interface for monthly captions PDF exporter."""

    @abc.abstractmethod
    def export(self, request: ExportPdfRequest) -> bytes:
        """Render monthly plan to PDF bytes."""
        raise NotImplementedError


class StubPdfExporter(BasePdfExporter):
    """Placeholder PDF exporter preparing architecture for future rendering library."""

    def export(self, request: ExportPdfRequest) -> bytes:
        raise NotImplementedError(
            "PDF export structure is defined. Full rendering engine will be implemented in a future phase."
        )


def get_pdf_exporter() -> BasePdfExporter:
    """Return configured PDF exporter."""
    return StubPdfExporter()
