"""LangGraph Ask orchestration with adaptive / baseline policies (Phase 3)."""

from __future__ import annotations

import time
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Literal, TypedDict, cast

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from backend.app.core.errors import AppError
from backend.app.data.models import AskRun
from backend.app.domain.trade import AskResponse, LandedCostInput
from backend.app.orchestration.complexity import (
    estimate_complexity,
    extract_hs,
    is_conceptual_query,
)
from backend.app.orchestration.focus import FOCUS_TOOLS, AskFocus
from backend.app.orchestration.policy import OrchestrationMode, ToolName, decide_policy
from backend.app.services import (
    ask_llm_service,
    checklist_service,
    cost_service,
    coverage_service,
    fta_service,
    retrieval_service,
    tariff_service,
)

NO_APPROVED_SOURCE = (
    "I cannot verify this against an approved source in the current dataset."
)


def _ensure_langchain_compat() -> None:
    try:
        import langchain

        if not hasattr(langchain, "debug"):
            langchain.debug = False  # type: ignore[attr-defined]
    except ImportError:
        return


class AskState(TypedDict, total=False):
    query: str
    as_of: date
    origin: str
    destination: str
    hs_code: str | None
    invoice_value: Decimal
    currency: str
    shipment_id: str | None
    orchestration_mode: OrchestrationMode
    focus: AskFocus
    intent: str
    intents: list[str]
    complexity_score: float
    complexity_label: str
    route: str
    planned_tools: list[str]
    tools_invoked: list[str]
    policy_rationale: str
    result: dict[str, Any]
    evidence: list[dict[str, Any]]
    answer: str
    warnings: list[str]
    tokens_in: int
    tokens_out: int
    evidence_score: float


