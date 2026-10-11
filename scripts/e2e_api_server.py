"""Prepare e2e DB then start uvicorn (cross-platform Playwright webServer entry)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    prepare = ROOT / "scripts" / "e2e_prepare.py"
    rc = subprocess.call([sys.executable, str(prepare)], cwd=str(ROOT))
    if rc != 0:
        return rc

    db_path = (ROOT / "data" / "processed" / "e2e_trade.db").resolve()
    env = os.environ.copy()
    env["TRADE_DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    env["TRADE_AUTH_ENABLED"] = "false"
    env["TRADE_ENVIRONMENT"] = "development"
    env["TRADE_OLLAMA_ENABLED"] = "false"
    env["TRADE_SOURCE_FETCH_SCHEDULER_ENABLED"] = "false"
    env["TRADE_LIVE_FEED_ENABLED"] = "false"

    return subprocess.call(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ],
        cwd=str(ROOT),
        env=env,
    )


if __name__ == "__main__":
    raise SystemExit(main())
