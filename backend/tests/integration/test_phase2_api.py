"""Phase 2 FTA / retrieval / watchlist tests."""

from __future__ import annotations

from backend.tests.helpers.db import make_client


def test_fta_check_returns_graph_path_and_preferential_rate() -> None:
    client = make_client()
    response = client.post(
        "/api/v1/fta/check",
        json={
            "hs_code": "6109.10",
            "origin": "BD",
            "destination": "IN",
            "as_of": "2026-06-01",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {
        "potentially_eligible",
        "needs_evidence",
        "eligible",
        "not_covered",
        "ineligible",
        "unknown",
    }
    assert float(body["preferential_rate_pct"]) == 5.0
    assert float(body["mfn_rate_pct"]) == 20.0
    assert body["certificate_doc_code"] == "certificate_of_origin"
    assert len(body["graph_path"]) >= 1
    assert any(e.get("kind") == "fta_eligibility" for e in body["evidence"])


def test_retrieve_rules_of_origin() -> None:
    client = make_client()
    response = client.get(
        "/api/v1/retrieve",
        params={"q": "proof of origin certificate preferential", "hs": "6109.10"},
    )
    assert response.status_code == 200
    hits = response.json()
    assert len(hits) >= 1
    assert hits[0]["source_document_id"]


def test_watchlist_shows_seeded_rate_change() -> None:
    client = make_client()
    items = client.get("/api/v1/watchlist").json()
    assert any(i["hs_code"] == "6109.10" for i in items)
    changes = client.get("/api/v1/watchlist/changes").json()
    assert len(changes) >= 1
    assert float(changes[0]["old_rate"]) == 22.0
    assert float(changes[0]["new_rate"]) == 20.0


def test_ask_fta_uses_graph_vector_route() -> None:
    client = make_client()
    ask = client.post(
        "/api/v1/ask",
        json={
            "query": "Can I claim preferential FTA duty for HS 6109.10 BD to IN under SAFTA?",
            "as_of": "2026-06-01",
        },
    )
    assert ask.status_code == 200
    body = ask.json()
    assert body["route"] == "graph_vector"
    assert "fta_check" in body["tools_invoked"]
    assert body["result"]["fta"]["status"] in {
        "potentially_eligible",
        "needs_evidence",
        "eligible",
        "not_covered",
        "ineligible",
        "unknown",
    }
