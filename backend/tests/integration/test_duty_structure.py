"""Integration: duty structure + exemption picker APIs."""

from __future__ import annotations

from backend.tests.helpers.db import make_client


def test_duty_structure_full_stack_and_exemptions() -> None:
    client = make_client()
    response = client.get(
        "/api/v1/duty/structure",
        params={
            "hs": "6109.10",
            "origin": "BD",
            "destination": "IN",
            "as_of": "2026-06-01",
            "assessable_value": "100000",
            "currency": "INR",
        },
    )
    assert response.status_code == 200
    body = response.json()
    codes = [r["code"] for r in body["stack"]]
    assert codes == ["BCD", "AIDC", "CHCESS", "SWS", "IGST", "CC"]
    assert float(body["total_duties"]) == 49860.0
    assert any(e["serial_no"] == "282" for e in body["exemptions"])
    assert "component" in body["honesty_note"].lower()
    assert body["component_sources"]
    assert body["coverage"]["bcd_pct"] in {
        "curated_official_backed",
        "illustrative",
        "source_verified",
    }


def test_duty_structure_with_exemption_saves_money() -> None:
    client = make_client()
    mfn = client.get(
        "/api/v1/duty/structure",
        params={
            "hs": "6109.10",
            "origin": "BD",
            "destination": "IN",
            "as_of": "2026-06-01",
            "assessable_value": "100000",
            "currency": "INR",
        },
    ).json()
    ex_id = next(e["id"] for e in mfn["exemptions"] if e["serial_no"] == "282")
    preferred = client.get(
        "/api/v1/duty/structure",
        params={
            "hs": "6109.10",
            "origin": "BD",
            "destination": "IN",
            "as_of": "2026-06-01",
            "assessable_value": "100000",
            "currency": "INR",
            "selected_exemption_id": ex_id,
        },
    ).json()
    assert float(preferred["duty_savings"]) > 0
    assert float(preferred["total_duties"]) < float(mfn["total_duties"])
    bcd = next(r for r in preferred["stack"] if r["code"] == "BCD")
    assert float(bcd["effective_rate_pct"]) == 5.0
    assert float(bcd["tariff_rate_pct"]) == 20.0
