"""Prepare an isolated SQLite DB and print env for Playwright e2e."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare TradeGraph e2e database")
    parser.add_argument(
        "--db",
        type=Path,
        default=ROOT / "data" / "processed" / "e2e_trade.db",
    )
    args = parser.parse_args()

    db_path = args.db.resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    os.environ["TRADE_DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    os.environ["TRADE_AUTH_ENABLED"] = "false"
    os.environ["TRADE_ENVIRONMENT"] = "development"
    os.environ["TRADE_OLLAMA_ENABLED"] = "false"
    os.environ["TRADE_SOURCE_FETCH_SCHEDULER_ENABLED"] = "false"
    os.environ["TRADE_LIVE_FEED_ENABLED"] = "false"

    from backend.app.core.config import Settings
    from backend.app.data.database import engine_from_settings, session_factory
    from backend.app.data.models import Base
    from backend.app.data.seeding import load_catalog, seed
    from backend.app.services import hs_catalog_service
    from backend.app.services.corridor_service import ensure_default_corridors
    from backend.app.services.org_service import ensure_demo_org

    settings = Settings.model_validate(
        {
            "database_url": f"sqlite:///{db_path.as_posix()}",
            "auth_enabled": False,
            "environment": "development",
            "ollama_enabled": False,
            "source_fetch_scheduler_enabled": False,
            "live_feed_enabled": False,
        }
    )
    engine = engine_from_settings(settings)
    Base.metadata.create_all(engine)
    factory = session_factory(engine)
    catalog = load_catalog(ROOT / "config" / "trade" / "demo" / "seed_catalog.v1.yaml")
    with factory() as session:
        seed(session, catalog, force=True)
        ensure_default_corridors(session)
        ensure_demo_org(session)
        hs_catalog_service.load_min_fixture(session)
        session.commit()

    print(db_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
