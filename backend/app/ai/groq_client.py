"""GroqCloud LLM wrapper used by the classification & summarization agents.

Exposes a single ``complete_json`` helper that asks the model for strict JSON
and parses it. When ``GROQ_API_KEY`` is not configured the helper returns
``None`` so callers can fall back to deterministic heuristics — this keeps the
whole pipeline runnable offline and in CI.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)

_JSON_BLOCK = re.compile(r"\{.*\}|\[.*\]", re.DOTALL)


@lru_cache(maxsize=1)
def _get_client():
    if not settings.groq_enabled:
        return None
    try:
        from groq import Groq

        return Groq(api_key=settings.GROQ_API_KEY)
    except Exception as exc:  # noqa: BLE001
        log.warning("groq_client_init_failed", error=str(exc))
        return None


def _extract_json(text: str) -> Any | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = _JSON_BLOCK.search(text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
    return None


def complete_json(
    system: str,
    user: str,
    *,
    temperature: float = 0.2,
    max_tokens: int = 1024,
) -> Any | None:
    """Run a chat completion expecting JSON output. Returns parsed JSON or None."""
    client = _get_client()
    if client is None:
        return None
    try:
        resp = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        content = resp.choices[0].message.content or ""
        return _extract_json(content)
    except Exception as exc:  # noqa: BLE001
        log.warning("groq_completion_failed", error=str(exc))
        return None


def complete_text(system: str, user: str, *, temperature: float = 0.3, max_tokens: int = 1024) -> str | None:
    client = _get_client()
    if client is None:
        return None
    try:
        resp = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content
    except Exception as exc:  # noqa: BLE001
        log.warning("groq_text_completion_failed", error=str(exc))
        return None
