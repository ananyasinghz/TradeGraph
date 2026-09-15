"""Phase C adapters: resolve bytes from curated mirrors / local archives / HTTP."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import httpx

from backend.app.core.errors import AppError

ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class FetchPayload:
    content: bytes
    content_type: str
    resolved_from: str


def _resolve_path(local_path: str) -> Path:
    path = Path(local_path)
    if not path.is_absolute():
        path = ROOT / path
    return path


def fetch_curated_json_mirror(*, local_path: str | None, source_url: str | None) -> FetchPayload:
    """
    BD→IN ch.61 curated mirror adapter.

    Prefer local archived JSON under config/trade/fixtures. Optional HTTP is allowed
    for demos but must not be presented as a live government API.
    """
    if local_path:
        path = _resolve_path(local_path)
        if path.is_file():
            try:
                rel = str(path.relative_to(ROOT)).replace("\\", "/")
            except ValueError:
                rel = str(path).replace("\\", "/")
            return FetchPayload(
                content=path.read_bytes(),
                content_type="application/json",
                resolved_from=rel,
            )
        raise AppError(
            code="SOURCE_LOCAL_MISSING",
            message=f"Curated mirror file not found: {path}",
            status_code=404,
        )
    if source_url:
        return fetch_http_get(source_url=source_url)
    raise AppError(
        code="SOURCE_ADAPTER_MISCONFIGURED",
        message="Curated mirror requires local_path or source_url",
        status_code=400,
    )


def fetch_local_archive(*, local_path: str | None) -> FetchPayload:
    if not local_path:
        raise AppError(
            code="SOURCE_ADAPTER_MISCONFIGURED",
            message="local_archive mode requires local_path",
            status_code=400,
        )
    path = _resolve_path(local_path)
    if not path.is_file():
        raise AppError(
            code="SOURCE_LOCAL_MISSING",
            message=f"Local archive not found: {path}",
            status_code=404,
        )
    suffix = path.suffix.lower()
    ctype = "application/json" if suffix == ".json" else "application/octet-stream"
    try:
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        rel = str(path).replace("\\", "/")
    return FetchPayload(
        content=path.read_bytes(),
        content_type=ctype,
        resolved_from=rel,
    )


def resolve_payload(
    *,
    adapter: str,
    fetch_mode: str,
    local_path: str | None,
    source_url: str | None,
    allowlist: str | None = None,
) -> FetchPayload:
    mode = (fetch_mode or "").lower()
    name = (adapter or "").lower()
    if name in {"curated_json_mirror", "cbic_curated_mirror"} or mode == "curated_mirror":
        return fetch_curated_json_mirror(local_path=local_path, source_url=source_url)
    if name in {"local_archive", "local_pdf_archive"} or mode == "local_archive":
        return fetch_local_archive(local_path=local_path)
    if name in {"http_get", "http", "live_http_api", "government_live_feed"} or mode == "http_get":
        if not source_url:
            raise AppError(
                code="SOURCE_ADAPTER_MISCONFIGURED",
                message="http_get / live_http_api mode requires source_url",
                status_code=400,
            )
        return fetch_http_get(source_url=source_url, allowlist=allowlist)
    raise AppError(
        code="SOURCE_ADAPTER_UNKNOWN",
        message=f"Unknown source adapter/mode: {adapter}/{fetch_mode}",
        status_code=400,
    )


def host_allowed(url: str, allowlist: str | None) -> bool:
    from urllib.parse import urlparse

    raw = (allowlist or "").strip()
    if not raw:
        return False
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return False
    suffixes = [s.strip().lower() for s in raw.split(",") if s.strip()]
    for suffix in suffixes:
        if host == suffix or host.endswith("." + suffix):
            return True
    return False


def fetch_http_get(
    *,
    source_url: str,
    timeout_seconds: float = 15.0,
    allowlist: str | None = None,
) -> FetchPayload:
    if allowlist is not None and not host_allowed(source_url, allowlist):
        raise AppError(
            code="SOURCE_HTTP_HOST_NOT_ALLOWLISTED",
            message=f"Host not in TRADE_HTTP_SOURCE_ALLOWLIST: {source_url}",
            status_code=403,
        )
    try:
        with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
            resp = client.get(
                source_url,
                headers={"User-Agent": "TradeGraph/0.1 (+local research prototype)"},
            )
            resp.raise_for_status()
            ctype = resp.headers.get("content-type", "application/octet-stream").split(";")[0]
            return FetchPayload(
                content=resp.content,
                content_type=ctype or "application/octet-stream",
                resolved_from=source_url,
            )
    except httpx.HTTPStatusError as exc:
        raise AppError(
            code="SOURCE_HTTP_ERROR",
            message=f"HTTP {exc.response.status_code} fetching {source_url}",
            status_code=502,
        ) from exc
    except httpx.HTTPError as exc:
        raise AppError(
            code="SOURCE_HTTP_ERROR",
            message=f"Network error fetching {source_url}: {exc}",
            status_code=502,
        ) from exc
