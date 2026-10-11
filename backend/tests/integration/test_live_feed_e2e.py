"""Live-feed acceptance tests (JSON test server → ingest → approve → impact)."""

from __future__ import annotations

import json
import threading
from datetime import UTC, date, datetime
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from sqlalchemy import func, select

from backend.app.core.errors import AppError
from backend.app.data.models import IngestionBatch, ScenarioImpact, Shipment, SourceConnection, TariffRate
from backend.app.domain.trade import IngestRunRequest, ShipmentCreate
from backend.app.services import ingestion_service, shipment_service, source_adapters, source_connection_service
from backend.app.services.source_connection_service import ensure_default_connections
from backend.tests.helpers.db import make_client, make_seeded_engine

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "config" / "trade" / "fixtures" / "cbic" / "cbic_notification_2026_q3.json"


class _PackServer:
    def __init__(self, body: bytes, status: int = 200, content_type: str = "application/json"):
        self.body = body
        self.status = status
        self.content_type = content_type
        parent = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # noqa: ANN002
                return

            def do_GET(self):  # noqa: N802
                self.send_response(parent.status)
                self.send_header("Content-Type", parent.content_type)
                self.send_header("Content-Length", str(len(parent.body)))
                self.end_headers()
                self.wfile.write(parent.body)

        self._httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.port = self._httpd.server_address[1]
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/tariff_pack.json"

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._httpd.shutdown()


def _valid_pack(*, rate_610910: float | None = None, whitespace: bool = False) -> bytes:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data["source_key"] = "live_tariff_http"
    data["document_type"] = "tariff_pack"
    if rate_610910 is not None:
        for rate in data["rates"]:
            if rate.get("hs_code") == "6109.10" and rate.get("origin") == "BD":
                rate["rate"] = rate_610910
                rate["duty_components"]["bcd_pct"] = rate_610910
    if whitespace:
        return (json.dumps(data, indent=4) + "\n\n").encode("utf-8")
    return json.dumps(data).encode("utf-8")


def _seed_live(session, url: str) -> None:
    ensure_default_connections(session)
    row = session.scalar(select(SourceConnection).where(SourceConnection.key == "live_tariff_http"))
    if row is None:
        session.add(
            SourceConnection(
                key="live_tariff_http",
                title="Live tariff JSON HTTP feed",
                publisher="test",
                fetch_mode="http_get",
                adapter="live_http_api",
                source_url=url,
                local_path=None,
                enabled=True,
                origin="BD",
                destination="IN",
                hs_chapter="61",
                honesty_label="Live HTTP feed",
                notes="test",
                created_at=datetime.now(UTC),
                capabilities_json={"pipeline": {"stage": "configured"}},
            )
        )
    else:
        row.source_url = url
        row.adapter = "live_http_api"
        row.enabled = True
    session.flush()


def test_fetch_and_archive_creates_artifact() -> None:
    server = _PackServer(_valid_pack())
    server.start()
    try:
        payload = source_adapters.fetch_http_get(
            source_url=server.url,
            allowlist="localhost,127.0.0.1",
            require_json=True,
            allow_localhost=True,
        )
        assert payload.content_type == "application/json"
        assert payload.final_url
        assert payload.http_status == 200
        assert json.loads(payload.content)["source_key"] == "live_tariff_http"
    finally:
        server.stop()


def test_network_failures_never_publish() -> None:
    with pytest.raises(AppError) as exc:
        source_adapters.fetch_http_get(
            source_url="https://not-allowed.example/x",
            allowlist="localhost,127.0.0.1",
            require_json=True,
        )
    assert exc.value.code == "SOURCE_HTTP_HOST_NOT_ALLOWLISTED"

    server = _PackServer(b"{}", status=404)
    server.start()
    try:
        with pytest.raises(AppError) as exc2:
            source_adapters.fetch_http_get(
                source_url=server.url,
                allowlist="localhost,127.0.0.1",
                require_json=True,
                allow_localhost=True,
            )
        assert exc2.value.code == "SOURCE_HTTP_ERROR"
    finally:
        server.stop()

    bad = _PackServer(b"<html>", content_type="text/html")
    bad.start()
    try:
        with pytest.raises(AppError) as exc3:
            source_adapters.fetch_http_get(
                source_url=bad.url,
                allowlist="localhost,127.0.0.1",
                require_json=True,
                allow_localhost=True,
            )
        assert exc3.value.code == "SOURCE_HTTP_CONTENT_TYPE"
    finally:
        bad.stop()


def test_live_fetch_ingest_quarantine_and_idempotent() -> None:
    server = _PackServer(_valid_pack())
    server.start()
    try:
        _engine, factory = make_seeded_engine()
        with factory() as session:
            _seed_live(session, server.url)
            session.commit()

            result = source_connection_service.fetch_connection(
                session, "live_tariff_http", run_ingest=True
            )
            assert result.ingest_batch_id
            assert result.checksum
            assert Path(ROOT / result.archive_path).is_file()

            batch = ingestion_service.get_batch(session, result.ingest_batch_id)
            assert batch.status == "pending_review"
            ok = [p for p in batch.proposals if p.validation_status == "ok"]
            err = [p for p in batch.proposals if p.validation_status == "error"]
            assert ok
            assert err
            assert any("unknown_hs_code" in (p.validation_errors or []) for p in err)

            result2 = source_connection_service.fetch_connection(
                session, "live_tariff_http", run_ingest=True
            )
            assert result2.ingest_batch_id == result.ingest_batch_id

            live_active = session.scalars(
                select(TariffRate).where(
                    TariffRate.source_document_id == "src_live_tariff_http",
                    TariffRate.status == "active",
                )
            ).all()
            assert live_active == []
            session.commit()
    finally:
        server.stop()


