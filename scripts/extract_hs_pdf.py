#!/usr/bin/env python3
"""Extract text from HS nomenclature PDFs to data/processed/hs_nomenclature/."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.integrations.adapters.pdf_document import extract_pdf_pages

_HS_HINT = re.compile(r"\d{4}(?:[\s.]\d{2}){0,2}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pdf",
        action="append",
        dest="pdfs",
        help="PDF path (repeatable). Defaults to both local source PDFs.",
    )
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "data" / "processed" / "hs_nomenclature",
    )
    args = parser.parse_args()
    pdfs = [Path(p) for p in (args.pdfs or [])]
    if not pdfs:
        pdfs = [
            ROOT / "config/trade/source/ITC-HS_2022.pdf",
            ROOT / "config/trade/source/HS_Code_Mappin.pdf",
        ]
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for pdf in pdfs:
        if not pdf.is_file():
            print(f"MISSING {pdf}", file=sys.stderr)
            return 1
        pages = extract_pdf_pages(pdf, max_pages=args.max_pages)
        stem = pdf.stem.replace(" ", "_")
        out_jsonl = args.out_dir / f"{stem}.pages.jsonl"
        out_txt = args.out_dir / f"{stem}.txt"
        hs_hits = 0
        with out_jsonl.open("w", encoding="utf-8") as fh:
            for row in pages:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                hs_hits += len(_HS_HINT.findall(str(row.get("text") or "")))
        out_txt.write_text(
            "\n\n".join(str(r.get("text") or "") for r in pages),
            encoding="utf-8",
        )
        nonempty = sum(1 for r in pages if int(r.get("char_count") or 0) > 0)
        print(
            f"OK {pdf.name}: pages={len(pages)} nonempty={nonempty} "
            f"hs_pattern_hits~={hs_hits} -> {out_jsonl}"
        )
        if nonempty == 0:
            print(f"FAIL empty extract: {pdf}", file=sys.stderr)
            return 2
        if hs_hits == 0:
            print(f"WARN no HS digit patterns in {pdf.name}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
