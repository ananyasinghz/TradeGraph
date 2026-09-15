"""HTML table adapter stub — field mappings drive extraction later."""

from __future__ import annotations

from backend.app.integrations.core.errors import AdapterError


def extract_html_tables(content: bytes) -> list[str]:
    text = content.decode("utf-8", errors="replace")
    if "<table" not in text.lower():
        raise AdapterError("No HTML tables found", code="HTML_TABLE_MISSING")
    return [text]
