"""Reset local SQLite demo DB: migrate → seed → optional ingest.

Stop uvicorn (or any process locking trade.db) before running.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset TradeGraph demo SQLite DB")
    parser.add_argument(
        "--db",
        type=Path,
        default=ROOT / "data" / "processed" / "trade.db",
        help="SQLite file to delete",
    )
    parser.add_argument(
        "--ingest",
        action="store_true",
        help="Run CBIC Q3 ingest after seed (still needs approve for Last approved)",
    )
    parser.add_argument(
        "--fetch",
        action="store_true",
        help="Fetch default source connection after seed",
    )
    args = parser.parse_args()

    db_path = args.db.resolve()
    if db_path.exists():
        try:
            db_path.unlink()
            print(f"Deleted {db_path}")
        except OSError as exc:
            print(
                f"Could not delete {db_path}: {exc}\n"
                "Stop uvicorn / other processes locking the file, then retry.",
                file=sys.stderr,
            )
            return 1
    else:
        print(f"No existing DB at {db_path}")

    for label, cmd in [
        ("alembic upgrade head", [sys.executable, "-m", "alembic", "upgrade", "head"]),
        (
            "seed",
            [sys.executable, str(ROOT / "scripts" / "seed_trade_data.py"), "--force"],
        ),
    ]:
        print(f"-> {label}")
        completed = subprocess.run(cmd, cwd=ROOT, check=False)
        if completed.returncode != 0:
            return completed.returncode

    if args.fetch or args.ingest:
        from backend.app.core.config import get_settings
        from backend.app.data.database import engine_from_settings, session_factory, session_scope
        from backend.app.services import source_connection_service

        settings = get_settings()
        factory = session_factory(engine_from_settings(settings))
        with session_scope(factory) as session:
            source_connection_service.ensure_default_connections(session)
            if args.fetch:
                result = source_connection_service.fetch_connection(
                    session,
                    "cbic_notification_2026_q3",
                    run_ingest=args.ingest,
                )
                print(json.dumps(result.model_dump(mode="json"), indent=2))
            elif args.ingest:
                from backend.app.domain.trade import IngestRunRequest
                from backend.app.services import ingestion_service

                batch = ingestion_service.run_ingest(
                    session,
                    IngestRunRequest(
                        source_key="cbic_notification_2026_q3",
                        archive_path="config/trade/fixtures/cbic/cbic_notification_2026_q3.json",
                        force=True,
                    ),
                )
                print(json.dumps({"ingest_batch_id": batch.id, "status": batch.status}, indent=2))

    print(
        "Done. Until you approve an ingest batch, system status "
        "'Last approved source update' stays None."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
