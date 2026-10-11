"""Clearance portal Rounds 6–11: admin, invites, parties, exports, share, search."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from backend.tests.helpers.db import make_client


def _create_shipment(client, *, title: str = "R6-R11 case", hs: str | None = "6109.10"):
    payload = {
        "title": title,
        "product_text": "100% cotton knitted T-shirts",
        "origin": "BD",
        "destination": "IN",
        "hs_code_working": hs,
        "as_of_date": "2026-06-01",
        "invoice_value": "5000",
        "currency": "USD",
        "incoterm": "CIF",
        "qty": 10,
    }
    created = client.post("/api/v1/shipments", json=payload)
    assert created.status_code == 200, created.text
    return created.json()["id"]


def test_admin_list_and_patch_user_role() -> None:
    client = make_client(auth_enabled=True)
    admin = {"Authorization": "Bearer demo-admin"}
    operator = {"Authorization": "Bearer demo-operator"}

    forbidden = client.get("/api/v1/admin/users", headers=operator)
    assert forbidden.status_code == 403

    users = client.get("/api/v1/admin/users", headers=admin)
    assert users.status_code == 200, users.text
    rows = users.json()
    assert any(u["email"] == "operator@demo.tradegraph.local" for u in rows)
    target = next(u for u in rows if u["email"] == "viewer@demo.tradegraph.local")
    assert target["role"] == "viewer"
    assert target["organization_id"]

    patched = client.patch(
        f"/api/v1/admin/users/{target['id']}",
        headers=admin,
        json={"role": "operator"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["role"] == "operator"


def test_operator_cannot_approve_ingest() -> None:
    client = make_client(auth_enabled=True)
    operator = {"Authorization": "Bearer demo-operator"}
    response = client.post(
        "/api/v1/ingest/batches/missing/approve",
        headers=operator,
    )
    assert response.status_code == 403


def test_invites_and_auth_me_and_mfa_whoami() -> None:
    client = make_client(auth_enabled=True)
    admin = {"Authorization": "Bearer demo-admin"}
    operator = {"Authorization": "Bearer demo-operator"}

    invite = client.post(
        "/api/v1/admin/invites",
        headers=admin,
        json={"email": "new.broker@example.com", "role": "operator"},
    )
    assert invite.status_code == 200, invite.text
    assert invite.json()["email"] == "new.broker@example.com"
    assert invite.json()["status"] == "pending"

    listed = client.get("/api/v1/admin/invites", headers=admin)
    assert listed.status_code == 200
    assert any(i["email"] == "new.broker@example.com" for i in listed.json())

    me = client.patch(
        "/api/v1/auth/me",
        headers=operator,
        json={
            "display_name": "Ops Lead",
            "notification_prefs": {"watchlist_email": False, "in_app": True},
        },
    )
    assert me.status_code == 200, me.text
    assert me.json()["name"] == "Ops Lead"
    assert me.json()["notification_prefs"]["watchlist_email"] is False

    who = client.get("/api/v1/auth/whoami", headers=operator)
    assert who.status_code == 200
    body = who.json()
    assert body["display_name"] == "Ops Lead"
    assert "mfa_required" in body
    assert body["mfa_required"] is False


def test_retention_archive_marks_old_closed() -> None:
    client = make_client()
    sid = _create_shipment(client, title="Archive me")
    closed = client.post(f"/api/v1/shipments/{sid}/close")
    assert closed.status_code == 200

    session_factory = client.app.state.session_factory
    with session_factory() as session:
        from backend.app.data.models import Shipment

        row = session.get(Shipment, sid)
        assert row is not None
        row.closed_at = datetime.now(UTC) - timedelta(days=120)
        session.commit()

    job = client.post("/api/v1/jobs/retention-archive?days=90")
    assert job.status_code == 200, job.text
    assert job.json()["summary"]["archived"] >= 1

    detail = client.get(f"/api/v1/shipments/{sid}")
    assert detail.status_code == 200
    assert detail.json()["archived_at"] is not None


def test_parties_line_items_comments_assign_reviewer() -> None:
    client = make_client()
    party = client.post(
        "/api/v1/parties",
        json={
            "name": "Dhaka Knit Exporters",
            "role": "exporter",
            "country": "BD",
        },
    )
    assert party.status_code == 200, party.text
    party_id = party.json()["id"]

    parties = client.get("/api/v1/parties")
    assert parties.status_code == 200
    assert any(p["id"] == party_id for p in parties.json())

    patched_party = client.patch(
        f"/api/v1/parties/{party_id}",
        json={"notes": "Preferred supplier"},
    )
    assert patched_party.status_code == 200
    assert patched_party.json()["notes"] == "Preferred supplier"

    sid = _create_shipment(client, title="Multi-line case")
    detail = client.get(f"/api/v1/shipments/{sid}")
    line_id = detail.json()["line_items"][0]["id"]

    updated = client.patch(
        f"/api/v1/shipments/{sid}/line-items/{line_id}",
        json={"qty": 20, "unit_value": "250"},
    )
    assert updated.status_code == 200, updated.text

    added = client.post(
        f"/api/v1/shipments/{sid}/line-items",
        json={
            "description": "Second line cotton tops",
            "line_number": 2,
            "hs_code": "6109.10",
            "qty": 5,
            "unit_value": "100",
            "currency": "USD",
            "origin": "BD",
        },
    )
    assert added.status_code == 200, added.text
    assert len(added.json()["line_items"]) >= 2

    calc = client.post(f"/api/v1/shipments/{sid}/calculate")
    assert calc.status_code == 200, calc.text
    assert calc.json()["latest_calculation"] is not None

    comment = client.post(
        f"/api/v1/shipments/{sid}/comments",
        json={"body": "Need COO before preferential claim."},
    )
    assert comment.status_code == 200, comment.text
    comments = client.get(f"/api/v1/shipments/{sid}/comments")
    assert comments.status_code == 200
    assert len(comments.json()) >= 1

    assigned = client.patch(
        f"/api/v1/shipments/{sid}/assign-reviewer",
        json={"assign_reviewer_user_id": "user_demo_reviewer"},
    )
    assert assigned.status_code == 200
    assert assigned.json()["assign_reviewer_user_id"] == "user_demo_reviewer"

    deleted = client.delete(
        f"/api/v1/shipments/{sid}/line-items/{added.json()['line_items'][-1]['id']}"
    )
    assert deleted.status_code == 200


def test_summary_pdf_cost_csv_compare_fta() -> None:
    client = make_client()
    sid = _create_shipment(client, title="Export case")
    calc = client.post(f"/api/v1/shipments/{sid}/calculate")
    assert calc.status_code == 200, calc.text

    pdf = client.get(f"/api/v1/shipments/{sid}/summary.pdf")
    assert pdf.status_code == 200, pdf.text
    assert pdf.headers["content-type"].startswith("application/pdf")
    assert pdf.content[:4] == b"%PDF"

    csv_resp = client.get(f"/api/v1/shipments/{sid}/cost.csv")
    assert csv_resp.status_code == 200
    assert "landed_cost" in csv_resp.text
    assert sid in csv_resp.text

    compare = client.post(f"/api/v1/shipments/{sid}/compare-fta")
    assert compare.status_code == 200, compare.text
    body = compare.json()
    assert body["without_preferential"]["id"]
    assert body["with_preferential"]["id"]
    assert "diff" in body


def test_watchlist_job_creates_user_notifications() -> None:
    client = make_client()
    sid = _create_shipment(client, title="Watch notify")
    watched = client.post("/api/v1/watchlist", json={"shipment_id": sid})
    assert watched.status_code == 200
    job = client.post("/api/v1/jobs/watchlist-impact")
    assert job.status_code == 200, job.text
    assert job.json()["summary"]["notifications_created"] >= 0
    notes = client.get("/api/v1/notifications")
    assert notes.status_code == 200
    assert isinstance(notes.json(), list)


def test_share_link_and_search_and_corridor_operational() -> None:
    client = make_client()
    sid = _create_shipment(client, title="Shareable clearance case")
    client.post(f"/api/v1/shipments/{sid}/checklist")

    share = client.post(f"/api/v1/shipments/{sid}/share-links")
    assert share.status_code == 200, share.text
    token = share.json()["token"]
    assert token

    public = client.get(f"/api/v1/public/share/{token}")
    assert public.status_code == 200, public.text
    body = public.json()
    assert body["shipment_id"] == sid
    assert "readiness" in body
    assert "papers" in body
    # Public share must not expose full calculation payloads.
    assert "latest_calculation" not in body

    search = client.get("/api/v1/search?q=Shareable")
    assert search.status_code == 200, search.text
    results = search.json()["results"]
    assert any(r["kind"] == "shipment" and r["shipment_id"] == sid for r in results)

    corridors = client.get("/api/v1/corridors")
    assert corridors.status_code == 200
    rows = corridors.json()
    bd_in = [c for c in rows if c["origin_country"] == "BD" and c["destination_country"] == "IN"]
    assert bd_in
    assert bd_in[0]["operational"] is True
    for c in rows:
        if not (c["origin_country"] == "BD" and c["destination_country"] == "IN"):
            assert c["operational"] is False
