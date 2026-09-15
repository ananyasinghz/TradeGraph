"""Classification FTS + priors + linen pants smoke tests."""

from __future__ import annotations

from backend.app.services.classification_service import rank_descriptions
from backend.app.services.hs_attributes import extract_attributes_rules
from backend.app.services.hs_eval_service import evaluate_hs_classify
from backend.tests.helpers.db import make_client, make_seeded_engine


def test_linen_pants_priors_prefer_trousers() -> None:
    ranked = rank_descriptions(
        "100% linen pants",
        [
            ("6203.42", "Men's trousers of cotton"),
            ("6108.21", "Women's briefs and panties"),
            ("6109.10", "T-shirts of cotton"),
        ],
    )
    assert ranked[0][0].startswith("6203")


def test_extract_attributes_trousers() -> None:
    attrs = extract_attributes_rules("100% linen pants")
    assert attrs.garment_type == "trousers"
    assert attrs.material == "linen"


def test_classification_api_linen_pants_nonempty() -> None:
    client = make_client()
    resp = client.post(
        "/api/v1/classification/candidates",
        json={"product_text": "100% linen pants", "limit": 5},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["candidates"], body
    codes = [c["hs_code"] for c in body["candidates"]]
    assert any(c.startswith("6203") or c.startswith("6204") or c.startswith("6103") for c in codes)


def test_classification_api_cotton_tshirt() -> None:
    client = make_client()
    resp = client.post(
        "/api/v1/classification/candidates",
        json={"product_text": "100% cotton knitted T-shirts", "limit": 5},
    )
    assert resp.status_code == 200
    codes = [c["hs_code"] for c in resp.json()["candidates"]]
    assert any(c.startswith("6109") for c in codes)


def test_hs_eval_runs_on_seeded_db() -> None:
    _engine, factory = make_seeded_engine()
    with factory() as session:
        report = evaluate_hs_classify(session, min_items_for_threshold=10_000)
    assert report["n"] >= 20
    assert report["top3_recall"] >= 0.3
    assert report["gate_failed"] is False