def _execute_tool(
    tool: ToolName,
    *,
    session: Session,
    state: AskState,
    result: dict[str, Any],
    evidence: list[dict[str, Any]],
    answers: list[str],
    warnings: list[str],
) -> None:
    as_of = state["as_of"]
    origin = state.get("origin") or "BD"
    destination = state.get("destination") or "IN"
    hs_code = state.get("hs_code")
    query = state["query"]

    if tool == "checklist_build":
        checklist = checklist_service.build_checklist(
            session, origin=origin, destination=destination, hs_code=hs_code
        )
        result["checklist"] = checklist.model_dump(mode="json")
        answers.append(
            f"Checklist for {origin}->{destination}"
            + (f" HS {hs_code}" if hs_code else "")
            + f": {checklist.progress} items tracked."
        )
        evidence.append({"kind": "checklist_rules", "count": len(checklist.items)})
        return

    if tool == "fta_check" or tool == "graph_expand":
        if tool == "graph_expand" and "fta" in result:
            return
        if not hs_code:
            warnings.append("Missing HS code for FTA check.")
            answers.append("Provide an HS code to check FTA / preferential eligibility.")
            return
        try:
            fta = fta_service.check_fta(
                session,
                hs_code=hs_code,
                origin=origin,
                destination=destination,
                as_of=as_of,
            )
        except AppError as exc:
            if exc.code == "COVERAGE_MISS":
                result["coverage_miss"] = exc.details
                answers.append(NO_APPROVED_SOURCE)
                warnings.append(exc.message)
                return
            raise
        result["fta"] = fta.model_dump(mode="json")
        answers.append(
            f"FTA status for HS {hs_code} {origin}->{destination}: {fta.status}. "
            f"MFN {fta.mfn_rate_pct}% vs preferential {fta.preferential_rate_pct}% under "
            f"{fta.agreement_name or 'n/a'}. Certificate: {fta.certificate_doc_code or 'n/a'}."
        )
        if fta.reasons:
            answers.append("Reasons: " + "; ".join(fta.reasons[:3]))
        evidence.extend(fta.evidence)
        if fta.graph_path:
            evidence.append({"kind": "graph_path", "paths": len(fta.graph_path)})
        return

    if tool == "regulation_retrieve":
        hits = retrieval_service.search_chunks(session, query=query, hs_code=hs_code, top_k=3)
        result["retrieval"] = {"hits": [h.model_dump(mode="json") for h in hits]}
        if hits:
            answers.append(
                f"Found {len(hits)} regulatory excerpt(s). Top source: "
                f"{hits[0].source_document_id} (score {hits[0].score})."
            )
            evidence.extend(
                {
                    "kind": "regulatory_chunk",
                    "chunk_id": h.chunk_id,
                    "source_document_id": h.source_document_id,
                    "score": h.score,
                }
                for h in hits
            )
        else:
            answers.append("No matching regulatory excerpts in the prototype corpus.")
            warnings.append("Empty retrieval result.")
        return

    if tool == "landed_cost":
        shipment_id = state.get("shipment_id")
        if not shipment_id:
            warnings.append(
                "Landed cost requires a scenario to produce a reconstructable snapshot."
            )
            answers.append(
                "I will not invent unreproducible landed-cost numbers. "
                "Open a shipment/scenario and ask again so the answer can cite a "
                "calculation_snapshot_id."
            )
            return
        if not hs_code:
            warnings.append("Missing HS code for landed cost.")
            answers.append("Provide an HS code to calculate landed cost.")
            return
        from backend.app.data.models import Shipment

        ship = session.get(Shipment, shipment_id)
        if ship is None:
            warnings.append("Scenario not found.")
            answers.append("Scenario not found for landed cost.")
            return
        try:
            breakdown = cost_service.calculate(
                session,
                LandedCostInput(
                    hs_code=hs_code or ship.hs_code_working or "",
                    origin=ship.origin,
                    destination=ship.destination,
                    as_of=ship.as_of_date,
                    invoice_value=ship.invoice_value,
                    currency=ship.currency,
                    incoterm=ship.incoterm,
                    freight=ship.freight,
                    insurance=ship.insurance,
                    requested_mode="estimate",
                    shipment_id=ship.id,
                    persist_snapshot=True,
                ),
            )
        except AppError as exc:
            if exc.code == "COVERAGE_MISS":
                result["coverage_miss"] = exc.details
                answers.append(NO_APPROVED_SOURCE)
                warnings.append(exc.message)
                return
            raise
        snap_id = None
        for a in breakdown.assumptions:
            if a.startswith("calculation_snapshot_id="):
                snap_id = a.split("=", 1)[1]
                break
        result["landed_cost"] = breakdown.model_dump(mode="json")
        result["calculation_snapshot_id"] = snap_id
        cite = f" calculation_snapshot_id={snap_id}." if snap_id else ""
        answers.append(
            f"{breakdown.title} for HS {hs_code} {origin}->{destination} "
            f"as of {as_of.isoformat()}: {breakdown.landed_cost} {breakdown.currency} "
            f"(BCD {breakdown.bcd_rate_pct}%). Reconstructable via{cite}"
        )
        evidence.append(
            {
                "kind": "calculation_snapshot",
                "calculation_snapshot_id": snap_id,
                "tariff_rate_id": breakdown.tariff_rate_id,
                "source_document_id": breakdown.source_document_id,
                "data_quality": breakdown.data_quality,
            }
        )
        return

    if tool == "llm_explain":
        from backend.app.core.config import get_settings
        from backend.app.data.models import Shipment

        cfg = get_settings()
        ship = None
        sid = state.get("shipment_id")
        if sid:
            ship = session.get(Shipment, sid)
        product_text = getattr(ship, "product_text", None) if ship else None
        case_ctx = ask_llm_service.format_case_context(
            ship,
            extras={
                "ask_corridor": f"{origin}->{destination}",
                "ask_hs": hs_code or "pending",
                "ask_as_of": as_of.isoformat(),
                "product": product_text or "",
            },
        )
        prior_facts = "\n".join(a for a in answers if a)
        if product_text:
            prior_facts = f"case_product={product_text}\n{prior_facts}".strip()
        # Preferential without HS: deterministic guidance (avoid hallucinated products).
        q_lower = query.lower()
        needs_hs = any(k in q_lower for k in ("preferential", "fta", "safta", "duty rate"))
        if ship and not hs_code and needs_hs:
            answers.clear()
            answers.append(
                ask_llm_service.pending_hs_template(
                    product_text=str(product_text or ""),
                    query=query,
                )
            )
            evidence.append(
                {
                    "kind": "llm_explain",
                    "grounded": True,
                    "template": "pending_hs",
                    "has_case_context": True,
                }
            )
            return
        if result.get("fta"):
            prior_facts = (prior_facts + "\n" + f"fta_json_keys={list(result['fta'].keys())}").strip()
        explanation = ask_llm_service.grounded_explain(
            query=query,
            tool_facts=prior_facts,
            case_context=case_ctx,
            settings=cfg,
            product_text=str(product_text) if product_text else None,
        )
        if explanation:
            result["tool_facts"] = list(answers)
            answers.clear()
            answers.append(explanation)
            evidence.append(
                {
                    "kind": "llm_explain",
                    "grounded": True,
                    "model": cfg.ollama_model,
                    "has_case_context": bool(ship),
                }
            )
        else:
            reason = (
                "Ollama is disabled"
                if not cfg.ollama_enabled
                else "Ollama timed out, returned empty, or was unreachable"
            )
            answers.append(
                f"LLM explanation unavailable ({reason}). "
                "Showing verified tool outputs only — retry Ask in a moment if the model was busy."
            )
            evidence.append(
                {
                    "kind": "llm_explain_proxy",
                    "grounded": True,
                    "ollama_enabled": bool(cfg.ollama_enabled),
                }
            )
        return

    # tariff_lookup
    if not hs_code:
        rows = tariff_service.list_tariffs(
            session, origin=origin, destination=destination, as_of=as_of
        )
        result["tariffs"] = [r.model_dump(mode="json") for r in rows[:10]]
        answers.append(f"Found {len(rows)} tariff rows for {origin}->{destination} on {as_of}.")
        return

    rows = tariff_service.list_tariffs(
        session,
        hs_code=hs_code,
        origin=origin,
        destination=destination,
        as_of=as_of,
    )
    result["tariffs"] = [r.model_dump(mode="json") for r in rows]
    if rows:
        top = rows[0]
        answers.append(
            f"HS {hs_code} {origin}->{destination} as of {as_of.isoformat()}: "
            f"{top.rate}% ({top.data_quality}), source {top.source_document_id}."
        )
        evidence.append(
            {
                "kind": "tariff_rate",
                "tariff_rate_id": top.id,
                "source_document_id": top.source_document_id,
                "data_quality": top.data_quality,
                "effective_from": top.effective_from.isoformat(),
                "rate": float(top.rate),
            }
        )
    else:
        miss = coverage_service.build_coverage_miss(
            session,
            origin=origin,
            destination=destination,
            hs_code=hs_code,
            as_of=as_of,
            context="ask",
        )
        result["coverage_miss"] = miss.model_dump(mode="json")
        answers.append(NO_APPROVED_SOURCE + " " + miss.message)
        warnings.append("Empty tariff result.")