def test_reject_preserves_prior_rules_and_approve_publishes() -> None:
    server = _PackServer(_valid_pack(rate_610910=12.0))
    server.start()
    try:
        client = make_client(
            live_feed_enabled=True,
            live_tariff_http_url=server.url,
            http_source_allowlist="localhost,127.0.0.1",
        )
        with client.app.state.session_factory() as session:
            _seed_live(session, server.url)
            ship = shipment_service.create_shipment(
                session,
                ShipmentCreate(
                    title="Live feed impact case",
                    product_text="cotton tee",
                    origin="BD",
                    destination="IN",
                    hs_code_working="6109.10",
                    as_of_date=date(2026, 6, 1),
                    invoice_value=Decimal("5000"),
                    currency="USD",
                    incoterm="CIF",
                    qty=Decimal("1"),
                    freight=Decimal("100"),
                    insurance=Decimal("50"),
                ),
            )
            srow = session.get(Shipment, ship.id)
            assert srow is not None
            srow.hs_confirmed_at = datetime.now(UTC)
            session.commit()
            ship_id = ship.id

        promo = client.post("/api/v1/ingest/promote-cbic", json={"notes": "baseline"})
        assert promo.status_code == 200, promo.text

        with client.app.state.session_factory() as session:
            prior_count = int(
                session.scalar(
                    select(func.count())
                    .select_from(TariffRate)
                    .where(TariffRate.status == "active", TariffRate.hs_code == "6109.10")
                )
                or 0
            )

        fetch = client.post("/api/v1/source-connections/live_tariff_http/fetch")
        assert fetch.status_code == 200, fetch.text
        batch_id = fetch.json()["ingest_batch_id"]
        assert batch_id

        diff = client.get(f"/api/v1/ingest/batches/{batch_id}/diff")
        assert diff.status_code == 200, diff.text
        assert diff.json()["quarantined"]

        rej = client.post(f"/api/v1/ingest/batches/{batch_id}/reject", json={"notes": "no"})
        assert rej.status_code == 200
        with client.app.state.session_factory() as session:
            after_reject = int(
                session.scalar(
                    select(func.count())
                    .select_from(TariffRate)
                    .where(TariffRate.status == "active", TariffRate.hs_code == "6109.10")
                )
                or 0
            )
            assert after_reject == prior_count

        with client.app.state.session_factory() as session:
            conn = session.scalar(
                select(SourceConnection).where(SourceConnection.key == "live_tariff_http")
            )
            assert conn and conn.last_archive_path
            arch = Path(ROOT / conn.last_archive_path)
            json_arch = arch.with_suffix(".json")
            path = (
                str(json_arch.relative_to(ROOT)).replace("\\", "/")
                if json_arch.is_file()
                else conn.last_archive_path
            )
            detail = ingestion_service.run_ingest(
                session,
                IngestRunRequest(source_key="live_tariff_http", archive_path=path, force=True),
            )
            session.commit()
            batch_id2 = detail.id

        appr = client.post(
            f"/api/v1/ingest/batches/{batch_id2}/approve",
            json={"notes": "approve live"},
        )
        assert appr.status_code == 200, appr.text
        assert appr.json()["status"] == "approved"

        feed = client.get("/api/v1/source-connections/feed-status")
        assert feed.status_code == 200
        assert feed.json()["live_feed_enabled_setting"] is True
        assert feed.json()["live_government_feed"] is True

        with client.app.state.session_factory() as session:
            live_rates = session.scalars(
                select(TariffRate).where(
                    TariffRate.source_document_id == "src_live_tariff_http",
                    TariffRate.status == "active",
                    TariffRate.hs_code == "6109.10",
                )
            ).all()
            assert live_rates
            assert float(live_rates[0].rate) == 12.0
            impacts = session.scalars(
                select(ScenarioImpact).where(ScenarioImpact.shipment_id == ship_id)
            ).all()
            assert impacts
    finally:
        server.stop()


def test_semantic_unchanged_no_new_batch_after_publish() -> None:
    server = _PackServer(_valid_pack(whitespace=False))
    server.start()
    try:
        _engine, factory = make_seeded_engine()
        with factory() as session:
            _seed_live(session, server.url)
            session.commit()
            r1 = source_connection_service.fetch_connection(session, "live_tariff_http")
            assert r1.ingest_batch_id
            ingestion_service.approve_batch(session, r1.ingest_batch_id, notes="pub")
            session.commit()

        server.stop()
        server = _PackServer(_valid_pack(whitespace=True))
        server.start()
        with factory() as session:
            _seed_live(session, server.url)
            r2 = source_connection_service.fetch_connection(session, "live_tariff_http")
            assert r2.outcome == "unchanged"
            assert r2.ingest_batch_id is None
            pending = session.scalars(
                select(IngestionBatch).where(
                    IngestionBatch.source_key == "live_tariff_http",
                    IngestionBatch.status == "pending_review",
                )
            ).all()
            assert pending == []
    finally:
        server.stop()


def test_honest_status_curated_never_live() -> None:
    client = make_client(live_feed_enabled=True)
    resp = client.get("/api/v1/source-connections/feed-status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["live_government_feed"] is False


def test_batch_diff_endpoint() -> None:
    _engine, factory = make_seeded_engine()
    with factory() as session:
        batch = ingestion_service.run_ingest(
            session,
            IngestRunRequest(source_key="cbic_notification_2026_q3", force=True),
        )
        session.commit()
        diff = ingestion_service.batch_diff(session, batch.id)
        assert diff.batch_id == batch.id
        assert diff.quarantined
        assert diff.changes
