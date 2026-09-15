"""CLI: seed TradeGraph SQLite from config/trade/demo/seed_catalog.v1.yaml."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from backend.app.core.config import Settings, get_settings
    from backend.app.data.database import engine_from_settings, session_factory, session_scope
    from backend.app.data.models import Base
    from backend.app.data.seeding import load_catalog, seed

    parser = argparse.ArgumentParser(description="Seed TradeGraph Phase 1 demo data")
    parser.add_argument(
        "--catalog",
        type=Path,
        default=ROOT / "config" / "trade" / "demo" / "seed_catalog.v1.yaml",
    )
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--create-schema",
        action="store_true",
        help="Create tables via SQLAlchemy metadata",
    )
    args = parser.parse_args()

    Settings.model_validate({})
    settings = get_settings()
    engine = engine_from_settings(settings)
    if args.create_schema:
        Base.metadata.create_all(engine)

    catalog = load_catalog(args.catalog)
    factory = session_factory(engine)
    with session_scope(factory) as session:
        result = seed(session, catalog, force=args.force)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