def parse_and_plan(state: AskState) -> AskState:
    query = state["query"]
    warnings = list(state.get("warnings") or [])
    hs_code = extract_hs(query, state.get("hs_code"))
    origin = state.get("origin") or "BD"
    destination = state.get("destination") or "IN"
    lower = query.lower()
    if "bangladesh" in lower:
        origin = "BD"
    if "india" in lower:
        destination = "IN"

    estimate = estimate_complexity(query, hs_code=hs_code)
    mode: OrchestrationMode = state.get("orchestration_mode") or "adaptive"
    decision = decide_policy(mode=mode, estimate=estimate, query=query)

    focus = state.get("focus")
    planned_tools: list[str] = list(decision.tools)
    route = decision.route
    rationale = decision.rationale
    if focus and mode == "adaptive":
        planned_tools = list(FOCUS_TOOLS[cast(AskFocus, focus)])
        route = {
            "tariff": "direct_lookup",
            "landed_cost": "single_tool",
            "fta": "graph_vector",
            "shipment_gaps": "multi_agent",
        }[focus]
        rationale = f"Focus action={focus}; tools={planned_tools}"

    # When Ollama is enabled, append grounded llm_explain last (Ask-only path).
    from backend.app.core.config import get_settings

    cfg = get_settings()
    conceptual = is_conceptual_query(query)
    if cfg.ollama_enabled:
        if conceptual and not focus and mode != "direct_lookup":
            # Concept questions: light tools (if any) + explanation; avoid full tariff spam.
            light: list[str] = []
            if "fta_check" in estimate.intents and hs_code:
                light.extend(["fta_check", "graph_expand"])
            if "regulation_retrieve" in estimate.intents or not light:
                light.append("regulation_retrieve")
            planned_tools = [*dict.fromkeys([*light, "llm_explain"])]
            route = "llm_grounded"
            rationale = "Conceptual Ask: retrieve context then grounded Ollama explanation"
        elif "llm_explain" not in planned_tools and mode != "direct_lookup":
            planned_tools = [*planned_tools, "llm_explain"]
            rationale = f"{rationale}; +llm_explain (Ollama grounded)"
        elif mode == "direct_lookup" and conceptual:
            planned_tools = [*planned_tools, "llm_explain"]
            rationale = f"{rationale}; +llm_explain for conceptual wrap"

    if estimate.intents and decision.primary_intent in {
        "tariff_lookup",
        "landed_cost",
        "fta_check",
    } and not hs_code:
        # Skip HS-missing warning for pure conceptual questions answered by LLM.
        if not (cfg.ollama_enabled and conceptual):
            warnings.append("No HS code detected in query; clarify HS for an exact lookup.")

    return {
        **state,
        "hs_code": hs_code,
        "origin": origin,
        "destination": destination,
        "intent": decision.primary_intent,
        "intents": list(estimate.intents),
        "complexity_score": estimate.score,
        "complexity_label": estimate.label,
        "route": route,
        "planned_tools": planned_tools,
        "policy_rationale": rationale,
        "tools_invoked": [],
        "tokens_in": decision.estimated_tokens_in,
        "tokens_out": decision.estimated_tokens_out,
        "warnings": warnings,
        "orchestration_mode": mode,
    }


