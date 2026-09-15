"""PDF document adapter — pypdf for real PDFs; legacy Tj fallback for simple PDFs."""

from __future__ import annotations

import re
from pathlib import Path

from backend.app.integrations.core.errors import AdapterError

_TJ = re.compile(r"\((?:\\.|[^\\)])*\)\s*Tj")


def extract_pdf_text_legacy_tj(content: bytes) -> str:
    """Support TradeGraph's minimal pdf_util writer (literal strings + Tj operators)."""
    if not content.startswith(b"%PDF"):
        raise AdapterError("Not a PDF document", code="PDF_INVALID")
    try:
        decoded = content.decode("latin-1", errors="replace")
    except Exception as exc:  # pragma: no cover
        raise AdapterError(f"PDF decode failed: {exc}", code="PDF_DECODE_ERROR") from exc
    parts: list[str] = []
    for match in _TJ.finditer(decoded):
        raw = match.group(0)
        inner = raw[1 : raw.rfind(")")]
        inner = inner.replace("\\(", "(").replace("\\)", ")").replace("\\\\", "\\")
        parts.append(inner)
    text = "\n".join(parts).strip()
    if not text:
        raise AdapterError(
            "No extractable text operators in PDF — use manual upload review",
            code="PDF_EXTRACT_EMPTY",
        )
    return text


def extract_pdf_text_pypdf(
    content: bytes,
    *,
    max_pages: int | None = None,
) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise AdapterError("pypdf is not installed", code="PDF_DEPENDENCY_MISSING") from exc
    if not content.startswith(b"%PDF"):
        raise AdapterError("Not a PDF document", code="PDF_INVALID")
    import io

    try:
        reader = PdfReader(io.BytesIO(content))
    except Exception as exc:
        raise AdapterError(f"PDF open failed: {exc}", code="PDF_OPEN_ERROR") from exc
    chunks: list[str] = []
    pages = reader.pages
    limit = len(pages) if max_pages is None else min(len(pages), max_pages)
    for i in range(limit):
        try:
            page_text = pages[i].extract_text() or ""
        except Exception:
            page_text = ""
        if page_text.strip():
            chunks.append(page_text)
    text = "\n".join(chunks).strip()
    if not text:
        raise AdapterError(
            "No extractable text via pypdf — PDF may be scanned; OCR not enabled",
            code="PDF_EXTRACT_EMPTY",
        )
    return text


def extract_pdf_text(content: bytes, *, max_pages: int | None = None) -> str:
    """Prefer pypdf; fall back to legacy Tj extraction for simple generated PDFs."""
    try:
        return extract_pdf_text_pypdf(content, max_pages=max_pages)
    except AdapterError as exc:
        if exc.code == "PDF_EXTRACT_EMPTY":
            return extract_pdf_text_legacy_tj(content)
        raise


def extract_pdf_pages(
    path: Path | str,
    *,
    max_pages: int | None = None,
) -> list[dict[str, object]]:
    """Return per-page text dicts for inspectability / JSONL dumps."""
    from pypdf import PdfReader

    p = Path(path)
    reader = PdfReader(str(p))
    out: list[dict[str, object]] = []
    limit = len(reader.pages) if max_pages is None else min(len(reader.pages), max_pages)
    for i in range(limit):
        try:
            text = reader.pages[i].extract_text() or ""
        except Exception:
            text = ""
        out.append({"page": i + 1, "text": text, "char_count": len(text)})
    return out
