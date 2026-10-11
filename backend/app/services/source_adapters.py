"""Source adapters: curated mirrors, local archives, and hardened live HTTP fetch."""

from __future__ import annotations

import ipaddress
import socket
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx

from backend.app.core.errors import AppError

ROOT = Path(__file__).resolve().parents[3]

DEFAULT_CONNECT_TIMEOUT = 5.0
DEFAULT_READ_TIMEOUT = 20.0
DEFAULT_MAX_BYTES = 5 * 1024 * 1024
DEFAULT_MAX_RETRIES = 2
JSON_CONTENT_TYPES = frozenset(
    {
        "application/json",
        "text/json",
        "application/vnd.api+json",
    }
)
LIVE_ADAPTERS = frozenset({"http_get", "http", "live_http_api", "government_live_feed"})
OFFICIAL_DOCUMENT_ADAPTERS = frozenset({"official_document_http", "cbic_document_http", "icegate_document_http"})
DOCUMENT_CONTENT_TYPES = frozenset(
    {
        "application/pdf",
        "text/html",
        "application/xhtml+xml",
        "text/plain",
        *JSON_CONTENT_TYPES,
    }
)


@dataclass(frozen=True)
class FetchPayload:
    content: bytes
    content_type: str
    resolved_from: str
    final_url: str | None = None
    http_status: int | None = None
    retrieved_at_unix: float | None = None


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
                final_url=None,
                http_status=None,
                retrieved_at_unix=time.time(),
            )
        raise AppError(
            code="SOURCE_LOCAL_MISSING",
            message=f"Curated mirror file not found: {path}",
            status_code=404,
        )
    if source_url:
        return fetch_http_get(source_url=source_url, allow_localhost=True)
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
        retrieved_at_unix=time.time(),
    )


def resolve_payload(
    *,
    adapter: str,
    fetch_mode: str,
    local_path: str | None,
    source_url: str | None,
    allowlist: str | None = None,
    live_mode: bool = False,
) -> FetchPayload:
    mode = (fetch_mode or "").lower()
    name = (adapter or "").lower()
    if name in {"curated_json_mirror", "cbic_curated_mirror"} or mode == "curated_mirror":
        return fetch_curated_json_mirror(local_path=local_path, source_url=source_url)
    if name in {"local_archive", "local_pdf_archive"} or mode == "local_archive":
        return fetch_local_archive(local_path=local_path)
    if name in OFFICIAL_DOCUMENT_ADAPTERS or mode == "official_document":
        if not source_url:
            raise AppError(
                code="SOURCE_ADAPTER_MISCONFIGURED",
                message="official_document_http mode requires source_url",
                status_code=400,
            )
        return fetch_http_get(
            source_url=source_url,
            allowlist=allowlist,
            require_json=False,
            permitted_content_types=DOCUMENT_CONTENT_TYPES,
            allow_localhost=not live_mode or _url_is_loopback(source_url),
            require_https=live_mode and not _url_is_loopback(source_url),
        )
    if name in LIVE_ADAPTERS or mode == "http_get":
        if not source_url:
            raise AppError(
                code="SOURCE_ADAPTER_MISCONFIGURED",
                message="http_get / live_http_api mode requires source_url",
                status_code=400,
            )
        return fetch_http_get(
            source_url=source_url,
            allowlist=allowlist,
            require_json=live_mode or name in {"live_http_api", "government_live_feed"},
            allow_localhost=not live_mode or _url_is_loopback(source_url),
            require_https=live_mode and not _url_is_loopback(source_url),
        )
    raise AppError(
        code="SOURCE_ADAPTER_UNKNOWN",
        message=f"Unknown source adapter/mode: {adapter}/{fetch_mode}",
        status_code=400,
    )


def host_allowed(url: str, allowlist: str | None) -> bool:
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


