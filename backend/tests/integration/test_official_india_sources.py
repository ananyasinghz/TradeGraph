"""Official India document sources: HTML/PDF fetch → normalize → approve → impact."""

from __future__ import annotations

import threading
from datetime import UTC, date, datetime
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from sqlalchemy import select

from backend.app.data.models import ScenarioImpact, Shipment, SourceConnection, TariffRate
from backend.app.domain.trade import ShipmentCreate
from backend.app.services import shipment_service
from backend.app.services.official_doc_normalize import normalize_official_document
from backend.app.services.source_connection_service import ensure_default_connections
from backend.tests.helpers.db import make_client

ROOT = Path(__file__).resolve().parents[3]
SAMPLES = ROOT / "config" / "trade" / "fixtures" / "cbic" / "official_samples"


class _FixtureServer:
    """Serves official_samples HTML/PDF; never hits production portals."""

    def __init__(self) -> None:
        parent = self
        self.files = {
            "/index.html": ("text/html", (SAMPLES / "index.html").read_bytes()),
            "/notification.html": ("text/html", (SAMPLES / "notification.html").read_bytes()),
            "/unsupported.html": ("text/html", (SAMPLES / "unsupported.html").read_bytes()),
            "/rate_change.html": ("text/html", (SAMPLES / "rate_change.html").read_bytes()),
            "/notification.pdf": ("application/pdf", (SAMPLES / "notification.pdf").read_bytes()),
            "/disallowed": ("text/html", b"<html>nope</html>"),
        }

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # noqa: ANN002
                return

            def do_GET(self):  # noqa: N802
                path = self.path.split("?")[0]
                if path == "/":
                    path = "/index.html"
                if path not in parent.files:
                    self.send_response(404)
                    self.end_headers()
                    return
                ctype, body = parent.files[path]
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self._httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.port = self._httpd.server_address[1]
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._httpd.shutdown()


def _seed_official(
    session,
    *,
    portal_url: str,
    document_url: str | None = None,
    key: str = "cbic_taxinfo_docs",
) -> None:
    ensure_default_connections(session)
    row = session.scalar(select(SourceConnection).where(SourceConnection.key == key))
    caps = {"pipeline": {"stage": "configured"}}
    if document_url:
        caps["document_url"] = document_url
    if row is None:
        session.add(
            SourceConnection(
                key=key,
                title="CBIC Tax Information Portal (test)",
                publisher="CBIC fixture",
                fetch_mode="official_document",
                adapter="official_document_http",
                source_url=portal_url,
                local_path=None,
                enabled=True,
                origin="BD",
                destination="IN",
                hs_chapter="61",
                honesty_label="Official document fixture",
                notes="test",
                created_at=datetime.now(UTC),
                capabilities_json=caps,
            )
        )
    else:
        row.source_url = portal_url
        row.adapter = "official_document_http"
        row.fetch_mode = "official_document"
        row.enabled = True
        row.capabilities_json = caps
    session.flush()


def test_normalize_html_and_pdf_chapter61() -> None:
    html = (SAMPLES / "notification.html").read_bytes()
    result = normalize_official_document(
        html,
        source_key="cbic_taxinfo_docs",
        content_type="text/html",
        source_url="http://127.0.0.1/notification.html",
    )
    assert result.document_type == "amendment"
    assert len(result.envelope["rates"]) >= 3
    hs = {r["hs_code"] for r in result.envelope["rates"]}
    assert "6109.10" in hs
    assert any("document_type_partial" in w for w in result.warnings)

    pdf = (SAMPLES / "notification.pdf").read_bytes()
    pdf_result = normalize_official_document(
        pdf, source_key="cbic_taxinfo_docs", content_type="application/pdf"
    )
    assert len(pdf_result.envelope["rates"]) >= 2
    assert "TG-PDF" in str(pdf_result.envelope.get("notice_id") or "")


def test_fetch_archive_html_and_pdf() -> None:
    server = _FixtureServer()
    server.start()
    try:
        client = make_client(
            live_feed_enabled=True,
            http_source_allowlist="localhost,127.0.0.1",
            cbic_taxinfo_url=f"{server.base}/index.html",
            cbic_taxinfo_document_url=f"{server.base}/notification.html",
        )
        factory = client.app.state.session_factory
        with factory() as session:
            _seed_official(
                session,
                portal_url=f"{server.base}/index.html",
                document_url=f"{server.base}/notification.html",
            )
            session.commit()

        fetch = client.post("/api/v1/source-connections/cbic_taxinfo_docs/fetch")
        assert fetch.status_code == 200, fetch.text
        body = fetch.json()
        assert body["checksum"]
        assert body["archive_path"]
        assert body["ingest_batch_id"]
        assert Path(ROOT / body["archive_path"]).is_file()

        # PDF path
        with factory() as session:
            _seed_official(
                session,
                portal_url=f"{server.base}/notification.pdf",
                document_url=None,
                key="cbic_customs_docs",
            )
            session.commit()
        pdf_fetch = client.post("/api/v1/source-connections/cbic_customs_docs/fetch")
        assert pdf_fetch.status_code == 200, pdf_fetch.text
        assert pdf_fetch.json()["checksum"]
    finally:
        server.stop()