def run_tools(state: AskState, session: Session) -> AskState:
    planned = [t for t in state.get("planned_tools") or [] if t]
    tools_invoked: list[str] = []
    warnings = list(state.get("warnings") or [])
    evidence: list[dict[str, Any]] = []
    result: dict[str, Any] = {}
    answers: list[str] = []

    # Deduplicate planned tools
    ordered: list[ToolName] = []
    seen: set[str] = set()
    for tool in planned:
        if tool in seen:
            continue
        seen.add(tool)
        ordered.append(cast(ToolName, tool))

    for tool in ordered:
        tools_invoked.append(tool)
        _execute_tool(
            tool,
            session=session,
            state=state,
            result=result,
            evidence=evidence,
            answers=answers,
            warnings=warnings,
        )

    answer = " ".join(answers) if answers else "No tools produced an answer."
    return {
        **state,
        "tools_invoked": tools_invoked,
        "result": result,
        "evidence": evidence,
        "answer": answer,
        "warnings": warnings,
    }


def _evidence_score(evidence: list[dict[str, Any]]) -> float:
    if not evidence:
        return 0.0
    kinds = {str(item.get("kind")) for item in evidence}
    score = 0.4
    if "tariff_rate" in kinds or "fta_eligibility" in kinds or "regulatory_chunk" in kinds:
        score += 0.4
    if "graph_path" in kinds or "checklist_rules" in kinds:
        score += 0.2
    return min(score, 1.0)


