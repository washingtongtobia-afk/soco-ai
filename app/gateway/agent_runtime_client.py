"""Client for querying the deployed Vertex AI Reasoning Engine on Agent Runtime."""

from __future__ import annotations

import json
import logging
import os
import subprocess
from collections.abc import AsyncGenerator
from typing import Any

import httpx
from google.adk.events import Event
from google.genai import types

logger = logging.getLogger(__name__)

DEFAULT_ENGINE_RESOURCE = os.environ.get("REASONING_ENGINE_RESOURCE_ID", "")
STREAM_QUERY_URL = os.environ.get(
    "REASONING_ENGINE_STREAM_URL",
    f"https://us-east1-aiplatform.googleapis.com/v1beta1/{DEFAULT_ENGINE_RESOURCE}:streamQuery" if DEFAULT_ENGINE_RESOURCE else "",
)


def _get_auth_token() -> str | None:
    """Obtain Google Cloud access token via environment or gcloud."""
    token = os.getenv("GOOGLE_OAUTH_ACCESS_TOKEN")
    if token:
        return token
    try:
        token = subprocess.check_output(["gcloud", "auth", "print-access-token"], text=True).strip()
        return token
    except Exception as exc:
        logger.warning("Unable to retrieve gcloud access token: %s", exc)
        return None


async def stream_deployed_reasoning_engine(
    text: str,
    business_id: str,
    year: int | None = None,
    month: int | None = None,
    month_name: str | None = None,
) -> AsyncGenerator[Event, None]:
    """Stream events from the live deployed Vertex AI Reasoning Engine."""
    token = _get_auth_token()
    if not token:
        raise RuntimeError("No Google Cloud access token available for deployed Reasoning Engine.")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "classMethod": "async_stream_query",
        "input": {
            "user_id": business_id,
            "message": text,
            "business_id": business_id,
            "year": year,
            "month": month,
            "month_name": month_name,
        },
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream("POST", STREAM_QUERY_URL, headers=headers, json=payload) as resp:
            if resp.status_code != 200:
                body = await resp.aread()
                raise RuntimeError(f"Reasoning Engine error ({resp.status_code}): {body.decode('utf-8', errors='replace')}")

            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    content = None
                    if "content" in data and "parts" in data["content"]:
                        parts = []
                        for p in data["content"]["parts"]:
                            if "text" in p:
                                parts.append(types.Part.from_text(text=p["text"]))
                        if parts:
                            content = types.Content(role=data["content"].get("role", "model"), parts=parts)
                    output = data.get("output")
                    yield Event(content=content, output=output)
                except Exception as exc:
                    logger.warning("Error parsing stream chunk: %s", exc)
