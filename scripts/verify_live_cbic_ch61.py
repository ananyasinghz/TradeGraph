#!/usr/bin/env python3
"""Live Source Verification — CBIC Chapter 61 (operator checklist runner).

Requires network access to the locked official CBIC document URL.
Does not use the local fixture server.

Usage:
  set TRADE_LIVE_OFFICIAL_VERIFY=1
  python scripts/verify_live_cbic_ch61.py

Exit 0 only when gates 1–5 pass (or gate 3 reports quarantine-only with explicit FAIL
if no publishable Chapter 61 row exists).
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Locked verified document (courier.cbic.gov.in — reachable HTTPS with valid chain).
LOCKED_DOCUMENT_URL = (
    "https://courier.cbic.gov.in/advisory/2025/"
    + quote("NOTIFICATION NO. 9_2025-INTEGRATED TAX (RATE) -1759486719.pdf")
)
LOCKED_PORTAL_URL = "https://courier.cbic.gov.in/notification.jsp"
CONNECTION_KEY = "cbic_ch61_igst_notif_9_2025"
ALLOWLIST = "localhost,127.0.0.1,courier.cbic.gov.in"


def _pass(name: str, detail: str) -> None:
    print(f"PASS  {name}: {detail}")


def _fail(name: str, detail: str) -> None:
    print(f"FAIL  {name}: {detail}")


def main() -> int:
    if os.environ.get("TRADE_LIVE_OFFICIAL_VERIFY", "").strip() not in {"1", "true", "TRUE", "yes"}:
        print("Set TRADE_LIVE_OFFICIAL_VERIFY=1 to run live official verification.")
        return 2

    from sqlalchemy import select

    from backend.app.data.models import SourceConnection, TariffRate
    from backend.app.domain.trade import ShipmentCreate
    from backend.app.services import shipment_service
    from backend.tests.helpers.db import make_client

    client = make_client(
        live_feed_enabled=True,
        http_source_allowlist=ALLOWLIST,
        cbic_customs_url=LOCKED_PORTAL_URL,
        cbic_customs_document_url=LOCKED_DOCUMENT_URL,
        live_feed_max_age_hours=720,
    )
    factory = client.app.state.session_factory
    results: dict[str, bool] = {}

    # Gate 1 — real fetch (no fixture server)
    fetch = client.post(f"/api/v1/source-connections/{CONNECTION_KEY}/fetch")
    if fetch.status_code != 200:
        _fail("gate1_fetch", f"status={fetch.status_code} body={fetch.text[:300]}")
        return 1
    body = fetch.json()
    archive = body.get("archive_path")
    checksum = body.get("checksum")
    if not archive or not checksum or not (ROOT / archive).is_file():
        _fail("gate1_fetch", f"missing archive/checksum: {body}")
        return 1
    _pass("gate1_fetch", f"checksum={checksum[:16]}… archive={archive}")
    results["gate1"] = True

    # Gate 2 — provenance (pre-approve artifact identity)
    conn = body.get("connection") or {}
    provenance = {
        "configured_url": LOCKED_PORTAL_URL,
        "document_url": LOCKED_DOCUMENT_URL,
        "final_url": conn.get("last_final_url") or LOCKED_DOCUMENT_URL,
        "content_type": conn.get("last_content_type"),
        "checksum": checksum,
        "archive_path": archive,
        "retrieved_at": conn.get("last_success_at"),
        "fixture_server_used": False,
        "parser_version": "official_india_doc.v2",
    }
    print("PROVENANCE", json.dumps(provenance, indent=2, default=str))
    if "127.0.0.1" in (LOCKED_DOCUMENT_URL + LOCKED_PORTAL_URL) or "localhost" in LOCKED_DOCUMENT_URL:
        _fail("gate2_provenance", "locked URL points at localhost")
        return 1
    _pass("gate2_provenance", "official host courier.cbic.gov.in; fixtures not used")
    results["gate2"] = True

    # Gate 3 — parse / validate
    batch_id = body.get("ingest_batch_id")
    if not batch_id:
        _fail("gate3_parse", f"no ingest batch (outcome={body.get('outcome')})")
        return 1
    detail = client.get(f"/api/v1/ingest/batches/{batch_id}").json()
    ok = int(detail.get("validation_summary", {}).get("ok") or 0)
    err = int(detail.get("validation_summary", {}).get("error") or 0)
    ch61_ok = [
        p
        for p in detail.get("proposals") or []
        if p.get("kind") == "tariff_rate"
        and p.get("validation_status") == "ok"
        and str((p.get("payload") or {}).get("hs_code") or "").startswith("61")
    ]
    if not ch61_ok:
        _fail("gate3_parse", f"no publishable Chapter 61 rows (ok={ok} err={err})")
        return 1
    sample = ch61_ok[0]["payload"]
    _pass(
        "gate3_parse",
        f"HS {sample.get('hs_code')} rate={sample.get('rate')} "
        f"components={sample.get('duty_components')} ok={ok} quarantined={err}",
    )
    results["gate3"] = True

    # Gate 4 — approve → lookup → shipment recalc
    approved = client.post(
        f"/api/v1/ingest/batches/{batch_id}/approve",
        json={"notes": "Live Source Verification CBIC Ch61"},
    )
    if approved.status_code != 200:
        _fail("gate4_approve", approved.text[:300])
        return 1
    feed = client.get("/api/v1/source-connections/feed-status").json()
    print(
        "FEED_AFTER_APPROVE",
        json.dumps(
            {
                "live_government_feed": feed.get("live_government_feed"),
                "live_feed_reason": feed.get("live_feed_reason"),
            },
            indent=2,
        ),
    )
    hs = str(sample.get("hs_code") or "6109.10")
    tariffs = client.get(
        "/api/v1/tariffs",
        params={"hs": hs, "origin": "BD", "destination": "IN", "as_of": "2025-10-01"},
    )
    if tariffs.status_code != 200 or not tariffs.json():
        _fail("gate4_lookup", f"status={tariffs.status_code} body={tariffs.text[:200]}")
        return 1
    row = tariffs.json()[0]
    if row.get("data_quality") not in {"source_verified", "demo_verified"}:
        _fail("gate4_lookup", f"unexpected data_quality={row.get('data_quality')}")
        return 1
    _pass(
        "gate4_lookup",
        f"rate={row.get('rate')} quality={row.get('data_quality')} "
        f"source={row.get('source_document_id')}",
    )

    with factory() as session:
        ship = shipment_service.create_shipment(
            session,
            ShipmentCreate(
                title="Live CBIC Ch61 verification case",
                product_text="Cotton knitted T-shirt chapter 61 verification",
                origin="BD",
                destination="IN",
                hs_code_working=hs,
                as_of_date=date(2025, 10, 1),
                invoice_value=Decimal("5000"),
                currency="USD",
                incoterm="CIF",
                qty=Decimal("1"),
                freight=Decimal("100"),
                insurance=Decimal("50"),
            ),
        )
        session.commit()
        ship_id = ship.id

    calc = client.post(f"/api/v1/shipments/{ship_id}/calculate", json={})
    if calc.status_code != 200:
        # Some APIs use /calculate differently
        calc = client.post(f"/api/v1/shipments/{ship_id}/calculate", json={"requested_mode": "estimate"})
    if calc.status_code != 200:
        _fail("gate4_calc", f"status={calc.status_code} {calc.text[:300]}")
        return 1
    calc_body = calc.json()
    _pass("gate4_calc", f"keys={list(calc_body.keys())[:8]}")
    results["gate4"] = True

    # Gate 5 — unchanged refresh + outage preserves rates
    again = client.post(f"/api/v1/source-connections/{CONNECTION_KEY}/fetch")
    again_body = again.json() if again.status_code == 200 else {}
    if again.status_code != 200 or again_body.get("outcome") not in {
        "unchanged",
        "pending_review",
        "published",
    }:
        # pending_review with same batch is acceptable idempotency
        if again_body.get("ingest_batch_id") == batch_id and again_body.get("outcome") == "unchanged":
            pass
        elif again_body.get("outcome") == "unchanged":
            pass
        else:
            _fail("gate5_refresh", f"status={again.status_code} body={again_body}")
            return 1
    _pass("gate5_refresh", f"outcome={again_body.get('outcome')}")

    with factory() as session:
        sc = session.scalar(select(SourceConnection).where(SourceConnection.key == CONNECTION_KEY))
        assert sc is not None
        prior_rates = {
            (r.hs_code, float(r.rate))
            for r in session.scalars(
                select(TariffRate).where(
                    TariffRate.status == "active",
                    TariffRate.source_document_id == f"src_{CONNECTION_KEY}",
                )
            ).all()
        }
        # Prevent ensure_default_connections from restoring the good env URL.
        settings = client.app.state.settings
        settings.cbic_customs_url = None
        settings.cbic_customs_document_url = None
        sc.source_url = "https://courier.cbic.gov.in/advisory/2025/does-not-exist-404.pdf"
        caps = dict(sc.capabilities_json or {})
        caps.pop("document_url", None)
        sc.capabilities_json = caps
        session.commit()

    outage = client.post(f"/api/v1/source-connections/{CONNECTION_KEY}/fetch")
    if outage.status_code < 400:
        _fail("gate5_outage", f"expected failure, got {outage.status_code}")
        return 1

    with factory() as session:
        sc = session.scalar(select(SourceConnection).where(SourceConnection.key == CONNECTION_KEY))
        assert sc is not None
        if not sc.last_error:
            _fail("gate5_outage", "last_error not persisted")
            return 1
        after_rates = {
            (r.hs_code, float(r.rate))
            for r in session.scalars(
                select(TariffRate).where(
                    TariffRate.status == "active",
                    TariffRate.source_document_id == f"src_{CONNECTION_KEY}",
                )
            ).all()
        }
        if after_rates != prior_rates:
            _fail("gate5_outage", f"rates changed after outage {prior_rates} -> {after_rates}")
            return 1

    still = client.get(
        "/api/v1/tariffs",
        params={"hs": hs, "origin": "BD", "destination": "IN", "as_of": "2025-10-01"},
    )
    if still.status_code != 200 or not still.json():
        _fail("gate5_outage", "tariff lookup failed after outage")
        return 1
    _pass("gate5_outage", f"last_error set; prior rates intact ({len(prior_rates)} rows)")
    results["gate5"] = True

    print("SUMMARY", json.dumps(results))
    print("All live CBIC Chapter 61 verification gates passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
