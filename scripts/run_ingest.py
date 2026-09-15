"""CLI: run archive ingest (pending review) or approve latest pending batch."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from backend.app.core.config import get_settings
    from backend.app.data.database import engine_from_settings, session_factory, session_scope
    from backend.app.domain.trade import IngestRunRequest
    from backend.app.services import ingestion_service

    parser = argparse.ArgumentParser(description="TradeGraph Phase 4 ingestion")
    parser.add_argument("--source-key", default="cbic_notification_2026_q3")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--approve", metavar="BATCH_ID", help="Approve a pending batch")
    parser.add_argument("--reject", metavar="BATCH_ID", help="Reject a pending batch")
    parser.add_argument("--notes", default=None)
    args = parser.parse_args()

    settings = get_settings()
    engine = engine_from_settings(settings)
    factory = session_factory(engine)

    with session_scope(factory) as session:
        if args.approve:
            result = ingestion_service.approve_batch(session, args.approve, notes=args.notes)
        elif args.reject:
            result = ingestion_service.reject_batch(session, args.reject, notes=args.notes)
        else:
            result = ingestion_service.run_ingest(
                session,
                IngestRunRequest(source_key=args.source_key, force=args.force),
            )
        print(result.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
