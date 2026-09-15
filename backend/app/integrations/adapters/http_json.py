"""HTTP JSON / local JSON adapter."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from backend.app.integrations.core.errors import AdapterError, FetchError

ROOT = Path(__file__).resolve().parents[4]


def read_local_bytes(path: str | Path) -> bytes:
    p = Path(path)
    if not p.is_absolute():
        p = ROOT / p
    if not p.is_file():
        raise AdapterError(f"Local file not found: {p}", code="SOURCE_LOCAL_MISSING")
    return p.read_bytes()


def parse_json_bytes(content: bytes) -> dict[str, Any] | list[Any]:
    try:
        return json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AdapterError(f"Invalid JSON payload: {exc}", code="JSON_PARSE_ERROR") from exc


def http_get_bytes(url: str, *, timeout_seconds: float = 15.0) -> tuple[bytes, str]:
    try:
        with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
            resp = client.get(
                url,
                headers={"User-Agent": "TradeGraph/0.1 (+integration adapter)"},
            )
            resp.raise_for_status()
            ctype = resp.headers.get("content-type", "application/octet-stream").split(";")[0]
            return resp.content, ctype or "application/octet-stream"
    except httpx.HTTPStatusError as exc:
        raise FetchError(
            f"HTTP {exc.response.status_code} fetching {url}",
            code="SOURCE_HTTP_ERROR",
        ) from exc
    except httpx.HTTPError as exc:
        raise FetchError(f"Network error fetching {url}: {exc}", code="SOURCE_HTTP_ERROR") from exc