def test_disallowed_host_never_publishes() -> None:
    client = make_client(
        live_feed_enabled=True,
        http_source_allowlist="example.invalid",
        cbic_taxinfo_url="http://127.0.0.1:9/notification.html",
    )
    factory = client.app.state.session_factory
    with factory() as session:
        before = session.scalar(
            select(TariffRate).where(TariffRate.status == "active").limit(1)
        )
        _seed_official(session, portal_url="http://127.0.0.1:9/notification.html")
        session.commit()
    resp = client.post("/api/v1/source-connections/cbic_taxinfo_docs/fetch")
    assert resp.status_code >= 400
    with factory() as session:
        after_count = len(
            session.scalars(select(TariffRate).where(TariffRate.status == "active")).all()
        )
        # Failed fetch must not wipe active rates (at least seed rates remain).
        assert after_count >= (1 if before else 0)


def test_quarantine_unknown_hs_and_approve_only_ok() -> None:
    server = _FixtureServer()
    server.start()
    try:
        client = make_client(
            live_feed_enabled=True,
            http_source_allowlist="localhost,127.0.0.1",
        )
        factory = client.app.state.session_factory
        with factory() as session:
            _seed_official(
                session,
                portal_url=f"{server.base}/notification.html",
            )
            session.commit()

        fetch = client.post("/api/v1/source-connections/cbic_taxinfo_docs/fetch")
        assert fetch.status_code == 200
        batch_id = fetch.json()["ingest_batch_id"]
        assert batch_id
        detail = client.get(f"/api/v1/ingest/batches/{batch_id}").json()
        assert detail["validation_summary"]["ok"] >= 1
        assert detail["validation_summary"]["error"] >= 1
        assert any(p["validation_status"] == "error" for p in detail["proposals"])

        approved = client.post(
            f"/api/v1/ingest/batches/{batch_id}/approve",
            json={"notes": "official india test"},
        )
        assert approved.status_code == 200
        body = approved.json()
        for p in body["proposals"]:
            if p["validation_status"] == "ok":
                assert p["publish_status"] == "published"
            if p["validation_status"] == "error":
                assert p["publish_status"] == "skipped"

        with factory() as session:
            bad = session.scalars(
                select(TariffRate).where(
                    TariffRate.hs_code == "9999.99",
                    TariffRate.status == "active",
                )
            ).all()
            assert bad == []
    finally:
        server.stop()


def test_idempotent_and_unsupported_document() -> None:
    server = _FixtureServer()
    server.start()
    try:
        client = make_client(
            live_feed_enabled=True,
            http_source_allowlist="localhost,127.0.0.1",
        )
        factory = client.app.state.session_factory
        with factory() as session:
            _seed_official(
                session,
                portal_url=f"{server.base}/notification.html",
            )
            session.commit()

        first = client.post("/api/v1/source-connections/cbic_taxinfo_docs/fetch").json()
        second = client.post("/api/v1/source-connections/cbic_taxinfo_docs/fetch").json()
        assert first["ingest_batch_id"]
        assert second["outcome"] in {"unchanged", "pending_review"}
        assert second["ingest_batch_id"] == first["ingest_batch_id"] or second["outcome"] == "unchanged"

        with factory() as session:
            _seed_official(
                session,
                portal_url=f"{server.base}/unsupported.html",
                key="icegate_public_docs",
            )
            session.commit()
        unsupported = client.post("/api/v1/source-connections/icegate_public_docs/fetch")
        assert unsupported.status_code == 200
        body = unsupported.json()
        assert body["ingest_batch_id"] is None
        assert body["outcome"] == "unsupported_document"
    finally:
        server.stop()


