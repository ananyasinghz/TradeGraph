"""Phase A: gold set + PDF source paths exist."""

from __future__ import annotations

from pathlib import Path

from backend.app.services.hs_gold_service import load_hs_gold

ROOT = Path(__file__).resolve().parents[3]


def test_hs_gold_v1_loads_at_least_20() -> None:
    items = load_hs_gold()
    assert len(items) >= 20
    assert all(i["product_text"] and i["expected_hs"] for i in items)


def test_itc_pdf_sources_on_disk() -> None:
    assert (ROOT / "config/trade/source/ITC-HS_2022.pdf").is_file()
    assert (ROOT / "config/trade/source/HS_Code_Mappin.pdf").is_file()
