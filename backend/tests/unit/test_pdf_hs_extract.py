"""PDF extract QA for HS nomenclature packs."""

from __future__ import annotations

import re
from pathlib import Path

from backend.app.integrations.adapters.pdf_document import extract_pdf_pages, extract_pdf_text

ROOT = Path(__file__).resolve().parents[3]
_HS = re.compile(r"\d{4}(?:[\s.]\d{2}){0,2}")


def test_mapping_pdf_extract_nonempty_with_hs_patterns() -> None:
    path = ROOT / "config/trade/source/HS_Code_Mappin.pdf"
    pages = extract_pdf_pages(path, max_pages=5)
    text = "\n".join(str(p.get("text") or "") for p in pages)
    assert len(text) > 100
    assert _HS.search(text)


def test_itc_pdf_sample_pages_extract() -> None:
    path = ROOT / "config/trade/source/ITC-HS_2022.pdf"
    pages = extract_pdf_pages(path, max_pages=15)
    nonempty = [p for p in pages if int(p.get("char_count") or 0) > 0]
    assert nonempty
    blob = "\n".join(str(p.get("text") or "") for p in nonempty)
    assert _HS.search(blob)


def test_extract_pdf_text_bytes() -> None:
    path = ROOT / "config/trade/source/HS_Code_Mappin.pdf"
    text = extract_pdf_text(path.read_bytes(), max_pages=2)
    assert "ITC-HS" in text or _HS.search(text)
