#!/usr/bin/env python3
"""Load HS nomenclature from PDF or pages JSONL into the trade DB."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.data.database import create_database_engine, session_factory, session_scope
from backend.app.services import hs_catalog_service


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-pdf", type=Path, action="append", dest="pdfs")
    parser.add_argument("--from-jsonl", type=Path, action="append", dest="jsonls")
    parser.add_argument(
        "--style",
        choices=["auto", "mapping", "itc"],
        default="auto",
    )
    parser.add_argument(
        "--default-pdfs",
        action="store_true",
        help="Load both config/trade/source PDFs",
    )
    args = parser.parse_args()
    pdfs = list(args.pdfs or [])
    jsonls = list(args.jsonls or [])
    if args.default_pdfs:
        pdfs.extend(
            [
                ROOT / "config/trade/source/HS_Code_Mappin.pdf",
                ROOT / "config/trade/source/ITC-HS_2022.pdf",
            ]
        )
    if not pdfs and not jsonls:
        pdfs = [ROOT / "config/trade/source/HS_Code_Mappin.pdf"]

    engine = create_database_engine()
    factory = session_factory(engine)
    totals = {"inserted": 0, "updated": 0, "synonyms_added": 0, "fts_rows": 0}
    with session_scope(factory) as session:
        for pdf in pdfs:
            style = "mapping" if "Mappin" in pdf.name or "Mapping" in pdf.name else args.style
            print(f"Loading PDF {pdf} style={style} ...")
            stats = hs_catalog_service.load_from_pdf(session, pdf, style=style)
            for k, v in stats.items():
                totals[k] = totals.get(k, 0) + int(v)
            print(stats)
        for jl in jsonls:
            print(f"Loading JSONL {jl} ...")
            stats = hs_catalog_service.load_from_jsonl_pages(
                session, jl, source_pack=jl.stem, style=args.style
            )
            for k, v in stats.items():
                totals[k] = totals.get(k, 0) + int(v)
            print(stats)
        from sqlalchemy import func, select

        from backend.app.data.models import HsCode

        count = int(session.scalar(select(func.count()).select_from(HsCode)) or 0)
        print(f"DONE totals={totals} hs_codes_count={count}")
        if count < 50:
            print("FAIL: expected hs_codes count >> 8", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
