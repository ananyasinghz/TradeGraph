"""HTTP XML adapter stub — parse when a real XML source is configured."""

from __future__ import annotations

from backend.app.integrations.core.errors import AdapterError


def parse_xml_bytes(content: bytes) -> str:
    if not content:
        raise AdapterError("Empty XML payload", code="XML_PARSE_ERROR")
    # Return text for downstream field mapping; full ElementTree parsing in IF-6+.
    return content.decode("utf-8", errors="replace")