def _url_is_loopback(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host in {"localhost", "127.0.0.1", "::1"}


def _is_private_or_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def validate_url_for_fetch(
    url: str,
    *,
    allowlist: str | None,
    allow_localhost: bool = False,
    require_https: bool = False,
) -> None:
    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()
    if scheme not in {"http", "https"}:
        raise AppError(
            code="SOURCE_HTTP_URL_INVALID",
            message=f"Unsupported URL scheme: {scheme or '(none)'}",
            status_code=400,
        )
    if require_https and scheme != "https" and not _url_is_loopback(url):
        raise AppError(
            code="SOURCE_HTTP_HTTPS_REQUIRED",
            message="Production live sources must use HTTPS",
            status_code=400,
        )
    if allowlist is not None and not host_allowed(url, allowlist):
        raise AppError(
            code="SOURCE_HTTP_HOST_NOT_ALLOWLISTED",
            message=f"Host not in TRADE_HTTP_SOURCE_ALLOWLIST: {url}",
            status_code=403,
        )
    host = (parsed.hostname or "").lower()
    if not host:
        raise AppError(
            code="SOURCE_HTTP_URL_INVALID",
            message="URL missing hostname",
            status_code=400,
        )
    if _url_is_loopback(url):
        if not allow_localhost:
            raise AppError(
                code="SOURCE_HTTP_SSRF_BLOCKED",
                message="Loopback hosts are only allowed for the local test server",
                status_code=403,
            )
        return
    try:
        infos = socket.getaddrinfo(host, parsed.port or (443 if scheme == "https" else 80))
    except socket.gaierror as exc:
        raise AppError(
            code="SOURCE_HTTP_DNS_FAILED",
            message=f"DNS resolution failed for {host}",
            status_code=502,
        ) from exc
    for info in infos:
        raw_ip = info[4][0]
        try:
            ip = ipaddress.ip_address(raw_ip)
        except ValueError:
            continue
        if _is_private_or_blocked_ip(ip):
            raise AppError(
                code="SOURCE_HTTP_SSRF_BLOCKED",
                message=f"Resolved address is not publicly routable: {ip}",
                status_code=403,
            )


def fetch_http_get(
    *,
    source_url: str,
    timeout_seconds: float | None = None,
    connect_timeout: float = DEFAULT_CONNECT_TIMEOUT,
    read_timeout: float = DEFAULT_READ_TIMEOUT,
    allowlist: str | None = None,
    max_bytes: int = DEFAULT_MAX_BYTES,
    max_retries: int = DEFAULT_MAX_RETRIES,
    require_json: bool = False,
    allow_localhost: bool = False,
    require_https: bool = False,
    permitted_content_types: frozenset[str] | None = None,
) -> FetchPayload:
    if timeout_seconds is not None:
        read_timeout = timeout_seconds
        connect_timeout = min(connect_timeout, timeout_seconds)

    validate_url_for_fetch(
        source_url,
        allowlist=allowlist,
        allow_localhost=allow_localhost,
        require_https=require_https,
    )

    timeout = httpx.Timeout(read_timeout, connect=connect_timeout)
    last_error: Exception | None = None
    attempts = max(1, max_retries + 1)

    for attempt in range(attempts):
        try:
            with httpx.Client(
                timeout=timeout,
                follow_redirects=False,
                headers={"User-Agent": "TradeGraph/0.1 (+source-fetch)"},
            ) as client:
                url = source_url
                for _redirect in range(5):
                    validate_url_for_fetch(
                        url,
                        allowlist=allowlist,
                        allow_localhost=allow_localhost,
                        require_https=require_https,
                    )
                    resp = client.get(url)
                    if resp.status_code in {301, 302, 303, 307, 308}:
                        loc = resp.headers.get("location")
                        if not loc:
                            raise AppError(
                                code="SOURCE_HTTP_REDIRECT_INVALID",
                                message="Redirect without Location header",
                                status_code=502,
                            )
                        url = str(httpx.URL(url).join(loc))
                        continue
                    break
                else:
                    raise AppError(
                        code="SOURCE_HTTP_REDIRECT_LOOP",
                        message="Too many redirects",
                        status_code=502,
                    )

                if resp.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"HTTP {resp.status_code}",
                        request=resp.request,
                        response=resp,
                    )
                if resp.status_code >= 400:
                    raise AppError(
                        code="SOURCE_HTTP_ERROR",
                        message=f"HTTP {resp.status_code} fetching {source_url}",
                        status_code=502,
                    )

                ctype = (resp.headers.get("content-type") or "application/octet-stream").split(";")[
                    0
                ].strip().lower()
                allowed = permitted_content_types or (
                    JSON_CONTENT_TYPES if require_json else None
                )
                if allowed is not None and ctype not in allowed:
                    raise AppError(
                        code="SOURCE_HTTP_CONTENT_TYPE",
                        message=f"Unsupported content type: {ctype}",
                        status_code=415,
                    )

                content_length = resp.headers.get("content-length")
                if content_length and content_length.isdigit() and int(content_length) > max_bytes:
                    raise AppError(
                        code="SOURCE_HTTP_RESPONSE_TOO_LARGE",
                        message=f"Response exceeds max size ({max_bytes} bytes)",
                        status_code=413,
                    )
                content = resp.content
                if len(content) > max_bytes:
                    raise AppError(
                        code="SOURCE_HTTP_RESPONSE_TOO_LARGE",
                        message=f"Response exceeds max size ({max_bytes} bytes)",
                        status_code=413,
                    )
                final_url = str(resp.url)
                return FetchPayload(
                    content=content,
                    content_type=ctype or "application/octet-stream",
                    resolved_from=source_url,
                    final_url=final_url,
                    http_status=resp.status_code,
                    retrieved_at_unix=time.time(),
                )
        except AppError:
            raise
        except httpx.TimeoutException as exc:
            last_error = exc
            if attempt + 1 >= attempts:
                raise AppError(
                    code="SOURCE_HTTP_TIMEOUT",
                    message=f"Timeout fetching {source_url}",
                    status_code=504,
                ) from exc
            time.sleep(0.25 * (2**attempt))
        except httpx.HTTPStatusError as exc:
            last_error = exc
            status = exc.response.status_code if exc.response is not None else 502
            if status >= 500 and attempt + 1 < attempts:
                time.sleep(0.25 * (2**attempt))
                continue
            raise AppError(
                code="SOURCE_HTTP_ERROR",
                message=f"HTTP {status} fetching {source_url}",
                status_code=502,
            ) from exc
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt + 1 >= attempts:
                raise AppError(
                    code="SOURCE_HTTP_ERROR",
                    message=f"Network error fetching {source_url}: {type(exc).__name__}",
                    status_code=502,
                ) from exc
            time.sleep(0.25 * (2**attempt))

    raise AppError(
        code="SOURCE_HTTP_ERROR",
        message=f"Network error fetching {source_url}: {last_error}",
        status_code=502,
    )
