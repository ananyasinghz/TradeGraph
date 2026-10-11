"""ClamAV upload scan hook (stub; enabled via TRADE_UPLOAD_AV_ENABLED)."""

from __future__ import annotations

import logging

from backend.app.core.config import Settings
from backend.app.core.errors import AppError

logger = logging.getLogger(__name__)


def scan_upload(content: bytes, *, filename: str, settings: Settings) -> None:
    """Stub AV scan. When enabled, logs and accepts all non-empty payloads.

    A real deployment would stream bytes to clamd. This hook exists so upload
    paths can be wired without requiring ClamAV in local/test environments.
    """
    if not settings.upload_av_enabled:
        return
    if not content:
        raise AppError(
            code="AV_EMPTY_UPLOAD",
            message="Empty upload rejected by AV hook",
            status_code=400,
        )
    # EICAR test signature rejection when AV is enabled (safe demo signal).
    if b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE" in content:
        raise AppError(
            code="AV_REJECTED",
            message="Upload rejected by antivirus scan",
            status_code=422,
        )
    logger.info("av_scan_stub_ok filename=%s bytes=%s", filename, len(content))
