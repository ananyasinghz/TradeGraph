"""Opt-in live official CBIC Chapter 61 verification (skipped unless env set).

Requires network access to courier.cbic.gov.in. Never run against production
fixtures; CI default skip keeps builds offline-safe.
"""

from __future__ import annotations

import os
from datetime import date
from decimal import Decimal
from pathlib import Path
from urllib.parse import quote

import pytest
from sqlalchemy import select

from backend.app.data.models import SourceConnection, TariffRate
from backend.app.domain.trade import ShipmentCreate
from backend.app.services import shipment_service
from backend.app.services.official_doc_normalize import normalize_official_document
from backend.tests.helpers.db import make_client

pytestmark = pytest.mark.skipif(
    os.environ.get("TRADE_LIVE_OFFICIAL_VERIFY", "").strip() not in {"1", "true", "TRUE", "yes"},
    reason="Set TRADE_LIVE_OFFICIAL_VERIFY=1 to hit real CBIC hosts",
)

ROOT = Path(__file__).resolve().parents[3]
LOCKED_DOCUMENT_URL = (
    "https://courier.cbic.gov.in/advisory/2025/"
    + quote("NOTIFICATION NO. 9_2025-INTEGRATED TAX (RATE) -1759486719.pdf")
)
LOCKED_PORTAL_URL = "https://courier.cbic.gov.in/notification.jsp"
ALLOWLIST = "localhost,127.0.0.1,courier.cbic.gov.in"
KEY = "cbic_ch61_igst_notif_9_2025"


@pytest.mark.live_official
def test_live_official_cbic_ch61_end_to_end() -> None:
    client = make_client(
        live_feed_enabled=True,
        http_source_allowlist=ALLOWLIST,
        cbic_customs_url=LOCKED_PORTAL_URL,
        cbic_customs_document_url=LOCKED_DOCUMENT_URL,
        live_feed_max_age_hours=720,
    )
    factory = client.app.state.session_factory

    fetch = client.post(f"/api/v1/source-connections/{KEY}/fetch")
    assert fetch.status_code == 200, fetch.text
    body = fetch.json()
    assert body["checksum"]
    assert (ROOT / body["archive_path"]).is_file()
    assert "courier.cbic.gov.in" in (body["connection"].get("last_final_url") or LOCKED_DOCUMENT_URL)

    batch_id = body.get("ingest_batch_id")
    assert batch_id, body
    detail = client.get(f"/api/v1/ingest/batches/{batch_id}").json()
    ok_rates = [
        p
        for p in detail["proposals"]
        if p["kind"] == "tariff_rate"
        and p["validation_status"] == "ok"
        and str(p["payload"].get("hs_code", "")).startswith("61")
    ]
    assert ok_rates, detail["validation_summary"]

    approved = client.post(
        f"/api/v1/ingest/batches/{batch_id}/approve",
        json={"notes": "live_official pytest"},
    )
    assert approved.status_code == 200

    hs = str(ok_rates[0]["payload"]["hs_code"])
    tariffs = client.get(
        "/api/v1/tariffs",
        params={"hs": hs, "origin": "BD", "destination": "IN", "as_of": "2025-10-01"},
    ).json()
    assert tariffs
    assert tariffs[0]["data_quality"] in {"source_verified", "demo_verified"}

    with factory() as session:
        ship = shipment_service.create_shipment(
            session,
            ShipmentCreate(
                title="live official ch61",
                product_text="knitted apparel verification",
                origin="BD",
                destination="IN",
                hs_code_working=hs,
                as_of_date=date(2025, 10, 1),
                invoice_value=Decimal("5000"),
                currency="USD",
                qty=Decimal("1"),
                freight=Decimal("50"),
                insurance=Decimal("25"),
            ),
        )
        session.commit()
        ship_id = ship.id

    calc = client.post(f"/api/v1/shipments/{ship_id}/calculate", json={})
    assert calc.status_code == 200, calc.text

    again = client.post(f"/api/v1/source-connections/{KEY}/fetch").json()
    assert again.get("outcome") in {"unchanged", "pending_review", "published"}

    with factory() as session:
        prior = {
            (r.hs_code, float(r.rate))
            for r in session.scalars(
                select(TariffRate).where(
                    TariffRate.status == "active",
                    TariffRate.source_document_id == f"src_{KEY}",
                )
            ).all()
        }
        row = session.scalar(select(SourceConnection).where(SourceConnection.key == KEY))
        assert row is not None
        client.app.state.settings.cbic_customs_url = None
        client.app.state.settings.cbic_customs_document_url = None
        row.source_url = "https://courier.cbic.gov.in/advisory/2025/missing-404.pdf"
        caps = dict(row.capabilities_json or {})
        caps.pop("document_url", None)
        row.capabilities_json = caps
        session.commit()

    fail = client.post(f"/api/v1/source-connections/{KEY}/fetch")
    assert fail.status_code >= 400

    with factory() as session:
        row = session.scalar(select(SourceConnection).where(SourceConnection.key == KEY))
        assert row is not None
        assert row.last_error
        after = {
            (r.hs_code, float(r.rate))
            for r in session.scalars(
                select(TariffRate).where(
                    TariffRate.status == "active",
                    TariffRate.source_document_id == f"src_{KEY}",
                )
            ).all()
        }
        assert after == prior


@pytest.mark.live_official
def test_normalize_live_downloaded_igst_pdf_bytes() -> None:
    import httpx

    data = httpx.get(LOCKED_DOCUMENT_URL, timeout=60.0).content
    assert data[:4] == b"%PDF"
    result = normalize_official_document(
        data,
        source_key=KEY,
        content_type="application/pdf",
        source_url=LOCKED_DOCUMENT_URL,
    )
    assert result.document_type == "amendment"
    assert any(r["hs_code"].startswith("61") for r in result.envelope["rates"])
    assert float(result.envelope["rates"][0]["duty_components"]["igst_pct"]) == 5.0
