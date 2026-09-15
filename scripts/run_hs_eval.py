#!/usr/bin/env python3
"""Run HS classification gold-set eval against the configured DB."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.data.database import create_database_engine, session_factory, session_scope
from backend.app.services.hs_eval_service import evaluate_hs_classify


def main() -> int:
    engine = create_database_engine()
    factory = session_factory(engine)
    with session_scope(factory) as session:
        report = evaluate_hs_classify(session)
    print(json.dumps(report, indent=2))
    return 1 if report.get("gate_failed") else 0


if __name__ == "__main__":
    raise SystemExit(main())
