"""Ask run history for a shipment workspace."""

from __future__ import annotations

from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.data.models import AskRun
from backend.app.domain.trade import AskHistoryItemOut

NextActionCode = Literal["upload_coo", "confirm_hs", "add_freight", "open_fta", "none"]


def derive_next_action_code(next_action: str | None) -> NextActionCode:
    text = (next_action or "").lower()
    if not text.strip():
        return "none"
    if any(
        token in text
        for token in (
            "certificate-of-origin",
            "certificate of origin",
            "coo",
            "origin evidence",
        )
    ):
        return "upload_coo"
    if "freight" in text or "insurance" in text:
        return "add_freight"
    if "hs" in text and (
        "confirm" in text or "provide" in text or "code" in text or "classification" in text
    ):
        return "confirm_hs"
    if "fta" in text or "preferential" in text or "agreement" in text:
        return "open_fta"
    return "none"


def list_for_shipment(session: Session, shipment_id: str) -> list[AskHistoryItemOut]:
    rows = session.scalars(
        select(AskRun)
        .where(AskRun.shipment_id == shipment_id)
        .order_by(AskRun.created_at.desc())
    ).all()
    out: list[AskHistoryItemOut] = []
    for row in rows:
        result = dict(row.result_json or {})
        plan = dict(row.plan_json or {})
        next_action = str(result.get("next_action") or plan.get("next_action") or "")
        answer = result.get("answer")
        if answer is not None:
            answer = str(answer)
        decision = result.get("decision")
        if decision is not None:
            decision = str(decision)
        tools = plan.get("tools") or plan.get("planned_tools") or []
        if not isinstance(tools, list):
            tools = []
        out.append(
            AskHistoryItemOut(
                ask_run_id=row.id,
                shipment_id=row.shipment_id,
                query=row.query,
                route=row.route,
                answer=answer,
                decision=decision,
                next_action=next_action or None,
                next_action_code=derive_next_action_code(next_action) if next_action else None,
                tools_invoked=[str(t) for t in tools],
                latency_ms=row.latency_ms,
                created_at=row.created_at,
            )
        )
    return out
