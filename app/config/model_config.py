"""Centralized model configuration for SoCo Agent.

Configures the primary and fallback LLM models across the entire application,
including the Google ADK workflow graph and caption generation engine.
"""

from __future__ import annotations

import os

# Primary model for SoCo conversational social media strategist
# Verified: Generally Available in us-east1 and designated default for Agent Platform
SOCO_PRIMARY_MODEL: str = os.getenv("SOCO_PRIMARY_MODEL", "gemini-3.8-flash")

# Fallback / alternate model if specified
SOCO_FALLBACK_MODEL: str = os.getenv("SOCO_FALLBACK_MODEL", "gemini-3.5-flash")