def verify(state: AskState) -> AskState:
    warnings = list(state.get("warnings") or [])
    evidence = list(state.get("evidence") or [])
    intent = state.get("intent")
    if intent in {"tariff_lookup", "landed_cost", "fta_check"} and not evidence:
        warnings.append("No source evidence attached.")
    answer = state.get("answer") or ""
    if "Illustrative" not in answer and intent != "checklist":
        answer = answer + " Values are prototype/illustrative unless marked demo_verified."
    return {
        **state,
        "warnings": warnings,
        "answer": answer,
        "evidence_score": _evidence_score(evidence),
    }


def build_ask_graph(session: Session) -> Any:
    graph = StateGraph(AskState)

    def tools_node(state: AskState) -> AskState:
        return run_tools(state, session)

    graph.add_node("parse_and_plan", parse_and_plan)
    graph.add_node("run_tools", tools_node)
    graph.add_node("verify", verify)
    graph.set_entry_point("parse_and_plan")
    graph.add_edge("parse_and_plan", "run_tools")
    graph.add_edge("run_tools", "verify")
    graph.add_edge("verify", END)
    return graph.compile()


def run_ask(
    session: Session,
    *,
    query: str,
    as_of: date,
    origin: str = "BD",
    destination: str = "IN",
    hs_code: str | None = None,
    invoice_value: Decimal | None = None,
    currency: str = "USD",
    shipment_id: str | None = None,
    orchestration_mode: OrchestrationMode = "adaptive",
    focus: AskFocus | None = None,
) -> AskResponse:
    _ensure_langchain_compat()
    started = time.perf_counter()
    if shipment_id:
        from backend.app.data.models import Shipment

        ship = session.get(Shipment, shipment_id)
        if ship is not None:
            hs_code = hs_code or ship.hs_code_working
            origin = ship.origin
            destination = ship.destination
            as_of = ship.as_of_date
            invoice_value = invoice_value or ship.invoice_value
            currency = ship.currency or currency
    app = build_ask_graph(session)
    initial: AskState = {
        "query": query,
        "as_of": as_of,
        "origin": origin,
        "destination": destination,
        "hs_code": hs_code,
        "invoice_value": invoice_value or Decimal("1000"),
        "currency": currency,
        "warnings": [],
        "orchestration_mode": orchestration_mode,
        "shipment_id": shipment_id,
    }
    if focus is not None:
        initial["focus"] = focus
    final = app.invoke(initial)
    latency_ms = int((time.perf_counter() - started) * 1000)

    run = AskRun(
        shipment_id=shipment_id,
        query=query,
        route=str(final.get("route") or "direct_lookup"),
        plan_json={
            "intent": final.get("intent"),
            "intents": final.get("intents"),
            "planned_tools": final.get("planned_tools"),
            "tools": final.get("tools_invoked"),
            "mode": final.get("orchestration_mode"),
            "focus": focus,
            "complexity_score": final.get("complexity_score"),
            "complexity_label": final.get("complexity_label"),
            "policy_rationale": final.get("policy_rationale"),
        },
        result_json=dict(final.get("result") or {}),
        evidence_json=list(final.get("evidence") or []),
        tokens_in=int(final.get("tokens_in") or 0),
        tokens_out=int(final.get("tokens_out") or 0),
        latency_ms=latency_ms,
        created_at=datetime.now(UTC),
    )
    session.add(run)
    session.flush()

    evidence = list(final.get("evidence") or [])
    result = dict(final.get("result") or {})
    warnings = list(final.get("warnings") or [])
    answer = str(final.get("answer") or "")
    decision, assumptions, next_action, source_status = _ask_contract(
        result=result,
        evidence=evidence,
        warnings=warnings,
        hs_code=hs_code,
        focus=focus,
    )
    if decision == "no_approved_source" and NO_APPROVED_SOURCE not in answer:
        answer = f"{NO_APPROVED_SOURCE} {answer}".strip()

    from backend.app.services.ask_history_service import derive_next_action_code

    # Persist contract fields for ask-history listing.
    run.result_json = {
        **result,
        "answer": answer,
        "decision": decision,
        "next_action": next_action,
        "next_action_code": derive_next_action_code(next_action),
        "assumptions": assumptions,
        "source_status": source_status,
    }
    session.flush()

    return AskResponse(
        ask_run_id=run.id,
        query=query,
        route=run.route,
        answer=answer,
        result=result,
        evidence=evidence,
        tools_invoked=list(final.get("tools_invoked") or []),
        latency_ms=latency_ms,
        tokens_in=run.tokens_in,
        tokens_out=run.tokens_out,
        warnings=warnings,
        orchestration_mode=str(final.get("orchestration_mode") or orchestration_mode),
        complexity_score=float(final.get("complexity_score") or 0.0),
        complexity_label=str(final.get("complexity_label") or "simple"),
        evidence_score=float(final.get("evidence_score") or 0.0),
        tool_count=len(list(final.get("tools_invoked") or [])),
        policy_rationale=str(final.get("policy_rationale") or ""),
        decision=decision,
        assumptions=assumptions,
        next_action=next_action,
        next_action_code=derive_next_action_code(next_action),
        source_status=source_status,
    )


