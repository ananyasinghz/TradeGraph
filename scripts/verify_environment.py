"""Smoke-check that the TradeGraph Phase 0 package imports cleanly."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from backend.app.core.config import Settings
    from backend.app.main import create_app

    settings = Settings.model_validate({"environment": "test"})
    app = create_app(settings)
    paths = getattr(app.router, "routes", [])
    corridor = f"{settings.default_origin}->{settings.default_destination}"
    print(f"ok: {settings.app_name} routes={len(paths)} corridor={corridor}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