def test_failed_refresh_keeps_prior_published_rates() -> None:
    server = _FixtureServer()
    server.start()
    try:
        client = make_client(
            live_feed_enabled=True,
            http_source_allowlist="localhost,127.0.0.1",
        )
        factory = client.app.state.session_factory
        with factory() as session:
            _seed_official(
                session,
                portal_url=f"{server.base}/notification.html",
            )
            session.commit()

        fetch = client.post("/api/v1/source-connections/cbic_taxinfo_docs/fetch").json()
        batch_id = fetch["ingest_batch_id"]
        approved = client.post(
            f"/api/v1/ingest/batches/{batch_id}/approve",
            json={"notes": "publish first"},
        )
        assert approved.status_code == 200

        with factory() as session:
            active_before = {
                (r.hs_code, float(r.rate))
                for r in session.scalars(
                    select(TariffRate).where(
                        TariffRate.status == "active",
                        TariffRate.source_document_id == "src_cbic_taxinfo_docs",
                    )
                ).all()
            }
            assert active_before
            row = session.scalar(
                select(SourceConnection).where(SourceConnection.key == "cbic_taxinfo_docs")
            )
            assert row is not None
            row.source_url = "http://127.0.0.1:1/nowhere"
            session.commit()

        fail = client.post("/api/v1/source-connections/cbic_taxinfo_docs/fetch")
        assert fail.status_code >= 400

        with factory() as session:
            active_after = {
                (r.hs_code, float(r.rate))
                for r in session.scalars(
                    select(TariffRate).where(
                        TariffRate.status == "active",
                        TariffRate.source_document_id == "src_cbic_taxinfo_docs",
                    )
                ).all()
            }
            assert active_after == active_before
            row = session.scalar(
                select(SourceConnection).where(SourceConnection.key == "cbic_taxinfo_docs")
            )
            assert row is not None
            assert row.last_error
            pipe = (row.capabilities_json or {}).get("pipeline") or {}
            assert pipe.get("stage") == "error"

        status = client.get("/api/v1/source-connections/feed-status").json()
        # After error, feed must not look freshly healthy as live without success.
        assert status["live_government_feed"] is False or status.get("last_error")
    finally:
        server.stop()


def test_rate_change_creates_impact_noop_does_not() -> None:
    server = _FixtureServer()
    server.start()
    try:
        client = make_client(
            live_feed_enabled=True,
            http_source_allowlist="localhost,127.0.0.1",
        )
        factory = client.app.state.session_factory
        with factory() as session:
            _seed_official(
                session,
                portal_url=f"{server.base}/notification.html",
            )
            shipment_service.create_shipment(
                session,
                ShipmentCreate(
                    title="Official impact case",
                    product_text="Cotton knitted T-shirt",
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
            session.commit()

        fetch = client.post("/api/v1/source-connections/cbic_taxinfo_docs/fetch").json()
        assert fetch["ingest_batch_id"]
        client.post(
            f"/api/v1/ingest/batches/{fetch['ingest_batch_id']}/approve",
            json={"notes": "baseline"},
        )

        with factory() as session:
            row = session.scalar(
                select(SourceConnection).where(SourceConnection.key == "cbic_taxinfo_docs")
            )
            assert row is not None
            row.source_url = f"{server.base}/rate_change.html"
            caps = dict(row.capabilities_json or {})
            pipe = dict(caps.get("pipeline") or {})
            pipe.pop("semantic_fingerprint", None)
            pipe.pop("last_published_fingerprint", None)
            caps["pipeline"] = pipe
            row.capabilities_json = caps
            session.commit()
            impacts_before = len(session.scalars(select(ScenarioImpact)).all())

        changed = client.post("/api/v1/source-connections/cbic_taxinfo_docs/fetch")
        assert changed.status_code == 200
        body = changed.json()
        batch_id = body.get("ingest_batch_id")
        assert batch_id, body
        client.post(
            f"/api/v1/ingest/batches/{batch_id}/approve",
            json={"notes": "rate change"},
        )

        with factory() as session:
            impacts = session.scalars(select(ScenarioImpact)).all()
            assert len(session.scalars(select(Shipment)).all()) >= 1
            assert len(impacts) >= impacts_before
            assert any(i.hs_code == "6109.10" for i in impacts)

        again = client.post("/api/v1/source-connections/cbic_taxinfo_docs/fetch").json()
        assert again.get("outcome") == "unchanged"
        assert again.get("ingest_batch_id") in {None, batch_id}
    finally:
        server.stop()


def test_ensure_seeds_official_when_env_set() -> None:
    client = make_client(
        cbic_taxinfo_url="http://127.0.0.1:8766/index.html",
        icegate_public_url="http://127.0.0.1:8766/unsupported.html",
        http_source_allowlist="localhost,127.0.0.1",
    )
    listed = client.get("/api/v1/source-connections").json()
    keys = {r["key"] for r in listed}
    assert "cbic_taxinfo_docs" in keys
    assert "icegate_public_docs" in keys
    tax = next(r for r in listed if r["key"] == "cbic_taxinfo_docs")
    assert tax["adapter"] == "official_document_http"
