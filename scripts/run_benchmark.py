"""CLI: run TradeGraph Phase 3 orchestration benchmark."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from backend.app.core.config import get_settings
    from backend.app.data.database import engine_from_settings, session_factory, session_scope
    from backend.app.data.models import Base
    from backend.app.data.seeding import load_catalog, seed
    from backend.app.evaluation.benchmark import run_benchmark

    parser = argparse.ArgumentParser(description="Run TradeGraph orchestration benchmark")
    parser.add_argument(
        "--modes",
        nargs="+",
        default=["adaptive", "direct_lookup", "fixed_multi", "always_llm"],
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "data" / "evaluation" / "benchmark_results.v1.json",
    )
    parser.add_argument("--ensure-seed", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    engine = engine_from_settings(settings)
    if args.ensure_seed:
        Base.metadata.create_all(engine)
        catalog = load_catalog(ROOT / "config" / "trade" / "demo" / "seed_catalog.v1.yaml")
        factory = session_factory(engine)
        with session_scope(factory) as session:
            seed(session, catalog, force=True)

    factory = session_factory(engine)
    with session_scope(factory) as session:
        result = run_benchmark(session, modes=args.modes)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    print(json.dumps([s.model_dump() for s in result.summaries], indent=2))
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