def _ask_contract(
    *,
    result: dict[str, Any],
    evidence: list[dict[str, Any]],
    warnings: list[str],
    hs_code: str | None,
    focus: AskFocus | None,
) -> tuple[
    Literal[
        "confirmed",
        "likely",
        "estimated",
        "needs_information",
        "not_supported",
        "no_approved_source",
    ],
    list[str],
    str,
    str,
]:
    assumptions: list[str] = [
        "Corridor limited to the prototype dataset unless otherwise noted.",
        "Duty math is deterministic and never invented by an LLM.",
    ]
    if result.get("coverage_miss"):
        return (
            "no_approved_source",
            assumptions,
            "Search Tariff Finder for a covered HS/date or request source review.",
            "none",
        )
    missing_hs = any("Missing HS" in w for w in warnings)
    needs_hs = bool(focus and not hs_code and focus != "shipment_gaps")
    if missing_hs or needs_hs:
        return (
            "needs_information",
            [*assumptions, "HS code was not provided or detected."],
            "Provide an HS code (chapter 61) and retry.",
            "illustrative",
        )

    qualities = [
        str(e.get("data_quality"))
        for e in evidence
        if e.get("data_quality")
    ]
    fta = result.get("fta") if isinstance(result.get("fta"), dict) else None
    if fta and fta.get("data_quality"):
        qualities.append(str(fta["data_quality"]))
    landed = result.get("landed_cost") if isinstance(result.get("landed_cost"), dict) else None
    if landed and landed.get("data_quality"):
        qualities.append(str(landed["data_quality"]))

    source_status = "demo_verified" if "demo_verified" in qualities else (
        "illustrative" if qualities or evidence else "none"
    )

    if fta and fta.get("status") in {"needs_evidence", "potentially_eligible"}:
        return (
            "needs_information",
            [*assumptions, *list(fta.get("reasons") or [])[:3]],
            "Upload/confirm certificate-of-origin and product-origin evidence, then re-check.",
            source_status,
        )
    if landed and landed.get("calculation_mode") == "estimate":
        return (
            "estimated",
            [*assumptions, *list(landed.get("assumptions") or [])[:4]],
            "Add freight/insurance and confirm the tariff rule before filing.",
            source_status,
        )
    if evidence and source_status == "demo_verified":
        return (
            "likely",
            assumptions,
            "Review the cited source document and effective dates before declaring.",
            source_status,
        )
    if evidence:
        return (
            "estimated",
            [*assumptions, "Results may use illustrative demonstration rules."],
            "Treat as demonstration until an approved published source backs the rule.",
            source_status,
        )
    return (
        "not_supported",
        assumptions,
        "Rephrase with HS, corridor BD->IN, and as-of date.",
        "none",
    )
