"""Email backend interface (console print + optional SMTP)."""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from backend.app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


def send_email(
    *,
    to: str,
    subject: str,
    body: str,
    settings: Settings | None = None,
) -> None:
    resolved = settings or get_settings()
    if resolved.email_backend == "smtp" and resolved.smtp_host:
        _send_smtp(to=to, subject=subject, body=body, settings=resolved)
        return
    print(f"[email:console] to={to} subject={subject}\n{body}")
    logger.info("console_email to=%s subject=%s", to, subject)


def _send_smtp(*, to: str, subject: str, body: str, settings: Settings) -> None:
    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(settings.smtp_host or "localhost", settings.smtp_port) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_username and settings.smtp_password:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(msg)


def notify_slack(text: str, *, webhook_url: str | None = None, settings: Settings | None = None) -> bool:
    """Optional Slack webhook notify. Returns True if a webhook was attempted."""
    resolved = settings or get_settings()
    url = webhook_url or resolved.slack_webhook_url
    if not url:
        return False
    try:
        import httpx

        httpx.post(url, json={"text": text}, timeout=5.0)
        return True
    except Exception:  # noqa: BLE001 — best-effort notify
        logger.warning("slack_webhook_failed", exc_info=True)
        return False
