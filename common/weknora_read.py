"""Read-only WeKnora calls. Same two operations T6's OpenCode MCP keeps enabled."""

from __future__ import annotations

import json
import os
import re
from typing import Any

import requests

_UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_DEFAULT_BASE = "https://knowledge.osisbim.com/api/v1"


def _client() -> tuple[str, dict[str, str]] | str:
    key = os.environ.get("WEKNORA_API_KEY", "").strip()
    if not key:
        return "TOOL_ERROR: WEKNORA_API_KEY is not set"
    base = os.environ.get("WEKNORA_BASE_URL", _DEFAULT_BASE).rstrip("/")
    return base, {
        "X-API-Key": key,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0",
    }


def _dump(payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False)
    if len(text) > 12000:
        return text[:12000] + "\n...[truncated]"
    return text


def list_knowledge_bases() -> str:
    """List WeKnora knowledge bases.

    Returns:
        JSON list of knowledge bases, or a TOOL_ERROR string.
    """

    client = _client()
    if isinstance(client, str):
        return client
    base, headers = client
    try:
        response = requests.get(f"{base}/knowledge-bases", headers=headers, timeout=60)
        response.raise_for_status()
        return _dump(response.json())
    except requests.RequestException as exc:
        return f"TOOL_ERROR: {type(exc).__name__}: {exc}"


def hybrid_search(kb_id: str, query: str, match_count: int = 5) -> str:
    """Hybrid-search one WeKnora knowledge base.

    Args:
        kb_id: Knowledge base UUID or name.
        query: Search text.
        match_count: Maximum number of hits to return.

    Returns:
        JSON search result, or a TOOL_ERROR string.
    """

    client = _client()
    if isinstance(client, str):
        return client
    base, headers = client
    try:
        resolved = kb_id.strip()
        if not _UUID.match(resolved):
            listing = requests.get(f"{base}/knowledge-bases", headers=headers, timeout=60)
            listing.raise_for_status()
            body = listing.json()
            rows = body.get("data", body) if isinstance(body, dict) else body
            if isinstance(rows, dict):
                rows = rows.get("list", rows.get("items", []))
            needle = resolved.casefold()
            resolved = ""
            for row in rows or []:
                if isinstance(row, dict) and str(row.get("name", "")).casefold() == needle:
                    resolved = str(row.get("id") or "")
                    break
            if not resolved:
                return f"TOOL_ERROR: knowledge base {kb_id!r} was not found"
        response = requests.post(
            f"{base}/knowledge-bases/{resolved}/hybrid-search",
            headers=headers,
            json={
                "query_text": query,
                "vector_threshold": 0.5,
                "keyword_threshold": 0.3,
                "match_count": max(1, min(int(match_count), 10)),
            },
            timeout=60,
        )
        response.raise_for_status()
        return _dump(response.json())
    except requests.RequestException as exc:
        return f"TOOL_ERROR: {type(exc).__name__}: {exc}"
