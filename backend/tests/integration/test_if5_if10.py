"""IF-5..IF-10 integration coverage."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from backend.app.calculation.duty_components import calculate_india_import
from backend.app.integrations.adapters import pdf_document
from backend.app.integrations.core.registry import get_registry, reset_registry_for_tests
from backend.app.integrations.providers.bangladesh_customs import BangladeshCustomsProvider
from backend.app.integrations.providers.cbic import CbicDocumentProvider
from backend.tests.helpers.db import make_client

ROOT = Path(__file__).resolve().parents[3]


def setup_function() -> None:
    reset_registry_for_tests()


def test_if5_fixture_layout_exists() -> None:
    assert (ROOT / "config/trade/demo/seed_catalog.v1.yaml").is_file()
    assert (ROOT / "config/trade/fixtures/cbic/cbic_notification_2026_q3.json").is_file()
    assert (ROOT / "config/trade/fixtures/cbic/chapter61_bd_in_corpus.v1.json").is_file()
    assert (ROOT / "config/trade/operational").is_dir()


def test_if6_cbic_provider_and_pdf() -> None:
    reg = get_registry()
    assert reg.has("IN_CBIC")
    provider = reg.get("IN_CBIC")
    assert isinstance(provider, CbicDocumentProvider)
    result = provider.fetch_result()
    assert len(result.records) >= 30
    pdf = ROOT / "config/trade/fixtures/cbic/sample_notification.pdf"
    text = pdf_document.extract_pdf_text(pdf.read_bytes())
    assert "6109.10" in text or "BCD" in text or "CBIC" in text


def test_if7_tariff_lookup_evidence() -> None:
    client = make_client()
    response = client.get(
        "/api/v1/tariffs/lookup",
        params={"hs": "6109.10", "origin": "BD", "destination": "IN", "as_of": "2026-06-01"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"found", "stale"}
    assert body["tariff"] is not None
    assert body["tariff"]["evidence"] is not None
    assert "document_id" in body["tariff"]["evidence"]


def test_if8_bd_customs_provider() -> None:
    reg = get_registry()
    assert reg.has("BD_CUSTOMS")
    provider = reg.get("BD_CUSTOMS")
    assert isinstance(provider, BangladeshCustomsProvider)
    result = provider.fetch_result()
    assert result.records
    assert any(r.get("hs_code") == "6109.10" for r in result.records)


def test_if9_india_duty_engine() -> None:
    components, total, landed = calculate_india_import(
        assessable_value=Decimal("1000"),
        currency="USD",
        bcd_pct=Decimal("10"),
        sws_pct_of_bcd=Decimal("10"),
        igst_pct=Decimal("5"),
    )
    assert [c.code for c in components] == ["BCD", "SWS", "IGST"]
    assert components[0].amount == Decimal("100.00")
    assert components[1].amount == Decimal("10.00")
    assert total == Decimal("165.50")
    assert landed == Decimal("1165.50")


def test_if10_organizations_and_watchlist_org() -> None:
    client = make_client()
    orgs = client.get("/api/v1/organizations").json()
    assert any(o["id"] == "org_demo" for o in orgs)
    items = client.get("/api/v1/watchlist").json()
    assert items
    assert items[0].get("organization_id") == "org_demo"
