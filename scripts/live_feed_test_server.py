#!/usr/bin/env python3
"""Controlled CBIC-envelope JSON server for live-feed development and tests.

Usage:
  python scripts/live_feed_test_server.py
  python scripts/live_feed_test_server.py --scenario malformed
  python scripts/live_feed_test_server.py --port 8765

Env for TradeGraph:
  TRADE_LIVE_FEED_ENABLED=true
  TRADE_LIVE_TARIFF_HTTP_URL=http://127.0.0.1:8765/tariff_pack.json
  TRADE_HTTP_SOURCE_ALLOWLIST=localhost,127.0.0.1
"""

from __future__ import annotations

import argparse
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "config" / "trade" / "fixtures" / "cbic" / "cbic_notification_2026_q3.json"

SCENARIO = "valid"


def _load_valid() -> dict:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data["document_type"] = "tariff_pack"
    data["source_key"] = "live_tariff_http"
    return data


def _body_for(scenario: str) -> tuple[bytes, int, str]:
    if scenario == "404":
        return b'{"error":"not_found"}', 404, "application/json"
    if scenario == "500":
        return b'{"error":"upstream"}', 500, "application/json"
    if scenario == "timeout":
        time.sleep(30)
        return b"{}", 200, "application/json"
    if scenario == "oversized":
        return (b'{"rates":[]}' + (b"x" * (6 * 1024 * 1024))), 200, "application/json"
    if scenario == "bad_content_type":
        return b"<html>nope</html>", 200, "text/html"
    if scenario == "malformed":
        return b"{not-json", 200, "application/json"
    if scenario == "unchanged_whitespace":
        data = _load_valid()
        # Byte-different but semantically identical rates.
        raw = json.dumps(data, indent=4, ensure_ascii=False) + "\n\n"
        return raw.encode("utf-8"), 200, "application/json"
    if scenario == "rate_change":
        data = _load_valid()
        for rate in data.get("rates") or []:
            if rate.get("hs_code") == "6109.10" and rate.get("origin") == "BD":
                rate["rate"] = 12.0
                rate["duty_components"]["bcd_pct"] = 12.0
                rate["notes"] = "Live test rate change"
        return json.dumps(data).encode("utf-8"), 200, "application/json"
    # valid
    data = _load_valid()
    return json.dumps(data, indent=2).encode("utf-8"), 200, "application/json"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        print(f"[live-feed-test] {self.address_string()} {fmt % args}")

    def do_GET(self) -> None:  # noqa: N802
        global SCENARIO
        if self.path.startswith("/scenario/"):
            SCENARIO = self.path.split("/scenario/", 1)[1].strip("/") or "valid"
            body = json.dumps({"scenario": SCENARIO}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path.split("?")[0] not in {"/tariff_pack.json", "/"}:
            self.send_response(404)
            self.end_headers()
            return
        body, status, ctype = _body_for(SCENARIO)
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    global SCENARIO
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--scenario",
        default="valid",
        choices=[
            "valid",
            "rate_change",
            "unchanged_whitespace",
            "malformed",
            "404",
            "500",
            "timeout",
            "oversized",
            "bad_content_type",
        ],
    )
    args = parser.parse_args()
    SCENARIO = args.scenario
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(
        f"Live feed test server on http://{args.host}:{args.port}/tariff_pack.json "
        f"(scenario={SCENARIO})"
    )
    print("Switch scenario: GET /scenario/<name>")
    server.serve_forever()


if __name__ == "__main__":
    main()
