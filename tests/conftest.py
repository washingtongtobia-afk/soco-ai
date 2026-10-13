"""Global pytest configuration for SoCo test suite.

Guarantees that offline unit tests remain independent of live credentials
and never trigger unapproved paid model calls.
"""

import os
import pytest


@pytest.fixture(autouse=True)
def offline_guardrail_by_default(monkeypatch):
    """Enforce offline execution for standard unit and integration tests.

    Live model calls will only occur if explicitly requested via SOCO_RUN_LIVE_AI=1
    or when a test explicitly mocks/patches call_model and is_ai_available.
    """
    if not os.environ.get("SOCO_RUN_LIVE_AI"):
        monkeypatch.setattr("app.planning.ai_caption_engine.is_ai_available", lambda force_check=False: False)
