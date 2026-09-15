"""Manual upload adapter — user-supplied official files."""

from __future__ import annotations

from pathlib import Path

from backend.app.integrations.adapters.http_json import read_local_bytes
from backend.app.integrations.core.errors import AdapterError

ROOT = Path(__file__).resolve().parents[4]


def load_upload(path: str | Path) -> bytes:
    """Load a manually uploaded archive from disk (under data/uploads or absolute)."""
    p = Path(path)
    if not p.is_absolute():
        candidates = [ROOT / p, ROOT / "data" / "uploads" / p]
        for candidate in candidates:
            if candidate.is_file():
                return read_local_bytes(candidate)
        raise AdapterError(f"Upload not found: {path}", code="UPLOAD_MISSING")
    return read_local_bytes(p)
