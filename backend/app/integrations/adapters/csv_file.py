"""CSV file adapter."""

from __future__ import annotations

import csv
import io
from typing import Any

from backend.app.integrations.core.errors import AdapterError


def parse_csv_bytes(content: bytes) -> list[dict[str, Any]]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise AdapterError(f"CSV decode failed: {exc}", code="CSV_DECODE_ERROR") from exc
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise AdapterError("CSV has no header row", code="CSV_HEADER_MISSING")
    return [dict(row) for row in reader]
