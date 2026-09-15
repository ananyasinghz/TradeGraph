"""Scenario decision timeline (IF-12d)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.errors import AppError
from backend.app.data.models import CalculationSnapshot, ScenarioEvent, Shipment
from backend.app.domain.trade import ScenarioTimelineEventOut, ScenarioTimelineOut


def _now() -> datetime:
    return datetime.now(UTC)


def record_event(
    session: Session,
    *,
    scenario_id: str,
    event_type: str,
    summary: str,
    payload: dict[str, Any] | None = None,
    organization_id: str | None = None,
    snapshot_id: str | None = None,
    tariff_rate_id: str | None = None,
    impact_id: str | None = None,
) -> ScenarioEvent:
    row = ScenarioEvent(
        scenario_id=scenario_id,
        organization_id=organization_id,
        event_type=event_type,
        summary=summary,
        payload_json=payload or {},
        snapshot_id=snapshot_id,
        tariff_rate_id=tariff_rate_id,
        impact_id=impact_id,
        created_at=_now(),
    )
    session.add(row)
    session.flush()
    return row


def _event_out(row: ScenarioEvent) -> ScenarioTimelineEventOut:
    return ScenarioTimelineEventOut(
        id=row.id,
        scenario_id=row.scenario_id,
        event_type=row.event_type,
        summary=row.summary,
        payload=row.payload_json or {},
        snapshot_id=row.snapshot_id,
        tariff_rate_id=row.tariff_rate_id,
        impact_id=row.impact_id,
        created_at=row.created_at,
    )


def get_timeline(
    session: Session,
    scenario_id: str,
    *,
    organization_id: str | None = None,
) -> ScenarioTimelineOut:
    ship = session.get(Shipment, scenario_id)
    if ship is None:
        raise AppError(code="SCENARIO_NOT_FOUND", message="Scenario not found", status_code=404)
    if organization_id and ship.organization_id and ship.organization_id != organization_id:
        raise AppError(code="SCENARIO_FORBIDDEN", message="Scenario not in organization", status_code=404)

    events = list(
        session.scalars(
            select(ScenarioEvent)
            .where(ScenarioEvent.scenario_id == scenario_id)
            .order_by(ScenarioEvent.created_at.desc())
        ).all()
    )

    # Backfill calculation snapshots as timeline events if none recorded yet
    snap_ids = {e.snapshot_id for e in events if e.snapshot_id}
    snapshots = session.scalars(
        select(CalculationSnapshot)
        .where(CalculationSnapshot.shipment_id == scenario_id)
        .order_by(CalculationSnapshot.created_at.desc())
    ).all()
    synthetic: list[ScenarioTimelineEventOut] = []
    for snap in snapshots:
        if snap.id in snap_ids:
            continue
        outputs = snap.outputs_json or {}
        inputs = snap.inputs_json or {}
        synthetic.append(
            ScenarioTimelineEventOut(
                id=f"snap:{snap.id}",
                scenario_id=scenario_id,
                event_type="calculation",
                summary=(
                    f"Saved calc · HS {inputs.get('hs_code') or '—'} · "
                    f"BCD {outputs.get('bcd_rate_pct', '—')}% · "
                    f"landed {outputs.get('landed_cost')} {outputs.get('currency', '')}"
                ),
                payload={
                    "landed_cost": outputs.get("landed_cost"),
                    "bcd_rate_pct": outputs.get("bcd_rate_pct"),
                    "hs_code": inputs.get("hs_code"),
                    "freight": inputs.get("freight"),
                    "mode": snap.calculation_mode,
                },
                snapshot_id=snap.id,
                created_at=snap.created_at,
            )
        )

    merged = [_event_out(e) for e in events] + synthetic
    merged.sort(key=lambda e: e.created_at, reverse=True)
    return ScenarioTimelineOut(scenario_id=scenario_id, events=merged)
