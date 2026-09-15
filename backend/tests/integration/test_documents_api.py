"""Documents catalog API tests."""

from __future__ import annotations

from backend.tests.helpers.db import make_client


def test_document_requirements_lists_bd_in_templates() -> None:
    client = make_client()
    response = client.get(
        "/api/v1/document-requirements",
        params={"origin": "BD", "destination": "IN"},
    )
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) >= 4
    codes = {r["doc_code"] for r in rows}
    assert "commercial_invoice" in codes
    assert "certificate_of_origin" in codes
    assert any(r["doc_label"] for r in rows)
