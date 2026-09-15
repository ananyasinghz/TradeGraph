"""Generate IF-6 / IF-8 fixture corpora (run once during setup)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    codes = [
        ("6101.20", "Mens overcoats of cotton"),
        ("6102.20", "Womens overcoats of cotton"),
        ("6103.42", "Mens trousers of cotton"),
        ("6104.42", "Womens dresses of cotton"),
        ("6104.62", "Womens trousers of cotton"),
        ("6105.10", "Mens shirts of cotton"),
        ("6105.20", "Mens shirts of man-made fibres"),
        ("6106.10", "Womens blouses of cotton"),
        ("6106.20", "Womens blouses of man-made fibres"),
        ("6107.11", "Mens underpants of cotton"),
        ("6108.21", "Womens briefs of cotton"),
        ("6108.31", "Womens nightdresses of cotton"),
        ("6109.10", "T-shirts of cotton"),
        ("6109.90", "T-shirts of other textiles"),
        ("6110.20", "Jerseys of cotton"),
        ("6110.30", "Jerseys of man-made fibres"),
        ("6111.20", "Babies garments of cotton"),
        ("6112.11", "Track suits of cotton"),
        ("6114.20", "Other garments of cotton"),
        ("6115.95", "Stockings of cotton"),
        ("6116.10", "Gloves impregnated"),
        ("6117.10", "Shawls and scarves"),
        ("6103.32", "Mens jackets of cotton"),
        ("6103.33", "Mens jackets of synthetic"),
        ("6104.32", "Womens jackets of cotton"),
        ("6107.21", "Mens nightshirts of cotton"),
        ("6108.11", "Womens slips of man-made fibres"),
        ("6110.11", "Jerseys of wool"),
        ("6110.12", "Jerseys of Kashmir goats"),
        ("6112.12", "Track suits of synthetic"),
        ("6115.21", "Pantyhose of synthetic"),
        ("6115.96", "Stockings of synthetic"),
        ("6101.30", "Mens overcoats of man-made fibres"),
        ("6102.30", "Womens overcoats of man-made fibres"),
        ("6109.10", "T-shirts of cotton duplicate skip"),
    ]
    seen: set[str] = set()
    rates: list[dict] = []
    for i, (code, desc) in enumerate(codes):
        if code in seen:
            continue
        seen.add(code)
        bcd = 8.0 + (i % 7)
        rates.append(
            {
                "hs_code": code,
                "description": desc,
                "origin": "BD",
                "destination": "IN",
                "regime": "MFN",
                "rate": bcd,
                "rate_type": "ad_valorem_pct",
                "duty_components": {
                    "bcd_pct": bcd,
                    "sws_pct_of_bcd": 10.0,
                    "igst_pct": 5.0,
                },
                "effective_from": "2026-07-01",
                "source_page": 1 + (len(rates) // 10),
                "notes": f"IF-6 curated CBIC-style corpus row for {code}",
            }
        )
    for hs, pref in (("6109.10", 5.0), ("6105.10", 6.0), ("6110.20", 5.5)):
        rates.append(
            {
                "hs_code": hs,
                "description": "SAFTA preferential",
                "origin": "BD",
                "destination": "IN",
                "regime": "SAFTA",
                "rate": pref,
                "rate_type": "ad_valorem_pct",
                "duty_components": {
                    "bcd_pct": pref,
                    "sws_pct_of_bcd": 10.0,
                    "igst_pct": 5.0,
                },
                "effective_from": "2026-07-01",
                "source_page": 2,
                "notes": "Preferential SAFTA illustrative row",
            }
        )

    cbic = {
        "source_key": "in_cbic_ch61_corpus_v1",
        "title": "CBIC-style BD to IN chapter 61 curated corpus (IF-6)",
        "publisher": "CBIC (illustrative curated archive for TradeGraph)",
        "url": "https://example.invalid/tradegraph/archives/cbic-ch61-corpus-v1",
        "notice_id": "TG-CBIC-61-CORPUS-001",
        "effective_from": "2026-07-01",
        "retrieved_at": "2026-09-14T10:00:00+00:00",
        "disclaimer": (
            "Prototype corpus — not an official CBIC publication. "
            "30+ HS rows for BD to IN ch.61."
        ),
        "corridor": {"origin": "BD", "destination": "IN"},
        "rates": rates,
        "chunks": [
            {
                "id": "chunk_corpus_safta",
                "hs_code": "6109.10",
                "tags": ["safta", "bcd", "chapter61"],
                "text": (
                    "Illustrative corpus note: preferential SAFTA rates apply only when "
                    "certificate of origin and RoO conditions are satisfied for "
                    "Bangladesh-origin knit apparel under chapter 61."
                ),
            }
        ],
    }
    cbic_path = ROOT / "config/trade/fixtures/cbic/chapter61_bd_in_corpus.v1.json"
    cbic_path.write_text(json.dumps(cbic, indent=2), encoding="utf-8")
    test_cbic = ROOT / "tests/fixtures/integrations/cbic/chapter61_bd_in_corpus.v1.json"
    test_cbic.write_text(cbic_path.read_text(encoding="utf-8"), encoding="utf-8")

    # Companion PDF (simple) for adapter tests
    from backend.app.services.pdf_util import text_to_pdf

    pdf_bytes = text_to_pdf(
        "CBIC-style notification excerpt (prototype)",
        "HS 6109.10 BD to IN BCD 10 percent effective 2026-07-01. Not an official CBIC PDF.",
    )
    (ROOT / "config/trade/fixtures/cbic/sample_notification.pdf").write_bytes(pdf_bytes)
    (ROOT / "tests/fixtures/integrations/cbic/sample_notification.pdf").write_bytes(pdf_bytes)

    bd = {
        "source_key": "bd_customs_ch61_operative_v1",
        "title": "Bangladesh Customs operative tariff excerpt ch.61 (IF-8)",
        "publisher": "Bangladesh Customs / NBR (illustrative curated archive)",
        "url": "https://example.invalid/tradegraph/archives/bd-customs-ch61",
        "notice_id": "TG-BD-61-001",
        "effective_from": "2026-01-01",
        "disclaimer": "Prototype BD export-side tariff excerpt — Level 1/2 document ingest.",
        "corridor": {"origin": "BD", "destination": "IN"},
        "rates": [
            {
                "hs_code": "6109.10",
                "origin": "BD",
                "destination": "IN",
                "rate": 0.0,
                "rate_type": "ad_valorem_pct",
                "duty_components": {"cd_pct": 0.0, "rd_pct": 0.0, "vat_pct": 0.0},
                "regime": "EXPORT_REF",
                "effective_from": "2026-01-01",
                "notes": "Export reference row (illustrative)",
            },
            {
                "hs_code": "6105.10",
                "origin": "BD",
                "destination": "IN",
                "rate": 0.0,
                "rate_type": "ad_valorem_pct",
                "duty_components": {"cd_pct": 0.0},
                "regime": "EXPORT_REF",
                "effective_from": "2026-01-01",
                "notes": "Export reference",
            },
        ],
        "chunks": [
            {
                "id": "chunk_bd_sro",
                "hs_code": "6109.10",
                "tags": ["sro", "bd"],
                "text": (
                    "Illustrative Bangladesh SRO reference for knit apparel chapter 61 "
                    "used in TradeGraph Level-1 document ingest demos."
                ),
            }
        ],
    }
    bd_path = ROOT / "config/trade/fixtures/bd_customs/chapter61_operative_v1.json"
    bd_path.write_text(json.dumps(bd, indent=2), encoding="utf-8")
    (
        ROOT / "tests/fixtures/integrations/bd_customs/chapter61_operative_v1.json"
    ).write_text(bd_path.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"CBIC rates={len(rates)} written to {cbic_path}")
    print(f"BD fixture written to {bd_path}")


if __name__ == "__main__":
    main()
