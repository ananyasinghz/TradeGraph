"""Promote CBIC curated fixture to verified published rates (IF-11b).

Usage (from repo root, venv active):

    python scripts/demo_promote_cbic.py

Then refresh the UI — banner should show approved rules and Verified source.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from backend.app.core.config import get_settings
    from backend.app.data.database import engine_from_settings, session_factory, session_scope
    from backend.app.services import promote_service, system_status_service

    settings = get_settings()
    engine = engine_from_settings(settings)
    factory = session_factory(engine)
    with session_scope(factory) as session:
        result = promote_service.promote_cbic_fixture(session)
        status = system_status_service.build_system_status(session, settings)
    print(result.message)
    print(f"batch_id={result.batch_id}")
    print(f"rates_published={result.rates_published}")
    print(f"approved_tariff_rule_count={result.approved_tariff_rule_count}")
    print(f"source_connection_kind={status.source_connection_kind}")
    print(f"source_connection_label={status.source_connection_label}")
    print(f"last_approved={status.last_approved_label} @ {status.last_approved_at}")
    print(f"customs_mode_hint={status.customs_mode_hint}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
